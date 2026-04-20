"""Golden-Regression-Test für das Stuttgart-Omega-Sorg-LV.

WAS WIRD GETESTET
-----------------
Der Stuttgart-Omega-Sorg-LV (Peter Gross Bau, Trockenbauwände + Decken,
48 Seiten, ~100 Positionen) dient als "Realwelt-Stresstest" für den
LV-Parser. Er enthält:

- Mehrstufige Hierarchie (OZ wie "1.9.1.1.10" bis "1.9.2.3.10")
- Exotische Systeme (Streckmetalldecke, Deckensegel, Wandabsorber)
- Schachtwände W628A, W630, W631
- Brandwand W133 (zweischalig)
- Bedarfspositionen (LV-Marker: "*** Bedarfsposition ohne GB")
- Alternativpositionen ("Alternativprodukt")

Dieser Test wacht über Regression der Klassifizierungs-Qualität, seit
die SYSTEM_PROMPT-Taxonomie und die Rezept-Liste erweitert wurden
(Commits 426f178, 415cbcf, 2026-04-20).

WARUM
-----
Komplexe LVs wurden vor der Taxonomie-Erweiterung häufig im Fehl-
Bucket "Verkleidung" abgelegt (23 von 102 Positionen). Nach dem Fix
greifen die präziseren Kategorien (Streckmetalldecke, Deckensegel,
Wandabsorber, W628A, W630, W133, Leibungsbekleidung, GK_Schwert etc.)
und der Fehl-Bucket schrumpfte auf 1.

Der Test soll schleichende Regression früh erkennen — wenn z.B. ein
späterer Prompt-Refactor die Klassifikation wieder verschlechtert
oder Parser-Updates Positionen verloren gehen.

WIE SNAPSHOT-UPDATE
-------------------
Der Test arbeitet gegen einen Roh-Parse-Snapshot
(`snapshots/stuttgart_raw_parse_v2.json`), nicht gegen einen Live-Lauf,
damit er schnell, deterministisch und API-frei läuft.

Zum Neu-Erzeugen des Snapshots (ca. 7 Minuten, ~$0.33 Claude-Credits):

    cd lv-preisrechner/backend
    source .venv/bin/activate
    python -m scripts.stuttgart_diagnostic stuttgart_raw_parse_v2.json

Das Script liegt lokal (nicht committet) — bei Bedarf aus der
Git-History wiederherstellen oder aus einem früheren Worktree kopieren.

MARKIERUNG
----------
Dieser Test ist als `@pytest.mark.integration` markiert. Bei lokalen
Pre-Commit-Runs und CI-PR-Runs wird er regulär mit ausgeführt (kostet
nur Millisekunden weil Snapshot-basiert). Bei Bedarf ausschließen:

    pytest -m "not integration"

PARSER-VARIANZ & DRIFT-WARNUNG
------------------------------
Claude Sonnet 4.6 gruppiert auf Seiten-Batch-Grenzen gelegentlich
benachbarte LV-Zeilen unterschiedlich (± 5-10 Positionen). Deshalb
die 90-Untergrenze in Assertion 1 (statt strikt 95). Zusätzlich gibt
der Test eine Drift-Warnung aus, wenn die aktuelle Positions-Anzahl
um mehr als 10 vom Snapshot-Referenzwert (93) abweicht — das hilft,
schleichende Verschlechterung früh zu erkennen, ohne den Test sofort
rot zu drehen.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

SNAPSHOT_PATH = (
    Path(__file__).parent / "snapshots" / "stuttgart_raw_parse_v3.json"
)
EXPECTED_POSITIONS_COUNT = 93  # laut User-Vorgabe unveraendert trotz v3-Snapshot mit 103
DRIFT_THRESHOLD = 10


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def snapshot() -> dict:
    if not SNAPSHOT_PATH.exists():
        pytest.skip(
            f"Snapshot fehlt: {SNAPSHOT_PATH}. "
            "Zum Erzeugen: "
            "`cd lv-preisrechner/backend && "
            "python -m scripts.stuttgart_diagnostic stuttgart_raw_parse_v2.json`"
        )
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def summary(snapshot) -> dict:
    return snapshot["summary"]


@pytest.fixture(scope="module")
def positions(snapshot) -> list[dict]:
    return snapshot["positionen"]


# ---------------------------------------------------------------------------
# Assertion 1: Mindestanzahl Positionen + Drift-Warnung
# ---------------------------------------------------------------------------
def test_1_positions_count(summary, capsys):
    count = summary["positionen_total"]
    assert (
        count >= 90
    ), f"Nur {count} Positionen erkannt (Untergrenze 90). Möglich: Regression im Parser."

    if abs(count - EXPECTED_POSITIONS_COUNT) > DRIFT_THRESHOLD:
        print(
            f"\n⚠️ Drift-Warnung: Positions-Anzahl weicht signifikant vom "
            f"Snapshot ab. "
            f"Aktuell: {count}, Snapshot-Referenz: {EXPECTED_POSITIONS_COUNT}, "
            f"Diff: {count - EXPECTED_POSITIONS_COUNT:+}. "
            "Prüfen ob Parser-Drift oder echte Regression."
        )


# ---------------------------------------------------------------------------
# Assertion 2: Bedarfspositionen
# ---------------------------------------------------------------------------
def test_2_bedarfspositionen_count_in_range(summary):
    count = summary["bedarfspositionen_count"]
    assert (
        4 <= count <= 10
    ), f"Bedarfspositionen: {count} (erwartet 4-10, Stuttgart-LV hat 6)"


# ---------------------------------------------------------------------------
# Assertion 3: Alternativpositionen
# ---------------------------------------------------------------------------
def test_3_alternativpositionen_count_in_range(summary):
    count = summary["alternativpositionen_count"]
    assert (
        3 <= count <= 10
    ), f"Alternativpositionen: {count} (erwartet 3-10, Stuttgart-LV hat 5)"


# ---------------------------------------------------------------------------
# Assertion 4: Knauf-Systeme (W112, W628/W628A, W630, W133) erkannt
# ---------------------------------------------------------------------------
def test_4_knauf_systems_detected(summary):
    systeme = summary["erkannte_systeme"]

    assert systeme.get("W112", 0) >= 1, "W112 nicht erkannt"

    w628_hits = systeme.get("W628", 0) + systeme.get("W628A", 0)
    assert w628_hits >= 1, (
        f"Weder W628 noch W628A erkannt. Gefunden: "
        f"W628={systeme.get('W628', 0)}, W628A={systeme.get('W628A', 0)}"
    )

    assert systeme.get("W630", 0) >= 1, "W630 nicht erkannt"
    assert systeme.get("W133", 0) >= 1, "W133 nicht erkannt"


# ---------------------------------------------------------------------------
# Assertion 5: Sonderkategorien (Streckmetall, Deckensegel, Wandabsorber)
# ---------------------------------------------------------------------------
def test_5_special_categories_detected(summary):
    systeme = summary["erkannte_systeme"]
    for key in ("Streckmetalldecke", "Deckensegel", "Wandabsorber"):
        assert systeme.get(key, 0) >= 1, f"Kategorie '{key}' nicht erkannt"


# ---------------------------------------------------------------------------
# Assertion 6: Mengeneinheiten m², lfm, Stk präsent
# ---------------------------------------------------------------------------
def test_6_units_present(summary):
    einheiten = summary["einheiten"]
    for u in ("m²", "lfm", "Stk"):
        assert einheiten.get(u, 0) > 0, f"Einheit '{u}' fehlt im Parse-Ergebnis"


# ---------------------------------------------------------------------------
# Assertion 7: Verkleidung-Bucket nicht zu breit (<= 10)
# ---------------------------------------------------------------------------
def test_7_verkleidung_bucket_not_too_broad(summary):
    count = summary["erkannte_systeme"].get("Verkleidung", 0)
    assert count <= 10, (
        f"Verkleidung-Bucket zu breit: {count} Treffer (Obergrenze 10). "
        f"Vor Taxonomie-Erweiterung waren es 23. Regression?"
    )


# ---------------------------------------------------------------------------
# Assertion 8: Bedarfspositionen dürfen NICHT in Gesamtsumme einfließen
# ---------------------------------------------------------------------------
def test_8_bedarfspositionen_not_in_total_sum(positions):
    """KRITISCH: Bedarfspositionen werden im echten LV mit 'Nur Einh.-Pr.'
    markiert — der Bieter nennt nur den EP, der GP fließt NICHT in die
    Angebotssumme ein.

    Erwartung nach Fix:
    - Jede Bedarfsposition wird klar markiert (z.B. via Flag `is_bedarf=True`
      oder `bedarfsposition=True`) ODER hat menge=0.
    - Die Kalkulation und PDF-Ausgabe ignorieren solche Positionen in der
      Summenbildung.

    Aktueller Zustand vor Aufgabe 3 (2026-04-20): Position-Model hat kein
    is_bedarf-Flag und keine gesonderte Behandlung. Bedarfspositionen haben
    Menge > 0 (typisch "1,000 Stk"). Dieser Test ist absichtlich so
    geschrieben, dass er aktuell FEHLSCHLÄGT und damit den Bug bestätigt.
    """
    bedarf = []
    for p in positions:
        kt = (p.get("kurztext") or "")
        tt = (p.get("titel") or "")
        combined = (kt + " " + tt).lower()
        if "bedarfsposition" in combined or "***" in (kt + tt):
            bedarf.append(p)

    assert (
        len(bedarf) >= 4
    ), f"Stuttgart-LV hat ~6 Bedarfspositionen, gefunden: {len(bedarf)}"

    # Der eigentliche Bug-Check:
    not_flagged = []
    for p in bedarf:
        is_flagged = (
            p.get("is_bedarf") is True
            or p.get("bedarfsposition") is True
            or (p.get("menge") or 0) == 0
        )
        if not is_flagged:
            not_flagged.append(p.get("oz", "?"))

    assert not not_flagged, (
        f"BUG: {len(not_flagged)} Bedarfspositionen sind nicht als solche "
        f"markiert und haben menge>0 — sie würden in Summen-Kalkulationen "
        f"einfließen. Erste OZs: {not_flagged[:5]}. "
        "Erwartet: is_bedarf=True oder menge=0 pro Bedarfsposition."
    )


# ---------------------------------------------------------------------------
# Zusatz-Assertion: Alternativpositionen analog behandelt
# ---------------------------------------------------------------------------
def test_9_alternativpositionen_have_flag(positions):
    """Positionen mit 'Alternativprodukt'-Marker sollen is_alternative=True
    haben."""
    alt_markierte = [
        p for p in positions
        if "alternativprodukt" in (p.get("kurztext") or "").lower()
    ]
    assert len(alt_markierte) >= 3, (
        f"Stuttgart-LV hat ~5 Alternativpositionen, gefunden: {len(alt_markierte)}"
    )
    not_flagged = [
        p.get("oz", "?") for p in alt_markierte if not p.get("is_alternative")
    ]
    assert not not_flagged, (
        f"{len(not_flagged)} Alternativpositionen ohne is_alternative-Flag: "
        f"{not_flagged[:5]}"
    )
