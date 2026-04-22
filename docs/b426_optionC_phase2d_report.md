# B+4.2.6 Option C Phase 2d — E2E-Regressions-Check

**Stand:** 22.04.2026 vormittags | **Branch:** `claude/beautiful-mendel`
**Commits:** 19 lokal vor Remote → nach diesem Report 20

## Executive Summary

Der Option-C-UT-Blacklist-Filter löst die PE-Folien-UT40-Regression
**vollständig** ohne Kollateralschaden. Stuttgart-LV Material netto
sinkt von 204 k € (B+4.2.7-Stand gestern Abend) auf **134 k €**, die
Angebotssumme auf **975 k €** — exakt im erwarteten Zielbereich
(130–160 k bzw. ~980 k). CW-Profil-Fuzzy-Fallback, B+4.2.7-Bundle-
Korrekturen und alle Random-Stichproben bleiben unberührt. Alle 389
Tests grün. Bereit zum Push.

## Drei Kern-Fragen

### (a) UT40-Regression verschwunden? ✓

Drei Dämmungs-Positionen im Vergleich über drei Stände hinweg:

| Position | 21.04. morgens (vor Fix) | 21.04. abends (B+4.2.6+7) | **22.04. (nach Option C)** |
|---|---|---|---|
| 1.9.1.1.10 D112 76 m² | 10,48 €/m² | 19,99 €/m² | **10,48 €/m²** ✓ |
| 1.9.2.2.30 W112 440 m² | 13,62 €/m² | 29,47 €/m² | **13,62 €/m²** ✓ |
| 1.9.2.2.60 W628A 123 m² | 45,54 €/m² | 61,39 €/m² | **45,54 €/m²** ✓ |

