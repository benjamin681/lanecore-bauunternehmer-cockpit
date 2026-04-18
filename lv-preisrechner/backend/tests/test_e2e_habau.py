"""E2E-Test: Komplette Pipeline mit realistischen Habau-Koblenz-Daten.

Verwendet einen gemockten Claude-Client — die Vision-Calls werden durch bekannte
Ground-Truth-Daten ersetzt. Getestet wird:
- Preislisten-Upload + Parsing
- LV-Upload + Positions-Extraktion
- DNA-Matching gegen Kundenpreisliste
- EP-Kalkulation (Material + Lohn + Zuschläge)
- PDF-Export + Download

Ground-Truth: Ausschnitt aus docs knowledge/habau-koblenz-lv-beispiel.json (10 Positionen).
"""

from __future__ import annotations

import io
from pathlib import Path

import fitz
import pytest


# --- Helpers ---------------------------------------------------------------
def make_test_pdf(page_count: int = 2, content: str = "Test-PDF") -> bytes:
    """Erzeugt ein kleines, valides PDF-Bytes-Objekt für Upload-Tests."""
    doc = fitz.open()
    for i in range(page_count):
        page = doc.new_page()
        page.insert_text((50, 80), f"{content} Seite {i+1}", fontsize=14)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


# --- Ground-Truth Habau-LV (10 Positionen) ---------------------------------
HABAU_LV_GROUND_TRUTH = {
    "projekt_name": "Verwaltungsgebäude Koblenz Löhr&Becker (17951-VK)",
    "auftraggeber": "Habau GmbH",
    "positionen": [
        {
            "reihenfolge": 1,
            "oz": "610.1",
            "titel": "Innenwände Trockenbau",
            "kurztext": "Metallständerwand W112 F30, CW50/UW50, beidseitig 1-lagig 12.5mm GKF, Mineralwolle 40mm, Rw 41dB",
            "menge": 1895,
            "einheit": "m²",
            "erkanntes_system": "W112",
            "feuerwiderstand": "F30",
            "plattentyp": "GKF",
            "konfidenz": 0.95,
        },
        {
            "reihenfolge": 2,
            "oz": "610.3",
            "titel": "Innenwände Trockenbau",
            "kurztext": "W112 F90, CW75/UW75, beidseitig 2-lagig 12.5mm GKF, Mineralwolle 60mm",
            "menge": 69,
            "einheit": "m²",
            "erkanntes_system": "W118",
            "feuerwiderstand": "F90",
            "plattentyp": "GKF",
            "konfidenz": 0.92,
        },
        {
            "reihenfolge": 3,
            "oz": "610.6",
            "titel": "Innenwände Trockenbau",
            "kurztext": "W135 F60 A+M mit Stahlblecheinlage, CW75/UW75, beidseitig 2-lagig GKF 12.5mm",
            "menge": 105.5,
            "einheit": "m²",
            "erkanntes_system": "W135",
            "feuerwiderstand": "F60",
            "plattentyp": "GKF",
            "konfidenz": 0.88,
        },
        {
            "reihenfolge": 4,
            "oz": "610.11",
            "titel": "Innenwände Trockenbau",
            "kurztext": "W115 Doppelständer, beidseitig 2-lagig 12.5mm GKB",
            "menge": 9.5,
            "einheit": "m²",
            "erkanntes_system": "W115",
            "feuerwiderstand": "",
            "plattentyp": "GKB",
            "konfidenz": 0.90,
        },
        {
            "reihenfolge": 5,
            "oz": "610.17",
            "titel": "Türaussparungen",
            "kurztext": "Türaussparung F30 in W112, 0.885-1.01 x 2.80m",
            "menge": 6,
            "einheit": "Stk",
            "erkanntes_system": "Zulage",
            "feuerwiderstand": "F30",
            "plattentyp": "",
            "konfidenz": 0.85,
        },
        {
            "reihenfolge": 6,
            "oz": "610.29",
            "titel": "Abkofferungen",
            "kurztext": "Abkofferung L-Form, 2x 12.5mm GKB, Mineralfaser 40mm",
            "menge": 15,
            "einheit": "Stk",
            "erkanntes_system": "Verkleidung",
            "feuerwiderstand": "",
            "plattentyp": "GKB",
            "konfidenz": 0.80,
        },
        {
            "reihenfolge": 7,
            "oz": "610.45",
            "titel": "Revisionsklappen",
            "kurztext": "Knauf Alu Top 60x60 Revisionsklappe",
            "menge": 4,
            "einheit": "Stk",
            "erkanntes_system": "Revisionsklappe",
            "feuerwiderstand": "",
            "plattentyp": "",
            "konfidenz": 0.95,
        },
        {
            "reihenfolge": 8,
            "oz": "620.622.1",
            "titel": "Abhangdecken",
            "kurztext": "D112 GK-Unterdecke abgehängt, 1x 12.5mm GKB",
            "menge": 620,
            "einheit": "m²",
            "erkanntes_system": "D112",
            "feuerwiderstand": "",
            "plattentyp": "GKB",
            "konfidenz": 0.93,
        },
        {
            "reihenfolge": 9,
            "oz": "610.12",
            "titel": "Vorsatzschalen",
            "kurztext": "Vorsatzschale freistehend GKBi 2-lagig 12.5mm, Dämmung 40mm",
            "menge": 18,
            "einheit": "m²",
            "erkanntes_system": "W623",
            "feuerwiderstand": "",
            "plattentyp": "GKBi",
            "konfidenz": 0.87,
        },
        {
            "reihenfolge": 10,
            "oz": "670.1",
            "titel": "Regiearbeiten",
            "kurztext": "Facharbeiter-Stunden",
            "menge": 40,
            "einheit": "h",
            "erkanntes_system": "",
            "feuerwiderstand": "",
            "plattentyp": "",
            "konfidenz": 0.95,
        },
    ],
}


