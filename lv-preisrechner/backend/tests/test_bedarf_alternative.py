"""Tests für Bedarfs- und Alternativpositionen.

Kontext: Bedarfs- und Alternativpositionen dürfen NICHT in die Angebotssumme
einfließen (sie sind im LV als "Nur Einh.-Pr." markiert — der Bieter gibt nur
den EP an, der GP wird nicht in die Summe einbezogen).

Position-Model hat dafür zwei Flags (seit Commit 4c3d7f4):
- is_bedarf
- is_alternative

Parser setzt die Flags automatisch via detect_optional_flags() bei bekannten
Textmarkern. Kalkulation schließt Positionen mit einem der beiden Flags aus
der Angebotssumme aus und weist sie separat aus.
"""

from __future__ import annotations

from app.models.lv import LV
from app.models.position import Position
from app.models.price_entry import PriceEntry
from app.models.price_list import PriceList
from app.models.tenant import Tenant
from app.models.user import User
from app.services.auth_service import hash_password
from app.services.kalkulation import kalkuliere_lv
from app.services.lv_parser import detect_optional_flags


# ---------------------------------------------------------------------------
# detect_optional_flags — reine Marker-Erkennung ohne DB
# ---------------------------------------------------------------------------

def test_detect_bedarf_marker_via_sternchen():
    """'*** Bedarfsposition ohne GB' im Kurztext → is_bedarf=True."""
    is_bedarf, is_alt = detect_optional_flags(
        kurztext="*** Bedarfsposition ohne GB. Wandabsorber 800 mm x 800 mm.",
        titel="",
        langtext="",
    )
    assert is_bedarf is True
    assert is_alt is False


def test_detect_alternative_marker():
    """'Alternativprodukt:' im Kurztext → is_alternative=True."""
    is_bedarf, is_alt = detect_optional_flags(
        kurztext="Alternativprodukt: Wandabsorber 1200 mm x 1100 mm. Günstigere Alternative.",
        titel="",
        langtext="",
    )
    assert is_bedarf is False
    assert is_alt is True


def test_detect_kombinierte_bedarf_und_alternative():
    """Bedarfs-Alternative: beide Flags True gleichzeitig."""
    is_bedarf, is_alt = detect_optional_flags(
        kurztext="*** Bedarfsposition ohne GB. Alternativprodukt: Deckensegel 1,20 x 4,00 m.",
        titel="",
        langtext="",
    )
    assert is_bedarf is True
    assert is_alt is True


def test_detect_nur_einheitspreis_in_einheit():
    """LV-Spezialfall: 'Nur Einh.-Pr.' wird manchmal in der Mengen-Spalte/Einheit geparst."""
    is_bedarf, _ = detect_optional_flags(
        kurztext="Normale Position ohne Marker",
        titel="",
        langtext="",
        einheit="Nur Einh.-Pr.",
    )
    assert is_bedarf is True


def test_detect_reguläre_position_keine_flags():
    """Normale Position ohne Marker → beide False."""
    is_bedarf, is_alt = detect_optional_flags(
        kurztext="GK - Trennwand W112, d=125mm, F0, Rw=55dB, Q2. 1.895,00 m².",
        titel="Innenwände Trockenbau",
        langtext="",
    )
    assert is_bedarf is False
    assert is_alt is False


# ---------------------------------------------------------------------------
# Integration: Kalkulation respektiert die Flags
# Nutzt das bestehende `client`-Fixture (conftest.py) um eine frische DB
# inklusive Tenant/PriceList/LV aufzusetzen, lädt die Daten aber direkt
# via Session (nicht via HTTP-Upload).
# ---------------------------------------------------------------------------

def _setup_tenant_with_price(session):
    """Legt Tenant + User + aktive Preisliste mit einem GKB-Eintrag an."""
    tenant = Tenant(name="TestBetrieb")
    session.add(tenant)
    session.flush()
    user = User(
        email="bedarf@test.local",
        tenant_id=tenant.id,
        password_hash=hash_password("test"),
    )
    session.add(user)
    pl = PriceList(
        tenant_id=tenant.id,
        haendler="Kemmler",
        niederlassung="Ulm",
        stand_monat="04/2026",
        original_dateiname="testpl.pdf",
        status="ready",
        aktiv=True,
    )
    session.add(pl)
    session.flush()
    # Ein Mindest-Preiseintrag, damit die Kalkulation einen Wert findet.
    pe = PriceEntry(
        price_list_id=pl.id,
        dna="Knauf|Gipskarton|GKB|12.5mm|",
        hersteller="Knauf",
        kategorie="Gipskarton",
        produktname="GKB",
        abmessungen="12.5mm",
        variante="",
        preis=3.50,
        einheit="m²",
        preis_pro_basis=3.50,
        basis_einheit="m²",
        konfidenz=1.0,
    )
    session.add(pe)
    session.flush()
    return tenant, pl


