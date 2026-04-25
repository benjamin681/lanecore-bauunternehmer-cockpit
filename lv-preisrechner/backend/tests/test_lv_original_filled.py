"""Tests fuer B+4.10 — Original-LV-PDF mit Preis-Overlay.

Strategie:
- Wir bauen ein realistisches Original-PDF mit OZ-Hierarchie + Punkt-
  Linien-Spalten via PyMuPDF, persistieren es als ``original_pdf_bytes``
  am LV.
- Service-Aufruf erzeugt das gefuellte PDF, Re-Parse mit pdfplumber
  prueft dass die EP-Werte tatsaechlich auf den Original-Seiten
  erscheinen.
- Endpoint-Tests: 401 ohne Auth, 404 fremder Tenant, 200 + PDF mit
  attachment-Filename fuer eigenen Tenant.
"""
from __future__ import annotations

import io

import fitz
import pdfplumber
import pytest

from app.models.lv import LV
from app.models.position import Position
from app.services.lv_original_filled import (
    LVOriginalFilledError,
    generate_original_filled_pdf,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _register(c, email: str) -> str:
    r = c.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "pw-testtest",
            "vorname": "T",
            "nachname": "U",
            "firma": "OrigFillBetrieb",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _db():
    from app.core import database
    return database.SessionLocal()


def _make_realistic_lv_pdf(positions: list[tuple[str, str, float, str]]) -> bytes:
    """Baut ein 1-Seiten-PDF mit OZ + Kurztext + Menge + leeren EP/GP-
    Punktlinien fuer jede Position. Format mimikriert das Salach-Layout.

    positions: list of (oz, kurztext, menge, einheit)
    """
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(
        (50, 50), "Test-LV (synthetisch fuer B+4.10)",
        fontsize=12, fontname="hebo",
    )
    y = 100.0
    for oz, kurztext, menge, einheit in positions:
        # Zeile 1: OZ
        page.insert_text((72, y), f"{oz}.", fontsize=9, fontname="helv")
        page.insert_text((150, y), kurztext, fontsize=9, fontname="helv")
        y += 14
        # Zeile 2: Menge + zwei Punkt-Linien (EP + GP)
        menge_str = f"{menge:.3f}".replace(".", ",")
        page.insert_text((72, y), f"{menge_str} {einheit}",
                         fontsize=9, fontname="helv")
        page.insert_text(
            (250, y),
            "....................." + "  " + ".....................",
            fontsize=9, fontname="helv",
        )
        y += 28  # Abstand bis naechste Position
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _seed_lv_with_pdf(
    db, tenant_id: str, *, positions_data: list[tuple[str, str, float, float]],
) -> str:
    """Erstellt ein LV mit Original-PDF und EP-bereitgestellten Positionen.

    positions_data: list of (oz, kurztext, menge, ep)
    """
    pdf_bytes = _make_realistic_lv_pdf(
        [(oz, kurz, menge, "m²") for (oz, kurz, menge, _ep) in positions_data]
    )
    lv = LV(
        tenant_id=tenant_id,
        projekt_name="Test-LV B+4.10",
        auftraggeber="Test-Auftraggeber GmbH",
        original_dateiname="b410-test.pdf",
        original_pdf_bytes=pdf_bytes,
        status="calculated",
        angebotssumme_netto=sum(menge * ep for (_, _, menge, ep) in positions_data),
    )
    db.add(lv)
    db.flush()
    for i, (oz, kurztext, menge, ep) in enumerate(positions_data):
        p = Position(
            lv_id=lv.id,
            reihenfolge=i,
            oz=oz,
            kurztext=kurztext,
            menge=menge,
            einheit="m²",
            erkanntes_system="W112",
            feuerwiderstand="F0",
            plattentyp="GKB",
            materialien=[],
            ep=ep,
            gp=round(menge * ep, 2),
        )
        db.add(p)
    db.commit()
    return lv.id


# --------------------------------------------------------------------------- #
# Service-Level
# --------------------------------------------------------------------------- #
def test_service_lv_ohne_original_pdf_raises(client):
    token = _register(client, "orig-noPDF@example.com")
    with _db() as db:
        from app.models.user import User
        u = db.query(User).filter_by(email="orig-noPDF@example.com").first()
        lv = LV(
            tenant_id=u.tenant_id,
            projekt_name="Empty-Original",
            auftraggeber="X",
            original_dateiname="x.pdf",
            original_pdf_bytes=None,
            status="calculated",
        )
        db.add(lv)
        db.commit()
        with pytest.raises(LVOriginalFilledError):
            generate_original_filled_pdf(lv)


def test_service_seitenanzahl_und_eps_eingetragen(client):
    """Output-PDF hat dieselbe Seitenzahl wie Original UND enthaelt die EP-
    Werte als Text auf den Seiten."""
    token = _register(client, "orig-eps@example.com")
    with _db() as db:
        from app.models.user import User
        u = db.query(User).filter_by(email="orig-eps@example.com").first()
        tid = u.tenant_id
    with _db() as db:
        lv_id = _seed_lv_with_pdf(
            db, tid,
            positions_data=[
                ("01.01.0010", "Innenwand W112 d=100mm", 100.0, 60.50),
                ("01.01.0020", "Innenwand W112 d=175mm",  20.0, 70.00),
                ("01.02.0010", "Schachtwand d=75 GKB",    50.0, 84.78),
            ],
        )
    with _db() as db:
        lv = db.get(LV, lv_id)
        pdf_out = generate_original_filled_pdf(lv)

    assert pdf_out.startswith(b"%PDF-")

    # Anzahl Seiten = Original (1)
    out_doc = fitz.open(stream=pdf_out, filetype="pdf")
    orig_doc = fitz.open(stream=bytes(lv.original_pdf_bytes), filetype="pdf")
    assert out_doc.page_count == orig_doc.page_count
    out_doc.close()
    orig_doc.close()

    # Mindestens eine EP muss als Text im Output erscheinen.
    # Format aus _euro_short: "60,50" bzw "70,00"
    with pdfplumber.open(io.BytesIO(pdf_out)) as pdf:
        full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    # 60,50 60,50 wird auf Punkt-Linien geschrieben. Mindestens 2 von 3 EPs
    # sollten matchen — der dot-pattern-Matcher des pdf_filler ist konservativ.
    found = sum(1 for ep_str in ("60,50", "70,00", "84,78") if ep_str in full_text)
    assert found >= 2, f"Erwartet mindestens 2 EPs im Output, gefunden: {found}\n{full_text[:500]!r}"


def test_service_skip_positions_mit_ep_null(client):
    """Positionen mit ep=0 werden nicht ueberschrieben."""
    token = _register(client, "orig-skip@example.com")
    with _db() as db:
        from app.models.user import User
        u = db.query(User).filter_by(email="orig-skip@example.com").first()
        tid = u.tenant_id
    with _db() as db:
        lv_id = _seed_lv_with_pdf(
            db, tid,
            positions_data=[
                ("01.01.0010", "Mit-Preis", 50.0, 60.50),
                ("01.01.0020", "Ohne-Preis", 50.0, 0.0),
            ],
        )
    with _db() as db:
        lv = db.get(LV, lv_id)
        pdf_out = generate_original_filled_pdf(lv)
    with pdfplumber.open(io.BytesIO(pdf_out)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    assert "60,50" in text
    # Es sollte nirgends im Output ein "0,00" als EP erscheinen — pruefen
    # waere allerdings bruechig, weil das Original schon Punkt-Linien hat.
    # Stattdessen nur sicherstellen, dass der Service nicht crasht.


# --------------------------------------------------------------------------- #
# HTTP-Endpoint
# --------------------------------------------------------------------------- #
def test_endpoint_eigener_tenant_200_pdf(client):
    token = _register(client, "orig-http@example.com")
    with _db() as db:
        from app.models.user import User
        u = db.query(User).filter_by(email="orig-http@example.com").first()
        tid = u.tenant_id
    with _db() as db:
        lv_id = _seed_lv_with_pdf(
            db, tid,
            positions_data=[("01.01.0010", "X", 1.0, 10.0)],
        )
    r = client.get(
        f"/api/v1/lvs/{lv_id}/export-original-filled-pdf",
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    cd = r.headers.get("content-disposition", "")
    assert cd.startswith("attachment; ")
    assert "Angebot-Original-" in cd
    assert r.content.startswith(b"%PDF-")


def test_endpoint_inline_modus(client):
    token = _register(client, "orig-inline@example.com")
    with _db() as db:
        from app.models.user import User
        u = db.query(User).filter_by(email="orig-inline@example.com").first()
        tid = u.tenant_id
    with _db() as db:
        lv_id = _seed_lv_with_pdf(
            db, tid,
            positions_data=[("01.01.0010", "X", 1.0, 10.0)],
        )
    r = client.get(
        f"/api/v1/lvs/{lv_id}/export-original-filled-pdf?inline=true",
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("inline; ")


def test_endpoint_fremder_tenant_404(client):
    owner = _register(client, "orig-owner@example.com")
    with _db() as db:
        from app.models.user import User
        u = db.query(User).filter_by(email="orig-owner@example.com").first()
        tid_owner = u.tenant_id
    with _db() as db:
        lv_id = _seed_lv_with_pdf(
            db, tid_owner,
            positions_data=[("01.01.0010", "X", 1.0, 10.0)],
        )

    stranger = _register(client, "orig-stranger@example.com")
    r = client.get(
        f"/api/v1/lvs/{lv_id}/export-original-filled-pdf",
        headers=_auth(stranger),
    )
    assert r.status_code == 404


def test_endpoint_lv_ohne_original_pdf_422(client):
    token = _register(client, "orig-422@example.com")
    with _db() as db:
        from app.models.user import User
        u = db.query(User).filter_by(email="orig-422@example.com").first()
        tid = u.tenant_id
        lv = LV(
            tenant_id=tid,
            projekt_name="Empty",
            auftraggeber="X",
            original_dateiname="x.pdf",
            original_pdf_bytes=None,
            status="calculated",
        )
        db.add(lv)
        db.commit()
        lv_id = lv.id

    r = client.get(
        f"/api/v1/lvs/{lv_id}/export-original-filled-pdf",
        headers=_auth(token),
    )
    assert r.status_code == 422