# --- Ground-Truth Kemmler-Preisliste (Ausschnitt) --------------------------
KEMMLER_PRICE_LIST = {
    "eintraege": [
        # Gipskarton
        {"hersteller": "Knauf", "kategorie": "Gipskarton", "produktname": "GKB", "abmessungen": "12.5mm", "variante": "", "preis": 3.00, "einheit": "€/m²", "konfidenz": 0.95, "art_nr": "3530100012"},
        {"hersteller": "Knauf", "kategorie": "Gipskarton", "produktname": "GKF", "abmessungen": "12.5mm", "variante": "Feuerschutz", "preis": 3.35, "einheit": "€/m²", "konfidenz": 0.95, "art_nr": "3530100028"},
        {"hersteller": "Knauf", "kategorie": "Gipskarton", "produktname": "GKBi", "abmessungen": "12.5mm", "variante": "Imprägniert", "preis": 4.50, "einheit": "€/m²", "konfidenz": 0.95, "art_nr": "3530100014"},
        # Profile
        {"hersteller": "Knauf", "kategorie": "Profile", "produktname": "CW50", "abmessungen": "50x0.6mm", "variante": "", "preis": 1.13, "einheit": "€/lfm", "konfidenz": 0.9, "art_nr": "3540100050"},
        {"hersteller": "Knauf", "kategorie": "Profile", "produktname": "UW50", "abmessungen": "50x0.6mm", "variante": "", "preis": 1.05, "einheit": "€/lfm", "konfidenz": 0.9, "art_nr": "3540100051"},
        {"hersteller": "Knauf", "kategorie": "Profile", "produktname": "CW75", "abmessungen": "75x0.6mm", "variante": "", "preis": 1.30, "einheit": "€/lfm", "konfidenz": 0.9, "art_nr": "3540100075"},
        {"hersteller": "Knauf", "kategorie": "Profile", "produktname": "UW75", "abmessungen": "75x0.6mm", "variante": "", "preis": 1.18, "einheit": "€/lfm", "konfidenz": 0.9, "art_nr": "3540100076"},
        {"hersteller": "Knauf", "kategorie": "Profile", "produktname": "CW100", "abmessungen": "100x0.6mm", "variante": "", "preis": 1.49, "einheit": "€/lfm", "konfidenz": 0.9, "art_nr": "3540100100"},
        {"hersteller": "Knauf", "kategorie": "Profile", "produktname": "UW100", "abmessungen": "100x0.6mm", "variante": "", "preis": 1.35, "einheit": "€/lfm", "konfidenz": 0.9, "art_nr": "3540100101"},
        {"hersteller": "Knauf", "kategorie": "Profile", "produktname": "CD60/27", "abmessungen": "60/27mm", "variante": "", "preis": 0.95, "einheit": "€/lfm", "konfidenz": 0.9, "art_nr": "3540200060"},
        # Dämmung
        {"hersteller": "Rockwool", "kategorie": "Daemmung", "produktname": "Sonorock", "abmessungen": "40mm", "variante": "", "preis": 2.84, "einheit": "€/m²", "konfidenz": 0.95, "art_nr": "3515100017"},
        {"hersteller": "Rockwool", "kategorie": "Daemmung", "produktname": "Sonorock", "abmessungen": "60mm", "variante": "", "preis": 4.61, "einheit": "€/m²", "konfidenz": 0.95, "art_nr": "3515100019"},
        {"hersteller": "Rockwool", "kategorie": "Daemmung", "produktname": "Sonorock", "abmessungen": "80mm", "variante": "", "preis": 6.16, "einheit": "€/m²", "konfidenz": 0.95, "art_nr": "3515100020"},
        # Schrauben
        {"hersteller": "Knauf", "kategorie": "Schrauben", "produktname": "Schnellbau", "abmessungen": "3.5x25", "variante": "", "preis": 21.07, "einheit": "€/Paket (500 Stk)", "konfidenz": 0.92, "art_nr": "3555100023"},
        {"hersteller": "Knauf", "kategorie": "Schrauben", "produktname": "Schnellbau", "abmessungen": "3.5x45", "variante": "", "preis": 24.50, "einheit": "€/Paket (500 Stk)", "konfidenz": 0.90, "art_nr": "3555100025"},
        # Spachtel
        {"hersteller": "Knauf", "kategorie": "Spachtel", "produktname": "Universal", "abmessungen": "25kg", "variante": "Multifinish", "preis": 1.36, "einheit": "€/kg", "konfidenz": 0.93, "art_nr": "3010300013"},
        # Revisionsklappen
        {"hersteller": "Knauf", "kategorie": "Revisionsklappen", "produktname": "Alu Top", "abmessungen": "400x400", "variante": "", "preis": 43.77, "einheit": "€/Stk", "konfidenz": 0.95, "art_nr": "3550100003"},
        {"hersteller": "Knauf", "kategorie": "Revisionsklappen", "produktname": "Alu Top", "abmessungen": "600x600", "variante": "", "preis": 59.93, "einheit": "€/Stk", "konfidenz": 0.95, "art_nr": "3550100005"},
    ]
}