def _add_position(session, lv, *, oz: str, menge: float, is_bedarf=False, is_alt=False):
    # Rezept 'Zulage' hat keine Pflicht-Materialien -> EP aus Lohn+Zuschlaegen > 0,
    # unabhaengig von der Preisliste. Damit testen wir sauber die Summen-Logik.
    p = Position(
        lv_id=lv.id,
        reihenfolge=0,
        oz=oz,
        kurztext=f"Zulage Test-Position {oz}",
        menge=menge,
        einheit="Stk",
        erkanntes_system="Zulage",
        is_bedarf=is_bedarf,
        is_alternative=is_alt,
    )
    session.add(p)
    return p


def test_angebotssumme_excludes_bedarf_and_alternative(client):
    """Bindende Angebotssumme enthält weder Bedarfs- noch Alternativpositionen;
    beide werden separat ausgewiesen."""
    from app.core import database

    session = database.SessionLocal()
    try:
        tenant, pl = _setup_tenant_with_price(session)

        lv = LV(
            tenant_id=tenant.id,
            original_dateiname="test.pdf",
            status="review_needed",
        )
        session.add(lv)
        session.flush()

        # 2 bindende Positionen + 1 Bedarf + 1 Alternative + 1 kombiniert
        _add_position(session, lv, oz="1.1", menge=100.0)
        _add_position(session, lv, oz="1.2", menge=50.0)
        _add_position(session, lv, oz="2.1", menge=10.0, is_bedarf=True)
        _add_position(session, lv, oz="3.1", menge=20.0, is_alt=True)
        _add_position(session, lv, oz="4.1", menge=5.0, is_bedarf=True, is_alt=True)
        session.commit()

        lv_result = kalkuliere_lv(session, lv.id, tenant.id)

        # Bindende Summe: nur die 2 regulären Positionen (150 m²)
        # Optional-Summen separat
        # Gesamt: alle 5 Positionen (185 m²)
        assert lv_result.angebotssumme_netto > 0
        assert lv_result.bedarfspositionen_summe > 0
        assert lv_result.alternativpositionen_summe > 0
        assert (
            lv_result.gesamtsumme_inklusive_optional
            > lv_result.angebotssumme_netto
        )
        # Summen-Konsistenz: bindend + bedarf + alternative == gesamt (bei is_bedarf UND
        # is_alternative zählt die Position als Bedarf — wird also nur in der Bedarf-
        # Summe gezählt, nicht doppelt)
        assert (
            round(
                lv_result.angebotssumme_netto
                + lv_result.bedarfspositionen_summe
                + lv_result.alternativpositionen_summe,
                2,
            )
            == lv_result.gesamtsumme_inklusive_optional
        )
        # Bindende Summe entspricht nur 2 bindenden Positionen
        # (Mengen 100 + 50 = 150 m² × EP je Position)
        # Sanity: angebotssumme_netto < gesamt
        assert lv_result.angebotssumme_netto < lv_result.gesamtsumme_inklusive_optional
    finally:
        session.close()


def test_bedarf_and_alternative_still_in_output(client):
    """Bedarfs- und Alternativpositionen bleiben in lv.positions erhalten
    (werden nur aus der bindenden Summe ausgeschlossen, nicht aus dem Output)."""
    from app.core import database

    session = database.SessionLocal()
    try:
        tenant, _ = _setup_tenant_with_price(session)
        lv = LV(tenant_id=tenant.id, original_dateiname="test.pdf")
        session.add(lv)
        session.flush()

        _add_position(session, lv, oz="1.1", menge=100.0)
        _add_position(session, lv, oz="2.1", menge=10.0, is_bedarf=True)
        _add_position(session, lv, oz="3.1", menge=20.0, is_alt=True)
        session.commit()

        lv_result = kalkuliere_lv(session, lv.id, tenant.id)
        # Alle 3 Positionen bleiben im Output
        assert len(lv_result.positions) == 3
        # Jede Position hat einen berechneten EP (nicht unterdrückt)
        for p in lv_result.positions:
            assert p.ep >= 0
            assert p.gp >= 0
    finally:
        session.close()
