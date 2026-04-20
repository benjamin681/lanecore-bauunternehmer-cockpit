"""Regressions-Tests für Etappe 3: Umbenennung auf offizielle Knauf-Nomenklatur.

Hintergrund: docs/KNAUF_KORREKTUREN.md K-11, K-12, K-13.
Variante 1: Offizielle Namen (W628A.de, W628B.de, W629.de, W635.de) sind jetzt
primär. Die alten internen Namen (W625S, W626S, W631S, W632) werden via
resolve_rezept-Aliase weiterhin akzeptiert (Backward-Compatibility).
"""

from __future__ import annotations

from app.services.materialrezepte import REZEPTE, resolve_rezept


# ---------------------------------------------------------------------------
# K-12: Neue offizielle Namen sind primär im REZEPTE-Dict
# ---------------------------------------------------------------------------

def test_offizielle_schachtwand_namen_sind_primary_keys():
    """Die neuen offiziellen Knauf-Codes sind jetzt primaer im REZEPTE-Dict."""
    for offizieller_name in ("W628A", "W628B", "W629", "W635"):
        assert offizieller_name in REZEPTE, (
            f"{offizieller_name} muss als primaerer Rezept-Key existieren"
        )


def test_alte_interne_namen_sind_nicht_mehr_primary():
    """Die alten S-Suffix-Namen sind KEINE primaeren Keys mehr."""
    for alter_name in ("W625S", "W626S", "W631S", "W632"):
        assert alter_name not in REZEPTE, (
            f"{alter_name} darf kein primaerer Rezept-Key mehr sein - "
            "nur als Alias im resolve_rezept."
        )


# ---------------------------------------------------------------------------
# K-12: Backward-Compatibility über Aliase
# ---------------------------------------------------------------------------

def test_w625s_mapt_auf_w628a():
    """Alte LVs mit 'W625S' sollen weiter funktionieren."""
    assert resolve_rezept("W625S", "", "") is REZEPTE["W628A"]


def test_w626s_mapt_auf_w628b():
    assert resolve_rezept("W626S", "", "") is REZEPTE["W628B"]


def test_w631s_mapt_auf_w629():
    assert resolve_rezept("W631S", "", "") is REZEPTE["W629"]


def test_w632_mapt_auf_w635():
    assert resolve_rezept("W632", "", "") is REZEPTE["W635"]


# ---------------------------------------------------------------------------
# K-12: Offizielle Knauf-.de-Suffixe greifen auch
# ---------------------------------------------------------------------------

def test_offizielle_de_suffixe_werden_erkannt():
    """LV-Text mit z.B. 'W628A.de' muss direkt auf W628A-Rezept auflösen."""
    assert resolve_rezept("W628A.de", "", "") is REZEPTE["W628A"]
    assert resolve_rezept("W628B.de", "", "") is REZEPTE["W628B"]
    assert resolve_rezept("W629.de", "", "") is REZEPTE["W629"]
    assert resolve_rezept("W635.de", "", "") is REZEPTE["W635"]


# ---------------------------------------------------------------------------
# K-12: Default 'SCHACHTWAND' zeigt auf W628A (nicht mehr W625S)
# ---------------------------------------------------------------------------

def test_default_schachtwand_zeigt_auf_w628a():
    assert resolve_rezept("Schachtwand", "", "") is REZEPTE["W628A"]
    assert resolve_rezept("SCHACHTWAND", "", "") is REZEPTE["W628A"]


# ---------------------------------------------------------------------------
# K-12: Neue Rezepte haben unterschiedliche Materialmengen
# (jedes System unterscheidet sich fachlich, nicht alle gleich kopiert)
# ---------------------------------------------------------------------------

def test_w628a_und_w628b_haben_unterschiedliche_profile():
    """W628A = freispannend (kein Mittel-Profil), W628B = CW-Einfachstaender."""
    # Fachliche Unterschiede sollten sich in Profil-Patterns zeigen
    w628a_cw = next(
        (m.dna_pattern for m in REZEPTE["W628A"].materialien if "CW" in m.dna_pattern),
        None,
    )
    w628b_cw = next(
        (m.dna_pattern for m in REZEPTE["W628B"].materialien if "CW" in m.dna_pattern),
        None,
    )
    # W628A hat CW75, W628B hat CW100 (wegen groesserer Spannweite)
    assert w628a_cw != w628b_cw, (
        f"W628A ({w628a_cw}) und W628B ({w628b_cw}) muessen unterschiedliche "
        "Profile haben (fachliche Differenz)"
    )


def test_w629_hat_doppelstaender():
    """W629 = CW-Doppelstaender. Erkennbar an hoeherer Profil-Menge pro m²."""
    w629_cw = next(
        (m.menge_pro_einheit for m in REZEPTE["W629"].materialien if "CW" in m.dna_pattern),
        0,
    )
    w628a_cw = next(
        (m.menge_pro_einheit for m in REZEPTE["W628A"].materialien if "CW" in m.dna_pattern),
        0,
    )
    assert w629_cw > w628a_cw, (
        "W629 (Doppelstaender, ~3.6 lfm/m²) muss mehr CW-Profil haben als "
        f"W628A (Einfach, ~1.8 lfm/m²). Actual: W629={w629_cw}, W628A={w628a_cw}"
    )


# ---------------------------------------------------------------------------
# Prefix-Heuristik: W62* default auf W625 (Vorsatzschale) oder W628A (Schacht)
# je nach Nummer
# ---------------------------------------------------------------------------

def test_w62_prefix_vorsatzschale_bei_niedrigen_nummern():
    """W621, W624 etc. (nicht definiert) fallen auf W625 (Vorsatzschale) zurueck."""
    assert resolve_rezept("W621", "", "") is REZEPTE["W625"]
    assert resolve_rezept("W624", "", "") is REZEPTE["W625"]


def test_w62_prefix_schachtwand_bei_W628():
    """W628 (ohne A/B) → W628A als Default."""
    assert resolve_rezept("W628", "", "") is REZEPTE["W628A"]