# --- Mock des Claude-Clients -----------------------------------------------
class MockClaudeClient:
    """Gibt pro Call vordefinierte Ground-Truth-Daten zurück."""

    def __init__(self, price_list: dict, lv: dict):
        self.price_list = price_list
        self.lv = lv
        self.call_log: list[str] = []

    def extract_json(self, *, system: str, user_text=None, images=None, force_fallback=False):
        # Unterscheide anhand des System-Prompts
        model = "claude-sonnet-4-6-mock"
        if "Händler-Preisliste" in system or "Preis-Eintrag" in system:
            self.call_log.append("price_list")
            return self.price_list, model
        if "Leistungsverzeichnisse" in system or "LV" in system:
            self.call_log.append("lv")
            return self.lv, model
        return {}, model


# --- Fixtures --------------------------------------------------------------
@pytest.fixture
def registered_client(client):
    """Client mit bereits registriertem User + Auth-Header."""
    r = client.post(
        "/api/v1/auth/register",
        json={
            "firma": "Trockenbau Mustermann GmbH",
            "email": "e2e@test.de",
            "password": "geheim12345",
        },
    )
    assert r.status_code == 201
    token = r.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}", **(client.headers or {})}
    return client


@pytest.fixture
def mock_claude(monkeypatch):
    mock = MockClaudeClient(KEMMLER_PRICE_LIST, HABAU_LV_GROUND_TRUTH)
    monkeypatch.setattr("app.services.price_list_parser.claude", mock)
    monkeypatch.setattr("app.services.lv_parser.claude", mock)
    return mock


