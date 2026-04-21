"""B+4.2.6 Golden Tests — CW/UW-Profile-Matcher.

Diese Tests reproduzieren den dokumentierten Bug (siehe
`docs/b426_baseline.md`): DNA-Pattern wie ``|Profile|CW75|`` liefern im
`material_normalizer` das Token ``cw75``. Der echte Kemmler-String
``CW-Profil 100x50x0,6 mm BL=2600 mm`` zerfaellt aber in die Tokens
``{cw, profil, 100, 50, 0.6}`` — die Schnittmenge ist leer, der
Score bleibt bei 0 %, und `price_lookup` faellt auf Stage 4
(`estimated`) zurueck.

Das Scoring passiert in :func:`score_query_against_candidate`, also
testen wir genau diese Funktion. Der `material_name`, der in
`lookup_price` ankommt, wird heute aus dem Rezept-Pattern ohne Leer-
zeichen zusammengebaut (``"CW75"``, ``"CW100"``) — so reproduzieren
wir den aktuellen Produktions-Input.

Status-Uebersicht:
- Test 1, 2, 6: **rot** auf aktuellem Code (reproduzieren den Bug).
- Test 3, 4, 5: **green guards** — pruefen, dass ein Fix nicht in
  die andere Richtung uebersteuert und False-Positives reinlaesst.
"""

from __future__ import annotations

from app.services.material_normalizer import score_query_against_candidate


FUZZY_THRESHOLD = 85.0  # in Prozent, entspricht price_lookup.FUZZY_MATCH_THRESHOLD*100


# --------------------------------------------------------------------------- #
# Reale und synthetische Fixture-Strings
# --------------------------------------------------------------------------- #
KEMMLER_CW_100 = "CW-Profil 100x50x0,6 mm BL=2600 mm 8 St./Bd."
"""Echter Kemmler-Eintrag (04/2026). Einziger echter CW-Profil-Eintrag."""

SYNTH_CW_75 = "CW-Profil 75x50x0,6 mm BL=2600 mm"
"""Synthetischer 75-mm-Eintrag in Kemmler-Stilistik."""

SYNTH_UW_75 = "UW-Profil 75x40x0,6 mm BL=2600 mm"
"""Synthetischer UW-Profil-Eintrag."""

KEMMLER_TP_75 = (
    "TP75 Türpfosten-Steckwinkel f. 75 mm CW/UA-Prof mit Kabeldurchlas"
)
"""Realer Kemmler-Türpfosten — enthaelt 'CW' und '75' im Text, soll trotzdem
NICHT als CW-75-Profil gelten."""

KEMMLER_UA_50 = "Anschlusswinkel f. UA-Profil 50 mm verzinkt"
"""Synthetischer UA-Anschlusswinkel (Kemmler-Typ-nahes Wording)."""


def _best(query: str, candidates: list[str]) -> tuple[str | None, float]:
    """Return (winner, score) via score_query_against_candidate."""
    best = (None, 0.0)
    for c in candidates:
        s = score_query_against_candidate(query, c)
        if s > best[1]:
            best = (c, s)
    return best


# --------------------------------------------------------------------------- #
# Test 1 — Happy Path: CW-100-Pattern muss den echten Kemmler-Eintrag finden
# --------------------------------------------------------------------------- #
def test_cw100_matcht_echten_kemmler_eintrag():
    """Pattern ``CW100`` (wie heute aus ``|Profile|CW100|`` generiert) muss
    gegen den echten Kemmler-CW-100-String mindestens Threshold-Score
    erreichen.

    Erwarteter Status heute: ROT (der Bug).
    Erwarteter Status nach korrektem Fix: GRUEN.
    """
    score = score_query_against_candidate("CW100", KEMMLER_CW_100)
    assert score >= FUZZY_THRESHOLD, (
        f"Erwartet ≥ {FUZZY_THRESHOLD}, bekommen {score:.1f}. "
        f"Query 'CW100' reicht im aktuellen Normalizer nicht aus, weil "
        f"es als Einzel-Token 'cw100' behandelt wird und nicht in den "
        f"Candidate-Tokens vorkommt."
    )


