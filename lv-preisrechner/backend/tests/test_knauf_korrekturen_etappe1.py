"""Regressions-Tests für die 5 GRAVIERENDEN Knauf-Korrekturen vom 2026-04-20.

Hintergrund: docs/KNAUF_KORREKTUREN.md Stufe 1 (K-1 bis K-5).
Die Rezepte und SYSTEM_PROMPT-Definitionen wurden gegen die offiziellen
Knauf-Quellen korrigiert. Diese Tests sichern ab, dass die Korrekturen
nicht versehentlich rückgängig gemacht werden.
"""

from __future__ import annotations

from app.services.materialrezepte import REZEPTE, resolve_rezept


# ---------------------------------------------------------------------------
# K-1: W135 ist Brandwand mit Stahlblech, nicht Installationswand
# ---------------------------------------------------------------------------

def test_w135_ist_brandwand_mit_stahlblech():
    """W135.de ist offiziell eine Sonderbauwand (Brandwand) mit Stahlblech.
    Dieser Test schlägt fehl wenn jemand W135 wieder als 'Installationswand'
    definiert oder das Stahlblech als optional markiert.
    """
    r = REZEPTE["W135"]
    assert "Brandwand" in r.beschreibung or "brandwand" in r.beschreibung.lower(), (
        f"W135-Beschreibung muss 'Brandwand' enthalten, aktuell: {r.beschreibung}"
    )
    stahlblech = [m for m in r.materialien if "Stahlblech" in m.dna_pattern]
    assert stahlblech, "W135 muss Stahlblech-Material enthalten (F90-A+mB)"
    assert not stahlblech[0].optional, "Stahlblech bei W135 ist Pflicht, nicht optional"


def test_w135_stahlblech_alias_zeigt_auf_w135():
    """Der alte Code 'W135_Stahlblech' existiert nicht mehr als eigenes Rezept.
    Backward-Compat via Alias auf W135.
    """
    assert "W135_Stahlblech" not in REZEPTE, (
        "W135_Stahlblech wurde entfernt — W135 ist selbst schon die Stahlblech-Variante"
    )
    # Alias greift
    assert resolve_rezept("W135_Stahlblech", "", "") is REZEPTE["W135"]
    assert resolve_rezept("Stahlblecheinlage", "", "") is REZEPTE["W135"]


# ---------------------------------------------------------------------------
# K-2: W623 und W625 Vertauschung
# ---------------------------------------------------------------------------

def test_w623_ist_direkt_befestigt_mit_cd_profil():
    """W623.de = direkt befestigt mit CD 60/27. Das CD-Profil ist das
    Unterscheidungsmerkmal.
    """
    r = REZEPTE["W623"]
    assert "direkt" in r.beschreibung.lower()
    # Rezept muss CD60/27 als Profil fordern (nicht CW)
    cd_profile = [m for m in r.materialien if "CD60" in m.dna_pattern]
    assert cd_profile, f"W623 muss CD60-Profil fordern, aktuelle Materialien: {[m.dna_pattern for m in r.materialien]}"


def test_w625_ist_freistehend_mit_cw_profil():
    """W625.de = freistehend mit CW-Profil (einlagig beplankt)."""
    r = REZEPTE["W625"]
    assert "freistehend" in r.beschreibung.lower()
    cw_profile = [m for m in r.materialien if "CW50" in m.dna_pattern or "CW75" in m.dna_pattern]
    assert cw_profile, f"W625 muss CW-Profil fordern, aktuelle Materialien: {[m.dna_pattern for m in r.materialien]}"


def test_w623_und_w625_haben_unterschiedliche_profile():
    """Sanity-Check: nachdem sie getauscht wurden, dürfen sie NICHT beide
    dasselbe Profil-Pattern haben.
    """
    w623_profile = set(m.dna_pattern for m in REZEPTE["W623"].materialien if "Profile" in m.dna_pattern)
    w625_profile = set(m.dna_pattern for m in REZEPTE["W625"].materialien if "Profile" in m.dna_pattern)
    assert w623_profile != w625_profile, "W623 und W625 müssen unterschiedliche Profile haben (Direkt- vs. Freistehend)"


# ---------------------------------------------------------------------------
# K-4: W131 mit Stahlblech
# ---------------------------------------------------------------------------

def test_w131_hat_stahlblech_als_pflicht():
    r = REZEPTE["W131"]
    stahlblech = [m for m in r.materialien if "Stahlblech" in m.dna_pattern]
    assert stahlblech, "W131 muss Stahlblech enthalten (F90-A+mB)"
    assert not stahlblech[0].optional


# ---------------------------------------------------------------------------
# K-5: W133 ist Einfachständer dreilagig (nicht Doppelständer)
# ---------------------------------------------------------------------------

def test_w133_existiert_als_eigenes_rezept():
    """Vorher wurde W133 auf W131 gemappt - das lieferte 2-lagig + Stahlblech.
    W133 ist aber 3-lagig + Stahlblech, braucht eigenes Rezept mit mehr GKF."""
    assert "W133" in REZEPTE


def test_w133_hat_mehr_gkf_als_w131():
    """W133 = 3-lagig, W131 = 2-lagig. Materialmenge muss unterschiedlich sein."""
    gkf_w131 = next(
        (m.menge_pro_einheit for m in REZEPTE["W131"].materialien if "GKF" in m.dna_pattern),
        0,
    )
    gkf_w133 = next(
        (m.menge_pro_einheit for m in REZEPTE["W133"].materialien if "GKF" in m.dna_pattern),
        0,
    )
    assert gkf_w133 > gkf_w131, (
        f"W133 (3-lagig, {gkf_w133} m²/m²) muss mehr GKF als W131 (2-lagig, {gkf_w131} m²/m²) haben"
    )


def test_w133_hat_stahlblech():
    r = REZEPTE["W133"]
    assert any("Stahlblech" in m.dna_pattern for m in r.materialien)


def test_w133_resolver_mapt_nicht_mehr_auf_w131():
    """resolve_rezept('W133', ...) muss jetzt das echte W133-Rezept liefern,
    nicht länger W131."""
    assert resolve_rezept("W133", "F90", "") is REZEPTE["W133"]
    assert resolve_rezept("W133", "F90", "") is not REZEPTE["W131"]


# ---------------------------------------------------------------------------
# Backward-Compatibility: alte Brandwand-Aliase greifen noch
# ---------------------------------------------------------------------------

def test_brandwand_aliase_backward_compatible():
    assert resolve_rezept("BRANDWAND", "", "") is REZEPTE["W131"]
    assert resolve_rezept("Einschalige Brandwand", "", "") is REZEPTE["W131"]
    assert resolve_rezept("Zweischalige Brandwand", "", "") is REZEPTE["W133"]


def test_vorsatzschale_default_ist_freistehend():
    """Generisches Keyword 'Vorsatzschale' ohne Präzisierung → W625 (freistehend,
    laut offizieller Knauf-Semantik). Vorher war Default W623."""
    assert resolve_rezept("Vorsatzschale", "", "") is REZEPTE["W625"]
    assert resolve_rezept("Vorsatzschale direkt befestigt", "", "") is REZEPTE["W623"]