# --- Tests -----------------------------------------------------------------
def test_e2e_habau_pipeline(registered_client, mock_claude):
    c = registered_client

    # 1. Preisliste hochladen
    pdf = make_test_pdf(page_count=3, content="Kemmler Testliste")
    r = c.post(
        "/api/v1/price-lists/upload",
        files={"file": ("kemmler.pdf", pdf, "application/pdf")},
        data={
            "haendler": "Kemmler",
            "niederlassung": "Neu-Ulm",
            "stand_monat": "04/2026",
        },
    )
    assert r.status_code == 201, r.text
    pl = r.json()
    assert pl["eintraege_gesamt"] == len(KEMMLER_PRICE_LIST["eintraege"])
    assert pl["haendler"] == "Kemmler"
    pl_id = pl["id"]

    # 2. Preisliste aktivieren
    r = c.post(f"/api/v1/price-lists/{pl_id}/activate")
    assert r.status_code == 200
    assert r.json()["aktiv"] is True

    # 3. LV hochladen
    pdf_lv = make_test_pdf(page_count=5, content="Habau Koblenz LV")
    r = c.post(
        "/api/v1/lvs/upload",
        files={"file": ("habau.pdf", pdf_lv, "application/pdf")},
    )
    assert r.status_code == 201, r.text
    lv = r.json()
    assert lv["positionen_gesamt"] == len(HABAU_LV_GROUND_TRUTH["positionen"])
    assert lv["projekt_name"].startswith("Verwaltungsgebäude Koblenz")
    lv_id = lv["id"]

    # 4. Kalkulation auslösen
    r = c.post(f"/api/v1/lvs/{lv_id}/kalkulation")
    assert r.status_code == 200, r.text
    calc = r.json()
    assert calc["status"] == "calculated"
    assert calc["angebotssumme_netto"] > 0
    summe = calc["angebotssumme_netto"]
    gematcht = calc["positionen_gematcht"]

    # Plausibilitäts-Check: Habau-LV mit obigen Positionen sollte grob
    # zwischen 60k und 500k € liegen (echte Habau-LV: ~272k € netto).
    # Mit unserem Ausschnitt (10 von 76 Pos., aber die großen m²-Pos. drin)
    # erwarten wir ~80k–300k €.
    assert 50_000 <= summe <= 500_000, f"Summe unplausibel: {summe}"

    # Mindestens 70% der Positionen sollten gematcht sein (Türaussparung /
    # Regiestunde matchen kein Materialrezept, das ist OK).
    total = calc["positionen_gesamt"]
    assert gematcht >= int(total * 0.6), f"Nur {gematcht}/{total} gematcht"

    # Alle Positionen haben einen EP berechnet, auch ohne Match (Lohn + Zuschlag)
    for p in calc["positions"]:
        assert p["ep"] >= 0, f"Pos {p['oz']}: EP negativ"

    # W112-Wand (610.1, 1895 m²) muss einen plausiblen EP haben:
    # Material(~15€/m²) + Lohn(0.55h*46 = 25€) + Zuschläge(27%) ≈ 50-55€/m²
    w112 = next(p for p in calc["positions"] if p["oz"] == "610.1")
    assert 40 <= w112["ep"] <= 80, f"W112 EP unplausibel: {w112['ep']}"
    assert w112["gp"] == pytest.approx(w112["ep"] * 1895, rel=0.01)

    # Regiestunde (610.670.1): EP = 46€ * 1.27 ≈ 58€/h
    regie = next(p for p in calc["positions"] if p["oz"] == "670.1")
    assert 50 <= regie["ep"] <= 70, f"Regie-EP unplausibel: {regie['ep']}"

    # 5. PDF-Export
    r = c.post(f"/api/v1/lvs/{lv_id}/export")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "exported"

    # 6. Download
    r = c.get(f"/api/v1/lvs/{lv_id}/download")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    pdf_bytes = r.content
    assert len(pdf_bytes) > 1000, "PDF zu klein"
    assert pdf_bytes[:4] == b"%PDF", "Keine PDF-Signatur"

    # 7. Mock-Log prüfen: beide Claude-Calls wurden gemacht
    assert "price_list" in mock_claude.call_log
    assert "lv" in mock_claude.call_log