# --------------------------------------------------------------------------- #
# Test 2 — Dimensions-Separation: CW-75 gewinnt gegen CW-100 und UW-75
# --------------------------------------------------------------------------- #
def test_cw75_pattern_waehlt_cw75_kandidaten():
    """Pattern ``CW75`` soll unter drei Kandidaten den 75-mm-CW-Profil
    gewinnen — nicht den 100-mm-CW noch den 75-mm-UW.

    Erwarteter Status heute: ROT.
    Erwarteter Status nach korrektem Fix: GRUEN.
    """
    winner, score = _best(
        "CW75",
        [
            "CW-Profil 100x50x0,6 mm BL=2600 mm",  # anderes Mass
            SYNTH_CW_75,  # gewinner
            SYNTH_UW_75,  # anderer Typ
        ],
    )
    assert winner == SYNTH_CW_75, (
        f"Erwartet Winner = {SYNTH_CW_75!r}, bekommen {winner!r} mit "
        f"Score {score:.1f}. Dimensions- und Typ-Token werden aktuell "
        f"nicht sauber voneinander unterschieden."
    )
    assert score >= FUZZY_THRESHOLD, (
        f"Winner steht, aber Score {score:.1f} < Threshold {FUZZY_THRESHOLD}."
    )


# --------------------------------------------------------------------------- #
# Test 3 — False-Positive-Schutz TP75 (Türpfosten-Steckwinkel)
# --------------------------------------------------------------------------- #
def test_cw75_matcht_nicht_auf_tuerpfosten():
    """Guard-Test: verhindert False-Positive ``TP75 Türpfosten-Steckwinkel``
    als CW-75-Profil.

    Aktueller Status: GRUEN, weil der zu fixende Bug alle Scores auf 0
    zieht und daher auch False-Positives verhindert.

    Erwarteter Status nach naivem Fix: ROT. Wenn der Normalizer
    ``cw75`` schlicht in ``cw 75`` zerlegt, tauchen beide Tokens ``cw``
    und ``75`` im TP-Kandidaten (``TP75 ... CW/UA-Prof``) auf; der
    Score springt auf ~100 %. Das ist der False-Positive-Pfad, den
    dieser Test verhindern soll.

    Erwarteter Status nach korrektem Fix: GRUEN. Ein vollstaendiger
    Fix mit Dimensions-Matching-Bonus muss garantieren, dass der Typ-
    Token (``cw``) nur zaehlt, wenn er **zum Hauptprodukt** gehoert —
    nicht wenn er in einem Nebensatz (``f. CW/UA-Prof``) steht.

    Wenn dieser Test nach einem Fix ROT wird, obwohl er vorher gruen
    war, ist der Fix zu aggressiv und laesst False-Positives durch —
    Stuckateur-Zubehoer wird dann faelschlich als tragendes Profil
    gematcht.
    """
    score = score_query_against_candidate("CW75", KEMMLER_TP_75)
    assert score < FUZZY_THRESHOLD, (
        f"False-Positive: TP75-Türpfosten matcht mit Score {score:.1f} "
        f"≥ Threshold {FUZZY_THRESHOLD} — das ist Stuckateur-Zubehör, "
        f"kein CW-75-Profil."
    )


# --------------------------------------------------------------------------- #
# Test 4 — Echte Katalog-Luecke: keine Treffer akzeptabel
# --------------------------------------------------------------------------- #
def test_cw75_ohne_passende_kandidaten_bleibt_ohne_match():
    """Guard-Test: verhindert False-Positive ``CW-Profil 100`` oder
    ``UW-Profil 100`` als Ersatz fuer einen gesuchten CW-75.

    Aktueller Status: GRUEN, weil der Bug alle Scores auf 0 zieht und
    daher auch diese falschen Ausweich-Matches verhindert.

    Erwarteter Status nach naivem Fix: GRUEN. Nach bloßer Normalizer-
    Aufweichung haben sowohl CW-100 (Overlap {cw} = 50 %) als auch
    UW-100 (Overlap {} = 0 %) Scores deutlich unter Threshold — der
    Test bleibt gruen.

    Erwarteter Status nach korrektem Fix: GRUEN. Auch mit Dimensions-
    Matching-Bonus darf weder CW-100 noch UW-100 ueber die Threshold
    rutschen, wenn die Anfrage explizit 75 mm will.

    Wenn dieser Test nach einem Fix ROT wird, obwohl er vorher gruen
    war, ist der Fix zu aggressiv: er buchhalterisch naechstbeste
    Alternativen als Treffer, statt die echte Katalog-Luecke (kein
    75er-Profil vorhanden) sichtbar zu machen.
    """
    _, score = _best(
        "CW75",
        [
            "CW-Profil 100x50x0,6 mm BL=2600 mm",
            "UW-Profil 100x50x0,6 mm BL=2600 mm",
        ],
    )
    assert score < FUZZY_THRESHOLD, (
        f"Katalog hat kein 75er-Profil, trotzdem Score {score:.1f} "
        f"≥ Threshold. Der Matcher bucht jetzt falsche Alternativen als "
        f"Treffer statt die Luecke sichtbar zu machen."
    )