Die Dämmungs-Material-Zeile (#3) matcht wieder auf Rockwool Sonorock
(3,05 €/m²) statt PE-Folie UT40 (18,90 €/m²). Der Blacklist-Filter
hat den UT40-Kandidaten vor dem Fuzzy-Scorer aus dem Pool entfernt
→ Sonorock gewinnt wie im ursprünglichen Zustand.

### (b) CW-100-Fuzzy-Match bleibt intakt? ✓

| Position | Stand gestern Abend (B+4.2.7) | **Stand jetzt** |
|---|---|---|
| 1.9.2.2.100 Deckenschürze 31 m | material_ep = 27,80 €/m | **27,80 €/m** (identisch) |
| 1.9.2.2.50 W133 135 m² | material_ep = 124,99 €/m² | **124,99 €/m²** (identisch) |
| 1.9.2.2.80 W625 390 m² | material_ep = 38,08 €/m² | 22,23 €/m² (leicht besser) |

Die Deckenschürze enthält den CW-Profil-Fuzzy-Fallback: der reale
Kemmler-Entry „CW-Profil 100x50x0,6 mm" hat **keinen** extrahierten
Code (strenger Regex, Phase-1-Design) — der Filter rührt ihn nicht
an, der Fuzzy-Scorer matcht ihn wie gestern. Die W625-Reduktion um
15,85 €/m² ist das UT40-Aus: die Dämmungs-Zeile wechselt auch hier
von PE-Folie zurück auf Sonorock.

### (c) B+4.2.7-Bundle-Korrekturen intakt? ✓

Fünf Positionen mit Bundle-korrigierten Preisen aus gestern:

| Position | material_ep gestern Abend | **jetzt** |
|---|---|---|
| 1.9.1.5.15 Streckmetalldecke | 0,15 €/m² | **0,15 €/m²** (unverändert) |
| 1.9.2.2.100 Deckenschürze | 27,80 €/m | **27,80 €/m** |
| 1.9.1.5.17 Streckmetalldecke | 0,15 | **0,15** |
| 1.9.2.2.120 Deckenschürze | 27,80 | **27,80** |
| 1.9.1.5.18 Streckmetalldecke | 0,15 | **0,15** |

Alle aus B+4.2.7 entpackten CW-Profil- und Kantenprofil-Preise
bleiben stabil. Der Backfill von heute Morgen (126 Entries mit
`product_code_*`) konkurriert nicht mit der gestrigen
`price_per_effective_unit`-Logik.

### (d) Random-Stichprobe: 5 unbeteiligte Positionen

| Position | material_ep | Δ gestern | Δ morgen |
|---|---|---|---|
| 1.9.2.1.10 Deckenschott | 45,13 | **0,00** | **0,00** |
| 1.9.2.2.183 Revisionsklappe | 46,90 | **0,00** | **0,00** |
| 1.9.1.4.60 Deckensprung | 5,17 | **0,00** | **0,00** |
| 1.9.2.2.180 Eckschiene | 0,00 | **0,00** | **0,00** |
| 1.9.2.2.187 Leibungsbekleidung | 1,14 | **0,00** | **0,00** |

**Null Drift** — alle Positionen, die weder UT40 noch CW-Profil
betreffen, sind identisch zu vorher. Der Blacklist-Filter ist
chirurgisch, wie designed.

## Diff-Tabellen

### A — Morgen 21.04. (vor allen Fixes) vs. Jetzt

| Metrik | Morgen 21.04. | Jetzt 22.04. | Δ |
|---|---|---|---|
| supplier_price Matches | 95 | **118** | +23 |
| estimated Stufe 4 | 70 | 62 | −8 |
| not_found | 79 | **64** | −15 |
| Positionen EP > 0 | 77 | 77 | 0 |
| Material netto | 122.666 € | **134.278 €** | **+11.612 €** (+9,5 %) |
| Angebotssumme | 959.558 € | **975.267 €** | +15.709 € (+1,6 %) |

Die +12 k € Material gegenüber Morgen stammen aus echten Match-
Zugewinnen (CW-Profil 167,40→8,05 €/m mit B+4.2.7, CD60-Clips,
korrigierte Sack-/Paket-Preise aus dem technischen-Schuld-Abbau).
**Das ist jetzt eine realistische Stuttgart-Angebotssumme.**

### B — Gestern Abend (B+4.2.7-Teil-2) vs. Jetzt

| Metrik | Gestern 21:40 | Jetzt | Δ |
|---|---|---|---|
| supplier_price Matches | 118 | **118** | 0 |
| estimated Stage 4 | 62 | 62 | 0 |
| not_found | 64 | 64 | 0 |
| Material netto | 204.244 € | **134.278 €** | **−69.967 €** (−34 %) |
| Angebotssumme | 1.064.134 € | **975.267 €** | −88.867 € (−8 %) |

**−70 k € Material durch den Blacklist-Filter** — exakt der UT40-
Schaden, den der Filter heute chirurgisch entfernt. Stage-Verteilung
**unverändert** (118/62/64), d. h. derselbe Kandidat-Pool matcht,
nur mit korrigiertem Gewinner bei Dämmungs-Zeilen.

## Pilot-Readiness-Bewertung

**B+4.2.6 Option C ist fertig und pilot-ready.**

- ✓ Die PE-Folien-UT40-Regression ist nachweislich behoben.
- ✓ Keine Kollateralschäden: CW-Fuzzy-Fallback intakt, B+4.2.7-
  Bundle-Korrekturen intakt, Random-Stichprobe null Drift.
- ✓ Alle 389 Tests grün (inkl. 6 UT-Blacklist-Golden, 21 Extractor-
  Tests, 6 CW/UW-Matcher-Golden, alle B+4.2.7 + bestehende Tests).
- ✓ Whitelist-Design: neue Blacklist-Einträge brauchen zwingend
  Test-Case + Regressions-Fall. Keine Präventiv-Aufnahmen.
- ✓ Stuttgart-LV-Angebotssumme im erwarteten Bereich **~975 k €**.

## Vergleich der drei Matcher-Fix-Versuche

| Versuch | Ergebnis |
|---|---|
| **B+4.2.6 Phase 3 gestern** (DNA-Pattern-Trennung + Whitelist-Scoring) | Funktional (6/6 Golden grün, 349/349 Tests grün), aber mit PE-Folie-UT40-Regression: Material explodiert 122 k → 536 k € |
| **B+4.2.6 Iteration 4** (gestern: `_explode_alnum` nur auf Query) | Brach 5 bestehende Tests (KKZ30/SLP30/MP75L Kemmler-Real-Lookup). Rollback. |
| **B+4.2.6 Option C Phase 2 heute** (strukturelle Code-Extraktion + Blacklist-Pre-Filter) | **Funktional ohne Regression.** 389 Tests grün, Material 134 k € (realistisch), chirurgischer Fix ohne Nebenwirkungen. |

### Lessons Learned

- **Strukturierte Daten vor Matcher-Logik.** Die Phase-1-Extraktion der
  Produkt-Codes in `attributes` macht die Matcher-Regel in Phase 2
  trivial — zwei Bedingungen (Type ∈ Blacklist, Dimension-Kollision)
  und fertig. Die früheren Versuche mussten mit verschmolzenen
  Tokens `cw75` kämpfen und dabei entweder False-Negatives (keine
  Matches) oder False-Positives (PE-Folie) riskieren.
- **Do-the-minimum-Disziplin bei Blacklists.** Die Entscheidung
  `{UT}` statt `{UT, TC}` hat verhindert, dass wir ohne konkreten
  Bug präventiv filtern. Das spart Wartung und macht jede
  Erweiterung nachvollziehbar.
- **Iteration-Limit schützt vor Gewichts-Drehen.** Phase 2b hat in
  Iteration 1 getroffen, weil die Logik vorher via Golden-Tests
  klar beschrieben war — kein Tuning nötig.

## Push-Vorbereitung

- **Lokal:** 20 Commits vor Remote (19 + dieser Commit).
- **Tests:** 389 passed, 0 failed.
- **Working Tree:** clean (abgesehen von bekannten IDE-/Smoke-Artefakten).
- **Push erfolgt erst nach Freigabe durch Benjamin.**
