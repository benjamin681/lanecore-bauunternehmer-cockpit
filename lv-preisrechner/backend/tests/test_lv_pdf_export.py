"""Tests fuer B+4.8 — Angebots-PDF-Export.

Strategie: Wir verifizieren das **Inhalts-Niveau** des PDFs (Texte,
Zahlen) durch Re-Parse mit PyMuPDF. Layout-Pixel-Genauigkeit ist
ausser Scope — die wuerden brechen sobald jemand einen Pt verschiebt.

Was die Tests sichern:
- generate_angebot_pdf wirft bei leerem LV.
- Erfolgs-PDF enthaelt: Firmenname, Empfaenger, Angebotsnummer,
  alle OZs der Positionen, Hauptgruppen-Zwischensummen, EUR-Summe netto.
- 19% MwSt + Brutto stimmen rechnerisch.
- HTTP-Endpoint liefert Content-Type=application/pdf,
  Content-Disposition mit korrektem Filename, Tenant-Isolation 404.
"""
from __future__ import annotations

from typing import Any

import fitz
import pytest

from app.models.lv import LV
from app.models.position import Position
from app.models.tenant import Tenant
from app.services.lv_pdf_export import (
    LVExportError,
    _build_angebotsnummer,
    generate_angebot_pdf,
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
            "firma": "Trockenbau Mustermann",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _db():
    from app.core import database
    return database.SessionLocal()


def _seed_realistic_lv(db, tenant_id: str) -> str:
    """Erzeugt ein LV mit 4 Positionen in 2 Hauptgruppen (59.10, 59.20),
    realistischen Mengen + EPs."""
    lv = LV(
        tenant_id=tenant_id,
        projekt_name="Salach Ensemble-Hoefe 1.BA TG",
        auftraggeber="Bauunternehmen Beispiel GmbH",
        original_dateiname="export-test.pdf",
        status="calculated",
        angebotssumme_netto=10000.0,
    )
    db.add(lv)
    db.flush()

    rows: list[dict[str, Any]] = [
        ("59.10.0010", "Innenwand d=100mm", 100.0, "m²", 60.00, 6000.00),
        ("59.10.0020", "Innenwand d=175mm", 10.0, "m²", 70.00, 700.00),
        ("59.20.0010", "Schachtwand d=75 GKB", 50.0, "m²", 50.00, 2500.00),
        ("59.20.0020", "Schachtwand d=100 GKB", 16.0, "m²", 50.00, 800.00),
    ]
    for i, (oz, txt, menge, einheit, ep, gp) in enumerate(rows):
        p = Position(
            lv_id=lv.id,
            reihenfolge=i,
            oz=oz,
            kurztext=txt,
            menge=menge,
            einheit=einheit,
            ep=ep,
            erkanntes_system="W112",
            feuerwiderstand="F0",
            plattentyp="GKB",
            materialien=[],
            needs_price_review=False,
        )
        db.add(p)
    db.commit()
    return lv.id


def _set_company_settings(tenant_id: str, settings: dict) -> None:
    with _db() as db:
        t = db.get(Tenant, tenant_id)
        t.company_settings = settings
        db.commit()


def _extract_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


# --------------------------------------------------------------------------- #
# Service-Level
# --------------------------------------------------------------------------- #
def test_export_leeres_lv_wirft_lvexporterror(client):
    token = _register(client, "pdf-empty@example.com")
    with _db() as db:
        from app.models.user import User
        user = db.query(User).filter_by(email="pdf-empty@example.com").first()
        lv = LV(
            tenant_id=user.tenant_id,
            projekt_name="Empty",
            auftraggeber="X",
            original_dateiname="x.pdf",
            status="uploaded",
        )
        db.add(lv)
        db.commit()
        tenant = db.get(Tenant, user.tenant_id)

        with pytest.raises(LVExportError):
            generate_angebot_pdf(lv, tenant)


def test_export_enthaelt_alle_pflichtinhalte(client):
    token = _register(client, "pdf-full@example.com")
    with _db() as db:
        from app.models.user import User
        user = db.query(User).filter_by(email="pdf-full@example.com").first()
        tid = user.tenant_id
    _set_company_settings(tid, {
        "firma": "Trockenbau Mustermann GmbH",
        "anschrift_zeile1": "Beispielweg 12",
        "anschrift_zeile2": "89073 Ulm",
        "telefon": "+49 731 12345",
        "email": "info@mustermann.de",
        "iban": "DE12 3456 7890 1234",
        "bic": "MUSTDE12",
        "ust_id": "DE123456789",
    })
    with _db() as db:
        lv_id = _seed_realistic_lv(db, tid)
    with _db() as db:
        lv = db.get(LV, lv_id)
        tenant = db.get(Tenant, tid)
        pdf = generate_angebot_pdf(lv, tenant)

    assert pdf.startswith(b"%PDF-")
    text = _extract_text(pdf)
    # Briefkopf
    assert "Trockenbau Mustermann GmbH" in text
    assert "Beispielweg 12" in text
    assert "info@mustermann.de" in text
    # Empfaenger
    assert "Bauunternehmen Beispiel GmbH" in text
    assert "Salach" in text
    # Header
    assert "ANGEBOT" in text
    assert _build_angebotsnummer(lv) in text
    # Tabelle: alle OZs
    for oz in ("59.10.0010", "59.10.0020", "59.20.0010", "59.20.0020"):
        assert oz in text
    # Hauptgruppen-Subtotals
    assert "Hauptgruppe 59.10" in text
    assert "Hauptgruppe 59.20" in text
    assert "Zwischensumme 59.10" in text
    assert "Zwischensumme 59.20" in text
    # Summen-Block
    assert "Gesamtsumme netto" in text
    assert "19" in text  # 19 % USt.
    assert "Gesamtsumme brutto" in text
    # Footer / Bank
    assert "DE12 3456 7890 1234" in text


def test_export_summen_rechnen_korrekt(client):
    """Brutto = Netto * 1.19, mwst gerundet auf 2 Dezimalen."""
    token = _register(client, "pdf-sum@example.com")
    with _db() as db:
        from app.models.user import User
        user = db.query(User).filter_by(email="pdf-sum@example.com").first()
        tid = user.tenant_id

    with _db() as db:
        lv_id = _seed_realistic_lv(db, tid)
    with _db() as db:
        lv = db.get(LV, lv_id)
        tenant = db.get(Tenant, tid)
        # Override netto auf einen krummen Wert, um Rundung zu pruefen
        lv.angebotssumme_netto = 12345.67
        db.commit()
        db.refresh(lv)
        pdf = generate_angebot_pdf(lv, tenant)
    text = _extract_text(pdf)
    # 12.345,67 + 19 % = 14.691,35 ; 19 % = 2.345,68
    assert "12.345,67 EUR" in text
    assert "2.345,68 EUR" in text
    assert "14.691,35 EUR" in text


# --------------------------------------------------------------------------- #
# HTTP-Endpoint
# --------------------------------------------------------------------------- #
def test_endpoint_liefert_pdf_mit_attachment_filename(client):
    token = _register(client, "pdf-http@example.com")
    with _db() as db:
        from app.models.user import User
        user = db.query(User).filter_by(email="pdf-http@example.com").first()
        tid = user.tenant_id
    with _db() as db:
        lv_id = _seed_realistic_lv(db, tid)

    r = client.get(f"/api/v1/lvs/{lv_id}/export-pdf", headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    cd = r.headers.get("content-disposition", "")
    assert cd.startswith("attachment; ")
    assert ".pdf" in cd
    assert r.content.startswith(b"%PDF-")


def test_endpoint_inline_modus(client):
    token = _register(client, "pdf-inline@example.com")
    with _db() as db:
        from app.models.user import User
        user = db.query(User).filter_by(email="pdf-inline@example.com").first()
        tid = user.tenant_id
    with _db() as db:
        lv_id = _seed_realistic_lv(db, tid)

    r = client.get(
        f"/api/v1/lvs/{lv_id}/export-pdf?inline=true",
        headers=_auth(token),
    )
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("inline; ")


def test_endpoint_fremder_tenant_404(client):
    owner = _register(client, "pdf-owner@example.com")
    with _db() as db:
        from app.models.user import User
        u = db.query(User).filter_by(email="pdf-owner@example.com").first()
        tid_owner = u.tenant_id
    with _db() as db:
        lv_id = _seed_realistic_lv(db, tid_owner)

    stranger = _register(client, "pdf-stranger@example.com")
    r = client.get(f"/api/v1/lvs/{lv_id}/export-pdf", headers=_auth(stranger))
    assert r.status_code == 404
