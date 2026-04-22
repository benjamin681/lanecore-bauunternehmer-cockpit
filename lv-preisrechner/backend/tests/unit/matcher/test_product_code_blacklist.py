"""B+4.2.6 Option C Phase 2 — Golden-Tests fuer den Blacklist-Pre-Filter.

Hintergrund: Der E2E-Lauf vom 21.04.2026 zeigte, dass der Fuzzy-Scorer
PE-Folien-Entries mit Suffix-Code `UT40` faelschlich auf Daemmungs-
Queries (`|Daemmung||40mm|`) matcht. Die Funktion
:func:`app.services.price_lookup.should_exclude_by_blacklist`
soll diesen Kandidaten **vor** dem Scoring aus dem Pool filtern.

Status-Uebersicht:
- Test 1: enthaelt Teil-Assertion fuer UT (rot) + TC-Guard (gruen).
- Test 2: rot (Dim-Kollisions-Logik muss greifen).
- Test 3, 4, 5: green guards — stellen sicher, dass der Filter nicht
  ueberzieht und keine legitimen Kandidaten blockiert.

Die Tests gehen direkt gegen
`should_exclude_by_blacklist(candidate_attrs, query_material_name)`.
Die Signatur ist bewusst pur (kein DB-Zugriff, kein Entry-Objekt noetig),
damit die Logik isoliert testbar ist. Der Fuzzy-Scorer und der
SupplierPriceEntry-Flow bleiben in dieser Phase unberuehrt.
"""

from __future__ import annotations

import pytest

from app.services.price_lookup import (
    PRODUCT_CODE_BLACKLIST,
    should_exclude_by_blacklist,
)


# --------------------------------------------------------------------------- #
# Test 1 — UT40 gegen 40mm-Query: UT wird gefiltert, TC/WLG/kein-Code bleiben
# --------------------------------------------------------------------------- #
def test_ut40_wird_gefiltert_tc_und_wlg_bleiben():
    """Kernfall der Regression. PE-Folie mit UT40 darf die Daemmungs-
    Query 40mm nicht mehr gewinnen; ein TC-Kandidat mit derselben
    Dimension bleibt als Regression-Schutz im Pool (TC ist NICHT
    blacklistet), WLG040 ebenso.

    Aktueller Status: **teilweise rot**, weil der Stub noch immer False
    zurueckgibt. Nach Fix:
    - UT-Teil wird gruen (Filter greift).
    - TC- und WLG-Teile bleiben gruen (Filter greift NICHT).

    Wenn dieser Test nach einem Fix ROT wird, wurden entweder UT nicht
    gefiltert oder TC/WLG versehentlich mitgefiltert. Beide Fehler-
    Richtungen muessen ausgeschlossen bleiben.
    """
    query = "40mm"

    # UT40 PE-Folie — muss ausgeschlossen werden
    ut_attrs = {"product_code_type": "UT", "product_code_dimension": "40"}
    assert should_exclude_by_blacklist(ut_attrs, query) is True, (
        "UT40 muss bei 40mm-Query gefiltert werden (Blacklist-Hit + "
        "Dimension-Kollision)."
    )

    # TC-Kandidat mit Dim 40 — darf NICHT gefiltert werden (TC nicht in Blacklist)
    tc_attrs = {"product_code_type": "TC", "product_code_dimension": "40"}
    assert should_exclude_by_blacklist(tc_attrs, query) is False, (
        "TC40 darf NICHT gefiltert werden — TC ist bewusst nicht in der "
        "Blacklist, siehe docs/b426_optionC_phase2_baseline.md."
    )

    # WLG040 Sonorock — darf NICHT gefiltert werden (WLG nicht in Blacklist)
    wlg_attrs = {"product_code_type": "WLG", "product_code_dimension": "040"}
    assert should_exclude_by_blacklist(wlg_attrs, query) is False


# --------------------------------------------------------------------------- #
# Test 2 — UT40 gegen 20mm-Query: keine Kollision, kein Filter
# --------------------------------------------------------------------------- #
def test_blacklist_greift_nur_bei_dimensions_kollision():
    """UT-Kandidat bleibt im Pool, wenn die Query eine andere Dimension
    hat. Die Filter-Logik darf nicht alle UT-Kandidaten pauschal
    werfen, sondern nur solche, die mit der Query-Dimension kollidieren.

    Aktueller Status: GRUEN (Stub gibt False — konsistent mit
    erwarteter Wirkung bei Nicht-Kollision). Nach Fix: GRUEN.

    Wenn dieser Test nach einem Fix ROT wird, filtert die Logik
    pauschal auf Blacklist-Typ, ohne die Dimension zu pruefen — das
    wuerde UT40 auch bei 20mm-Queries ausschliessen und legitime
    Fuzzy-Matches (z. B. mit Produktname-Tokens) verhindern.
    """
    ut_attrs = {"product_code_type": "UT", "product_code_dimension": "40"}
    assert should_exclude_by_blacklist(ut_attrs, "20mm") is False