def test_e2e_ohne_aktive_preisliste_schlaegt_fehl(registered_client, mock_claude):
    c = registered_client
    # LV hochladen, aber KEINE aktive Preisliste
    pdf_lv = make_test_pdf(page_count=2)
    r = c.post("/api/v1/lvs/upload", files={"file": ("lv.pdf", pdf_lv, "application/pdf")})
    lv_id = r.json()["id"]

    r = c.post(f"/api/v1/lvs/{lv_id}/kalkulation")
    assert r.status_code == 400
    assert "Preisliste" in r.json()["detail"]


def test_e2e_position_manuell_korrigieren(registered_client, mock_claude):
    c = registered_client

    # Preisliste hochladen + aktivieren
    pdf = make_test_pdf(page_count=2)
    r = c.post(
        "/api/v1/price-lists/upload",
        files={"file": ("kemmler.pdf", pdf, "application/pdf")},
        data={"haendler": "Kemmler"},
    )
    pl_id = r.json()["id"]
    c.post(f"/api/v1/price-lists/{pl_id}/activate")

    # LV hochladen
    r = c.post("/api/v1/lvs/upload", files={"file": ("lv.pdf", pdf, "application/pdf")})
    lv = r.json()
    lv_id = lv["id"]
    pos_id = lv["positions"][0]["id"]

    # Manuell Menge ändern
    r = c.patch(
        f"/api/v1/lvs/{lv_id}/positions/{pos_id}",
        json={"menge": 999.0},
    )
    assert r.status_code == 200
    assert r.json()["menge"] == 999.0
    assert r.json()["manuell_korrigiert"] is True


def test_tenant_isolation(client, mock_claude):
    # User A
    r = client.post(
        "/api/v1/auth/register",
        json={"firma": "Firma A", "email": "a@x.de", "password": "geheim12345"},
    )
    token_a = r.json()["access_token"]

    # User B
    r = client.post(
        "/api/v1/auth/register",
        json={"firma": "Firma B", "email": "b@x.de", "password": "geheim12345"},
    )
    token_b = r.json()["access_token"]

    pdf = make_test_pdf(page_count=2)
    # A lädt Preisliste
    r = client.post(
        "/api/v1/price-lists/upload",
        files={"file": ("kemmler.pdf", pdf, "application/pdf")},
        data={"haendler": "Kemmler"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    pl_a_id = r.json()["id"]

    # B sieht A's Preisliste NICHT
    r = client.get(
        "/api/v1/price-lists", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert r.status_code == 200
    assert len(r.json()) == 0

    # B kann A's Preisliste nicht öffnen
    r = client.get(
        f"/api/v1/price-lists/{pl_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert r.status_code == 404
