"""Regressions-Tests für die 5 MITTEL-Prioritaets-Knauf-Korrekturen vom 2026-04-20.

Hintergrund: docs/KNAUF_KORREKTUREN.md Stufe 2 (K-6 bis K-10).
"""

from __future__ import annotations

from app.services.materialrezepte import REZEPTE, resolve_rezept


# ---------------------------------------------------------------------------
# K-6: D112/D113 unterscheiden sich nach UK-Art, nicht Beplankung
# ---------------------------------------------------------------------------

def test_d112_ist_metall_uk_standard():
    r = REZEPTE["D112"]
    assert "Metall-UK" in r.beschreibung
    # Kein "1-lagig" oder "2-lagig" als definierendes Merkmal mehr
    assert "1-lagig" not in r.beschreibung.lower()


def test_d113_ist_metall_uk_niveaugleich():
    r = REZEPTE["D113"]
    assert "niveaugleich" in r.beschreibung.lower()
    # Nicht mehr "2-lagig" als definierendes Merkmal
    assert "2-lagig" not in r.beschreibung.lower()


def test_d116_existiert_als_weitspann_rezept():
    """D116.de war bisher nur Knowledge-Datenpunkt. Jetzt eigenes Rezept."""
    assert "D116" in REZEPTE
    r = REZEPTE["D116"]
    assert "weitspannend" in r.beschreibung.lower()
    # UA 50 Profil ist Kennzeichen von D116 (im Gegensatz zu D112/D113 mit nur CD60/27)
    assert any("UA" in m.dna_pattern for m in r.materialien)


# ---------------------------------------------------------------------------
# K-7: D131 ist spezifisch für Holzbalkendecke
# ---------------------------------------------------------------------------

def test_d131_hat_eigenes_rezept_mit_holzbalken_bezug():
    assert "D131" in REZEPTE
    r = REZEPTE["D131"]
    assert "holzbalken" in r.beschreibung.lower()


def test_d131_resolver_liefert_eigenes_rezept():
    """Vorher wurde D131 auf D113 gemappt. Jetzt eigenes Rezept."""
    assert resolve_rezept("D131", "", "") is REZEPTE["D131"]
    assert resolve_rezept("D131", "", "") is not REZEPTE["D113"]


# ---------------------------------------------------------------------------
# K-8: W628A präziser beschrieben (im SYSTEM_PROMPT, nicht im Rezept direkt)
# ---------------------------------------------------------------------------

def test_w628a_description_in_prompt_ist_praeziser():
    """W628A.de ist freispannend bis 2m Schachtbreite. Die alte Beschreibung
    ('erhöhte Wandhöhe bis 8.9m') war ungenau."""
    from app.services.lv_parser import SYSTEM_PROMPT
    # Neue Beschreibung muss 'freispannend' und '2m' enthalten
    assert "freispannend" in SYSTEM_PROMPT.lower() or "FREISPANNEND" in SYSTEM_PROMPT
    assert "2m" in SYSTEM_PROMPT or "2 m" in SYSTEM_PROMPT.replace("ca. ", "")


# ---------------------------------------------------------------------------
# K-9: W116 verlascht (nicht entkoppelt)
# ---------------------------------------------------------------------------

def test_w116_ist_verlascht_nicht_entkoppelt():
    r = REZEPTE["W116"]
    assert "verlascht" in r.beschreibung.lower()
    assert "entkoppelt" not in r.beschreibung.lower()


def test_w115_und_w116_haben_unterschiedliche_beschreibungen():
    """W115 = entkoppelt (Schallschutz), W116 = verlascht (Installation).
    Beide sind Doppelständer, aber mit unterschiedlichem Zweck."""
    w115_b = REZEPTE["W115"].beschreibung.lower()
    w116_b = REZEPTE["W116"].beschreibung.lower()
    assert w115_b != w116_b


# ---------------------------------------------------------------------------
# K-10: W113 dreilagig (eigenes Rezept)
# ---------------------------------------------------------------------------

def test_w113_existiert_als_eigenes_rezept():
    """W113.de war vorher im resolve_rezept auf W112 gemappt. Jetzt eigenes
    Rezept mit dreilagiger Beplankung."""
    assert "W113" in REZEPTE


def test_w113_hat_mehr_gkb_als_w112():
    gkb_w112 = next(
        (m.menge_pro_einheit for m in REZEPTE["W112"].materialien if "GKB" in m.dna_pattern),
        0,
    )
    gkb_w113 = next(
        (m.menge_pro_einheit for m in REZEPTE["W113"].materialien if "GKB" in m.dna_pattern),
        0,
    )
    assert gkb_w113 > gkb_w112, (
        f"W113 (3-lagig, {gkb_w113} m²/m²) muss mehr GKB haben als W112 (2-lagig, {gkb_w112})"
    )


def test_w113_resolver_liefert_eigenes_rezept():
    """resolve_rezept('W113', ...) darf nicht mehr auf W112 zurueckfallen.
    Wenn eine W11-Nummer EXPLIZIT gefordert ist, respektieren wir sie — auch
    bei F90. Der W118-F90-Fallback greift nur fuer undefinierte W11-Codes.
    """
    assert resolve_rezept("W113", "", "") is REZEPTE["W113"]
    assert resolve_rezept("W113", "F90", "") is REZEPTE["W113"]


def test_w11_undefinierte_nummer_mit_f90_wird_w118():
    """Nur bei nicht-explizit gelistetem W11-Code (z.B. W114) greift der
    F90-W118-Fallback."""
    assert resolve_rezept("W114", "F90", "GKF") is REZEPTE["W118"]


def test_w11_andere_nummern_fallen_auf_w112_zurueck():
    """W114, W117 etc. — nicht definierte W11-Codes — fallen auf W112 zurück."""
    assert resolve_rezept("W114", "", "") is REZEPTE["W112"]
    assert resolve_rezept("W117", "", "") is REZEPTE["W112"]