# --------------------------------------------------------------------------- #
# Test 3 — Nicht-Blacklist-Code: bleibt immer im Pool
# --------------------------------------------------------------------------- #
def test_nicht_blacklist_code_wird_nie_gefiltert():
    """Jeder Kandidat mit Code ausserhalb der Blacklist bleibt im Pool,
    unabhaengig von Dimensions-Kollision.

    Aktueller Status: GRUEN. Nach Fix: GRUEN. Stellt sicher, dass WLG,
    CE, NAO, TP, MP, KKZ, SLP, SP usw. nicht betroffen sind.

    Wenn dieser Test nach einem Fix ROT wird, hat jemand die
    Blacklist ausserhalb der Review-Regel erweitert.
    """
    wlg_attrs = {"product_code_type": "WLG", "product_code_dimension": "040"}
    assert should_exclude_by_blacklist(wlg_attrs, "40mm") is False

    ce_attrs = {"product_code_type": "CE", "product_code_dimension": "3"}
    assert should_exclude_by_blacklist(ce_attrs, "3mm") is False

    # Bonus: DA (echtes Typ-Produkt, wurde explizit NICHT blacklistet)
    da_attrs = {"product_code_type": "DA", "product_code_dimension": "125"}
    assert should_exclude_by_blacklist(da_attrs, "125mm") is False


# --------------------------------------------------------------------------- #
# Test 4 — Kandidat ohne Code: bleibt immer im Pool
# --------------------------------------------------------------------------- #
def test_kandidat_ohne_code_wird_nie_gefiltert():
    """Kandidaten ohne extrahierten Code (freier Produktname wie
    'Rockwool Sonorock Trennwandplatte') landen im Fuzzy-Pfad wie
    bisher.

    Aktueller Status: GRUEN. Nach Fix: GRUEN.

    Wenn dieser Test ROT wird, hat die Filter-Logik einen Fall, in dem
    sie None-/missing-attributes als Blacklist-Hit behandelt — das
    wuerde die grosse Mehrheit des Katalogs aussperren.
    """
    # attributes-Dict existiert, enthaelt aber keine product_code_*-Keys
    plain_attrs = {"raw_price": 3.05, "list_price": None}
    assert should_exclude_by_blacklist(plain_attrs, "40mm") is False

    # attributes ist None (altes Entry ohne Metadaten)
    assert should_exclude_by_blacklist(None, "40mm") is False

    # attributes ist ein leeres Dict
    assert should_exclude_by_blacklist({}, "40mm") is False


# --------------------------------------------------------------------------- #
# Test 5 — CW-100-Query gegen CW-Profil-Entry: kein Filter, Fuzzy-Fallback aktiv
# --------------------------------------------------------------------------- #
def test_cw100_query_kein_code_im_kandidat_passiert_filter():
    """Regression-Schutz fuer B+4.2.6: die CW-100-Query trifft den
    Kemmler-CW-Profil-Entry, der **keinen** extrahierten Code hat
    (striker Regex matcht 'CW-Profil 100' nicht). Der Filter darf
    diesen Entry nicht anfassen; der Fuzzy-Fallback aus B+4.2.6 bleibt
    alleinverantwortlich.

    Aktueller Status: GRUEN (Stub gibt False). Nach Fix: GRUEN — Filter
    darf sich bei missing code nicht einmischen.

    Wenn dieser Test ROT wird, hat die Filter-Logik einen Fall, in dem
    sie das Fehlen von `product_code_type` als Ausschluss-Grund
    interpretiert — das wuerde die gestrige CW-100-Match-Wiederherstellung
    kassieren.
    """
    # CW-Profil-Entry hat keinen Code (Phase-1-Design)
    cw_profil_attrs = {"raw_price": 167.40}
    assert should_exclude_by_blacklist(cw_profil_attrs, "CW 100") is False


# --------------------------------------------------------------------------- #
# Meta-Guard: Blacklist enthaelt genau {UT}
# --------------------------------------------------------------------------- #
def test_blacklist_enthaelt_genau_UT():
    """Dokumentiert den Sollzustand der Blacklist. Schlaegt fehl, sobald
    Codes ohne konkreten Test-Case aufgenommen werden — erzwingt die
    im Baseline-Doc festgelegte Minimalismus-Regel.
    """
    assert PRODUCT_CODE_BLACKLIST == frozenset({"UT"})
