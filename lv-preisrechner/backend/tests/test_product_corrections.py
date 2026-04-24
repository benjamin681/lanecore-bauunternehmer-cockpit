"""Tests fuer den B+4.4 P4 Review-/Correction-Workflow.

Deckt:
- GET /pricing/entries/{pricelist_id}/review — gruppiert nach review_reason.
- POST /pricing/entries/{entry_id}/correct — wendet Korrektur auf Entry an,
  persistiert optional in lvp_product_corrections.
- Upsert-Verhalten: Mehrfach-Correct auf gleichem Key erzeugt keine Dubletten.
- Parser-Hook: apply_known_corrections_to_entries setzt die Felder eines
  frisch geparsten Entry anhand einer zuvor gespeicherten Korrektur.
"""
from __future__ import annotations

import io
import uuid

from app.models.pricing import (
    ProductCorrection,
    SupplierPriceEntry,
    SupplierPriceList,
)
from app.services.product_corrections import (
    apply_known_corrections_to_entries,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _sl():
    from app.core import database

    return database.SessionLocal


def _register_and_login(c, email: str, firma: str = "T") -> str:
    r = c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "pw-testtest",
            "vorname": "T",
            "nachname": "U",
            "firma": firma,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _upload_pricelist(c, token: str) -> str:
    filename = f"seed-{uuid.uuid4().hex[:8]}.pdf"
    resp = c.post(
        "/api/v1/pricing/upload",
        headers=_auth(token),
        files={"file": (filename, io.BytesIO(b"%PDF-1.4 seed"), "application/pdf")},
        data={
            "supplier_name": "Kemmler",
            "list_name": "Review-Test",
            "valid_from": "2026-04-01",
            "auto_parse": "false",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _seed_entry(
    pricelist_id: str,
    tenant_id: str,
    *,
    product_name: str,
    article_number: str | None,
    review_reason: str | None = "bundgroesse_fehlt",
    needs_review: bool = True,
    package_size: float | None = 3.0,
    price_net: float = 318.80,
    manufacturer: str | None = "Kemmler",
) -> str:
    with _sl()() as db:
        attrs: dict = {}
        if review_reason:
            attrs["review_reason"] = review_reason
        e = SupplierPriceEntry(
            pricelist_id=pricelist_id,
            tenant_id=tenant_id,
            article_number=article_number,
            manufacturer=manufacturer,
            product_name=product_name,
            price_net=price_net,
            currency="EUR",
            unit="€/m",
            package_size=package_size,
            pieces_per_package=None,
            effective_unit="lfm",
            price_per_effective_unit=price_net,
            attributes=attrs,
            source_page=1,
            parser_confidence=0.3,
            needs_review=needs_review,
        )
        db.add(e)
        db.commit()
        db.refresh(e)
        return e.id


def _tenant_id_of_pricelist(pricelist_id: str) -> str:
    with _sl()() as db:
        pl = db.get(SupplierPriceList, pricelist_id)
        assert pl is not None
        return pl.tenant_id


# --------------------------------------------------------------------------- #
# GET /review — gruppiert
# --------------------------------------------------------------------------- #
def test_review_overview_gruppiert_nach_review_reason(client):
    token = _register_and_login(client, "review1@example.com")
    pl_id = _upload_pricelist(client, token)
    tid = _tenant_id_of_pricelist(pl_id)

    # 2x bundgroesse_fehlt, 1x einheit_nicht_erkannt, 1x ok (nicht im Review)
    _seed_entry(
        pl_id, tid, product_name="UA-Profil 48x40x2 BL=3000",
        article_number="3575100048", review_reason="bundgroesse_fehlt",
    )
    _seed_entry(
        pl_id, tid, product_name="UA-Profil 73x40x2 BL=3000",
        article_number="3575100056", review_reason="bundgroesse_fehlt",
    )
    _seed_entry(
        pl_id, tid, product_name="Trennwandkitt",
        article_number="3590700002", review_reason="einheit_nicht_erkannt",
    )
    _seed_entry(
        pl_id, tid, product_name="GKB-Platte", article_number="35301",
        review_reason=None, needs_review=False,
    )

    resp = client.get(
        f"/api/v1/pricing/entries/{pl_id}/review", headers=_auth(token)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["pricelist_id"] == pl_id
    assert body["total_needs_review"] == 3

    reason_to_count = {g["review_reason"]: g["count"] for g in body["groups"]}
    assert reason_to_count["bundgroesse_fehlt"] == 2
    assert reason_to_count["einheit_nicht_erkannt"] == 1

    # Groessere Gruppe kommt zuerst (sort key: -count, reason-alpha)
    assert body["groups"][0]["review_reason"] == "bundgroesse_fehlt"


def test_review_overview_fremder_tenant_404(client):
    t1 = _register_and_login(client, "owner@example.com")
    pl_id = _upload_pricelist(client, t1)

    t2 = _register_and_login(client, "stranger@example.com", firma="Andere")
    resp = client.get(
        f"/api/v1/pricing/entries/{pl_id}/review", headers=_auth(t2)
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# POST /correct
# --------------------------------------------------------------------------- #
def test_correct_pieces_per_package_berechnet_ppeu_neu(client):
    token = _register_and_login(client, "correct@example.com")
    pl_id = _upload_pricelist(client, token)
    tid = _tenant_id_of_pricelist(pl_id)

    # UA-Profil BL=3000mm (package_size=3.0), 318.80 EUR Bundpreis
    e_id = _seed_entry(
        pl_id, tid, product_name="UA-Profil 48x40x2 BL=3000 mm",
        article_number="3575100048", package_size=3.0, price_net=318.80,
    )

    resp = client.post(
        f"/api/v1/pricing/entries/{e_id}/correct",
        headers=_auth(token),
        json={
            "correction_type": "pieces_per_package",
            "corrected_value": {"pieces_per_package": 6},
            "persist": True,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    entry = body["entry"]

    # 6 St. x 3m = 18 lfm pro Bund -> 318.80 / 18 = 17.711...
    assert entry["pieces_per_package"] == 6
    assert abs(entry["price_per_effective_unit"] - 17.7111) < 0.01
    assert entry["needs_review"] is False
    assert entry["correction_applied"] is True

    # review_reason archiviert, nicht geloescht
    attrs = entry["attributes"]
    assert attrs.get("review_reason_resolved") == "bundgroesse_fehlt"
    assert "review_reason" not in attrs  # wurde umbenannt
    assert attrs.get("correction_source") == "manual_user_input"

    # Persistenz pruefen
    assert body["correction_persisted"] is True
    assert body["correction_id"] is not None


def test_correct_ohne_persist_speichert_keine_correction(client):
    token = _register_and_login(client, "nopersist@example.com")
    pl_id = _upload_pricelist(client, token)
    tid = _tenant_id_of_pricelist(pl_id)
    e_id = _seed_entry(
        pl_id, tid, product_name="UA-Profil 48x40x2",
        article_number="3575100048", package_size=3.0,
    )

    resp = client.post(
        f"/api/v1/pricing/entries/{e_id}/correct",
        headers=_auth(token),
        json={
            "correction_type": "pieces_per_package",
            "corrected_value": {"pieces_per_package": 6},
            "persist": False,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["correction_persisted"] is False

    with _sl()() as db:
        count = db.query(ProductCorrection).count()
    assert count == 0


def test_correct_upsert_keine_dubletten(client):
    token = _register_and_login(client, "upsert@example.com")
    pl_id = _upload_pricelist(client, token)
    tid = _tenant_id_of_pricelist(pl_id)
    e_id = _seed_entry(
        pl_id, tid, product_name="UA-Profil 48x40x2 BL=3000",
        article_number="3575100048", package_size=3.0,
    )

    def _post(pieces: int):
        return client.post(
            f"/api/v1/pricing/entries/{e_id}/correct",
            headers=_auth(token),
            json={
                "correction_type": "pieces_per_package",
                "corrected_value": {"pieces_per_package": pieces},
                "persist": True,
            },
        )

    # Erste Korrektur: pieces=6
    r1 = _post(6)
    assert r1.status_code == 200
    cid1 = r1.json()["correction_id"]

    # Zweite Korrektur auf gleichem Key: pieces=8 — updated den bestehenden Eintrag
    r2 = _post(8)
    assert r2.status_code == 200
    cid2 = r2.json()["correction_id"]
    assert cid1 == cid2, "Upsert muss die ID beibehalten, nicht neue anlegen"

    with _sl()() as db:
        rows = db.query(ProductCorrection).all()
        assert len(rows) == 1
        assert rows[0].corrected_value == {"pieces_per_package": 8}


def test_correct_validation_fehler_gibt_422(client):
    token = _register_and_login(client, "invalid@example.com")
    pl_id = _upload_pricelist(client, token)
    tid = _tenant_id_of_pricelist(pl_id)
    e_id = _seed_entry(
        pl_id, tid, product_name="UA-Profil", article_number="X"
    )

    # pieces_per_package als String -> Service lehnt ab
    resp = client.post(
        f"/api/v1/pricing/entries/{e_id}/correct",
        headers=_auth(token),
        json={
            "correction_type": "pieces_per_package",
            "corrected_value": {"pieces_per_package": "sechs"},
            "persist": True,
        },
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Parser-Hook
# --------------------------------------------------------------------------- #
def test_parser_hook_wendet_bekannte_correction_an(client):
    """Wenn fuer (manufacturer, article_number) schon eine Korrektur
    gespeichert ist, wendet apply_known_corrections_to_entries sie beim
    naechsten Parse automatisch an."""
    token = _register_and_login(client, "hook@example.com")
    pl_id = _upload_pricelist(client, token)
    tid = _tenant_id_of_pricelist(pl_id)

    # User-ID aus der DB holen (ProductCorrection.created_by_user_id ist NOT NULL)
    from app.models.user import User
    with _sl()() as db:
        user = db.query(User).filter(User.email == "hook@example.com").first()
        assert user is not None
        user_id = user.id

    # Korrektur vorab persistieren
    with _sl()() as db:
        db.add(
            ProductCorrection(
                tenant_id=tid,
                manufacturer="Kemmler",
                article_number="3575100048",
                product_name_fallback="UA-Profil 48x40x2 BL=3000",
                correction_type="pieces_per_package",
                corrected_value={"pieces_per_package": 6},
                created_by_user_id=user_id,
            )
        )
        db.commit()

    # Jetzt eine frische Entry-Zeile in die DB legen (simuliert neuen Parse)
    e_id = _seed_entry(
        pl_id, tid,
        product_name="UA-Profil 48x40x2 BL=3000 mm",
        article_number="3575100048",
        package_size=3.0,
        price_net=318.80,
    )

    # Hook aufrufen
    with _sl()() as db:
        entry = db.get(SupplierPriceEntry, e_id)
        modified = apply_known_corrections_to_entries(
            db=db,
            tenant_id=tid,
            entries=[entry],
        )
        db.commit()
        db.refresh(entry)

    assert modified == 1
    assert entry.pieces_per_package == 6
    assert abs(entry.price_per_effective_unit - 17.7111) < 0.01
    assert entry.needs_review is False
    assert entry.correction_applied is True
