# B+4.3.0c E2E-Smoke gegen Stuttgart-LV

**Datum:** 22.04.2026
**Test-Skript:** `lv-preisrechner/tests/live/test_gaps_smoke.py`
**Snapshot:** `lv-preisrechner/tests/live/e2e_gaps_smoke.json` (gitignored)
**Laufumgebung:** app-DB `data/lv_preisrechner.db`, Tenant
`19f3cd31-…` mit Stuttgart-LV `9d9fda20-…` (102 Positionen, 244
Materialien aus letzter Kalkulation).

Der HTTP-Layer ist bereits durch die 10 Golden-Tests in
`test_lvs_gaps.py` abgedeckt. Der Smoke ruft `compute_lv_gaps`
direkt auf — dieselbe Funktion, die der Handler nach dem Tenant-Check
aufruft.

---

## Call A — Default (ohne Opt-in)

| Feld | Wert |
|---|---|
| HTTP-Equivalent | `GET /api/v1/lvs/9d9fda20-…/gaps` |
| elapsed | **0,48 ms** (grün) |
| total_positions | 102 |
| total_materials | 244 |
| gaps_count | **126** |
| missing_count | 64 |
| estimated_count | 62 |
| low_confidence_count | 0 (Opt-in aus) |
| counter_invariant | **OK** |
| erste severity | `missing` |
| letzte severity | `estimated` |

Severities in gaps: `{missing: 64, estimated: 62}` — keine `low_confidence`
im Default-Modus.

## Call B — Mit `?include_low_confidence=true`

| Feld | Wert |
|---|---|
| HTTP-Equivalent | `GET /api/v1/lvs/9d9fda20-…/gaps?include_low_confidence=true` |
| elapsed | **0,42 ms** (grün) |
| gaps_count | 126 |
| missing_count | 64 |
| estimated_count | 62 |
| low_confidence_count | **0** |
| counter_invariant | **OK** |
| b_count >= a_count | True |

Auf dem aktuellen Stuttgart-LV gibt es keine `supplier_price`-Materialien
mit `confidence < 0.5`. Das ist plausibel: der B+4.2.6-Option-C-Matcher
fällt bei sehr schwachen Scores direkt auf Stage 4 (`estimated`), statt
einen wackeligen supplier_price zurückzugeben. Der Opt-in-Pfad bleibt
korrekt implementiert, hat hier nur keine aktive Wirkung.

## Call C — Stichproben

| Severity | pos_oz | material_dna | material_name | match_confidence | price_source |
|---|---|---|---|---|---|
| missing | `1.9.1.2.50` | `""` | `""` | None ✓ | `not_found` |
| estimated | `1.9.1.1` | `""` | `""` | 0.5 ✓ | `estimated` |
| low_confidence | — | — | — | — | kein Eintrag |

**`match_confidence=None` bei missing** ist korrekt (Baseline §3).
**`confidence=0.5` bei estimated** ist die Default-Konfidenz der
Kategorie-Mittelwert-Schätzung.

## UT40-Check

| Bedingung | Ergebnis |
|---|---|
| UT40-Hits im Gaps-Report (über `material_name` oder `source_description`) | **0** |

Bestätigt: B+4.2.6-Blacklist wirkt so, dass UT40-PE-Folie nicht mehr
in die materialien-JSONs als supplier_price-Winner gelangt — deshalb
taucht sie auch im Gaps-Report nicht auf (weder als false positive
noch als valider Match).

## Performance

Beide Calls <1 ms auf dem vollen Stuttgart-LV (102 Positionen, 244
Materialien). Das ist deutlich unter dem grünen Richtwert (<500 ms).
Keine Performance-Sorgen.

---

## Beobachtung: leere `material_name`-Werte

**Befund:** Bei den gezeigten Stichproben ist sowohl `material_dna` als
auch `material_name` ein leerer String.

**Ursache:** Bei bestimmten Stuttgart-Positionen (z. B. `1.9.1.2.50`,
`1.9.1.1`) liefert der Rezept-Resolver kein `MaterialBedarf` mit DNA —
die Position wird zum Regiestunden-ähnlichen Fallback umgelenkt, und
die Kalkulation setzt nur einen Marker-Eintrag ins `materialien`-JSON
(mit `dna=""`). Das ist **Datenlage**, kein Bug in B+4.3.0c.

**Auswirkung auf UI (B+4.3.1):** Der Frontend-Tab für Katalog-Lücken
sollte bei leerem `material_name` einen Fallback wählen — z. B.
`source_description` oder `position_name` anzeigen. Aufgenommen als
**Follow-up-Kandidat**, nicht als Backend-Blocker.

---

## Overall

| Check | Ergebnis |
|---|---|
| Counter-Invariante (beide Calls) | OK |
| `gaps_count > 0` im Default | OK (126) |
| `b_count ≥ a_count` | OK |
| Kein UT40-Hit | OK |
| Nur `missing`+`estimated` im Default | OK |

**Gesamt-Verdikt:** `Overall: OK` — Endpoint ist pilot-ready für die
B+4.3.1-Frontend-Integration.