# --------------------------------------------------------------------------- #
# Test 5 — False-Positive-Schutz UA-Anschlusswinkel
# --------------------------------------------------------------------------- #
def test_cw75_matcht_nicht_auf_ua_anschlusswinkel():
    """Guard-Test: verhindert False-Positive ``Anschlusswinkel f. UA-Profil``
    als CW-75-Profil.

    Aktueller Status: GRUEN, weil der Bug alle Scores auf 0 zieht.

    Erwarteter Status nach naivem Fix: GRUEN. Nach Normalizer-
    Aufweichung haette der UA-Kandidat Tokens ``{anschlusswinkel, ua,
    profil, 50}`` — die Query-Tokens ``{cw, 75}`` haben 0 Overlap.

    Erwarteter Status nach korrektem Fix: GRUEN. UA-Einträge duerfen
    das bereits funktionierende UA-Matching nicht gefaehrden.

    Wenn dieser Test nach einem Fix ROT wird, obwohl er vorher gruen
    war, hat der Fix den Typ-Filter aufgeweicht (``cw`` gilt plotz-
    lich auch als UA-Indikator, oder ``profil`` allein reicht) — das
    waere eine schwerwiegende Regression gegen das existierende
    UA-Matching.
    """
    score = score_query_against_candidate("CW75", KEMMLER_UA_50)
    assert score < FUZZY_THRESHOLD, (
        f"False-Positive: UA-Anschlusswinkel matcht mit Score {score:.1f} "
        f"≥ Threshold {FUZZY_THRESHOLD} — das ist kein CW-75-Profil."
    )


# --------------------------------------------------------------------------- #
# Test 6 — Typ-Prioritaet vor Dimension
# --------------------------------------------------------------------------- #
def test_cw75_typ_schlaegt_dimension_bei_winner_pick():
    """Pattern ``CW75`` gegen zwei Kandidaten — einer ist Typ-korrekt
    mit falscher Dimension (CW-100), einer ist Typ-falsch mit
    korrekter Dimension (UW-75). Der Typ-korrekte muss gewinnen.

    Begruendung: Der Profil-Typ (CW vs. UW) bestimmt die statische
    Funktion der Wand. Ein korrekt dimensionierter UW-Profil ist KEIN
    Ersatz fuer einen falsch-dimensionierten CW-Profil — die Wand
    wuerde zu schwach.

    Erwarteter Status heute: ROT (beide Scores 0, Winner = None).
    Erwarteter Status nach korrektem Fix: GRUEN. Die Fix-Gewichtung
    muss so sein, dass der Typ-Token ``cw`` hoeher gewichtet wird als
    die Dimension ``75``. Z. B. 70 % Typ + 30 % Dimension liefert:
    CW-100 → 0,7·1 + 0,3·0 = 0,7; UW-75 → 0,7·0 + 0,3·1 = 0,3 →
    CW-100 gewinnt.
    """
    winner, _score = _best(
        "CW75",
        [
            "CW-Profil 100x50x0,6 mm BL=2600 mm",  # Typ korrekt, Dim falsch
            "UW-Profil 75x40x0,6 mm BL=2600 mm",  # Typ falsch, Dim korrekt
        ],
    )
    assert winner == "CW-Profil 100x50x0,6 mm BL=2600 mm", (
        f"Typ-Priorität verletzt: Winner = {winner!r}. Erwartet war "
        f"der CW-Kandidat (richtiger Typ, falsche Dimension), nicht "
        f"der UW-Kandidat (falscher Typ, richtige Dimension)."
    )
