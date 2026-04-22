# B+4.3.0b Phase 4 — E2E-Smoke Report

**Stand:** 22.04.2026 nachmittags | **Tenant:** `19f3cd31-…`
(Stuttgart-LV) | **Quelle:** `scripts/smoke_candidates_endpoint.py`

## Executive Summary

Drei echte Positionen im Stuttgart-LV wurden durch
`list_candidates_for_position` gezogen. **UT40-PE-Folie erscheint in
keinem Material als Kandidat** (Blacklist-Filter verifiziert),
CW-Profil 100 wird bei CW-75-Query als Fuzzy-Kandidat mit Score 0,68
und Preis 8,05 €/m geliefert, Materialien ohne Datenbasis bekommen den
Platzhalter-Estimated-Eintrag mit `price_net=0`. **Alle Laufzeiten
< 50 ms** — weit im grünen Bereich.

## Stichprobe 1 — W628A (Schachtwand)

**Position:** `oz 1.9.2.2.60`, 123 m², System `W628A`, `elapsed=34 ms`

Rezept liefert 6 Materialien:

| # | Material | Anzahl Kandidaten | Winner-Stage | Winner-Preis | UT40 im Pool? |
|---|---|---|---|---|---|
| 1 | Fireboard 20 mm | 4 | supplier_price (conf 1.00) | 18,35 €/m² | ✓ sauber |
| 2 | CW 75 | 4 | fuzzy (conf 0,68) | **8,05 €/m** (CW-Profil 100×50×0,6) | ✓ sauber |
| 3 | UW 75 | 3 | fuzzy (conf 0,33) | 2,51 €/lfm (GK-Streifen, schwach) | ✓ sauber |
| 4 | **40 mm (Dämmung)** | 3 | supplier_price (conf 1.00) | **3,05 €/m² (Sonorock)** | ✓ **sauber** |
| 5 | Schrauben 3.5×45 | 4 | supplier_price (conf 1.00) | 0,045 €/Stk | ✓ sauber |
| 6 | Spachtel Universal | 3 | supplier_price (conf 1.00) | 1,03 €/kg | ✓ sauber |

**Kern-Verifikation (UT40-Blacklist):**

Die Dämmungs-Material-Zeile (`40mm` Query, Kategorie `Daemmung`)
liefert als Kandidaten:

- `Trennwandpl. Sonorock WLG040, 1000x625x40 mm` — conf 1.00, 3,05 €/m² ← **Winner**
- `Trennwandpl. Thermolan TP115 WLS038, 1250x625x40 mm` — conf 1.00, 1,79 €/m²
- `Ø Kategorie Daemmung` (Platzhalter, keine Datenbasis für den Durchschnitt
  nach dem Blacklist-Filter) — conf 0.00, 0,00 €/m²

**PE-Folie UT40 erscheint explizit nicht.** Blacklist greift wie designed.

### CW-Profil-Verhalten (erwartungsgemäß)

Der einzige echte CW-Profil-Entry im Katalog (100 mm) wird für eine
CW-75-Query mit Fuzzy-Score **0,68** geliefert — unter Threshold 0,85,
daher Stage `fuzzy`. Das ist semantisch korrekt (falsche Dimension,
aber richtiger Typ). Der Near-Miss-Drawer zeigt das dem Handwerker
transparent mit der `match_reason` „Fuzzy-Aehnlichkeit 68%" — er
kann entscheiden, ob er das Profil akzeptiert oder manuell überschreibt.

Preis 8,05 €/m ist der B+4.2.7-Bundle-Resolver-Wert (167,40 / (8×2,6)).
Korrekt.

## Stichprobe 2 — Deckensegel (exotisches System)

**Position:** `oz 1.9.1.6.10`, 31 Stk, System `Deckensegel`, `elapsed=19 ms`

Rezept liefert 2 Materialien, beide ohne Daten:

| Material | Kandidaten | Ergebnis |
|---|---|---|
| System 7300 | 1 (nur estimated) | conf 0.00, 0,00 €/Stk, „Kein Katalog-Durchschnitt verfuegbar" |
| Seil | 1 (nur estimated) | conf 0.00, 0,00 €/Stk, „Kein Katalog-Durchschnitt verfuegbar" |

Erwartungsgemäß — die Kategorien `Deckensegel` und `Abhänger` haben im
Kemmler-Katalog keine matching Entries. Platzhalter-Estimated-Pfad
greift, Invariante „letzter Eintrag = estimated" bleibt erhalten, UI
kann „Richtwert nicht verfügbar" rendern.

## Stichprobe 3 — Streckmetalldecke

**Position:** `oz 1.9.1.5.10`, 0 m², System `Streckmetalldecke`, `elapsed=11 ms`

3 Materialien:

| Material | Kandidaten | Winner | Kommentar |
|---|---|---|---|
| LMD 215 | 1 (nur estimated) | conf 0.00 | kein Match im Katalog |
| Tragprofil | 2 | supplier_price conf 1.00 | construkt cliq 24MR (0,019 €/m, B+4.2.7-Bundle-resolver aktiv) |
| Nonius | 4 | supplier_price conf 1.00 | Kemmler SBN100 Sicherungsbügel (0,090 €/Stk, R1-Backfill) |

Die zwei echten Matches belegen, dass der Backfill von gestern
(product_code_* + R1-Gebinde-Auflösung) unverändert greift.

## UT40-Blacklist — Gesamt-Verifikation

Über alle drei Positionen × 11 Materialien × jeweils bis zu 4 Kandidaten
wurden **30 Kandidaten** evaluiert. **Null** davon trägt `UT40` im
Produktnamen. ✓

## Performance

| Position | Materialien | elapsed |
|---|---|---|
| W628A | 6 | **34 ms** |
| Deckensegel | 2 | **19 ms** |
| Streckmetalldecke | 3 | **11 ms** |

**Alle Calls < 50 ms** — weit unter dem Zielwert 500 ms (grün).
Kein Follow-up-Ticket für Pre-Filter nötig.

## Überraschungen / Auffälligkeiten

- **UW 75 hat als Winner einen GK-Plattenstreifen mit Score 0,33.**
  Das ist noise — der Matcher hat einfach den besten verfügbaren
  Kandidat in der Kategorie "Profile" ausgewählt, weil kein
  UW-spezifisches Entry existiert. Die UI wird mit `match_reason
  "Fuzzy-Aehnlichkeit 33%"` dem Bieter signalisieren, dass die
  Wahl sehr unsicher ist — der Handwerker klickt in dem Fall
  „Preis selbst eintragen". Design-konformes Verhalten.
- **„Kein Katalog-Durchschnitt verfuegbar" bei Daemmungs-Estimated**
  ist nicht intuitiv — es gibt ja Sonorock und Thermolan. Grund:
  `_build_estimated_candidate` iteriert über Entries mit Category
  `Daemmung` + `unit_matches(query_unit, …)`. Der Filter zieht nur
  Entries aus `valid_from >= year_ago`; Sonorock und Thermolan
  haben `valid_from=2026-01-01`, also sollten sie dabei sein. Warum
  Preis 0? → Prüfen: vielleicht matched `unit_matches("m²",
  e.effective_unit)` nicht, weil `effective_unit` auf leer steht.
  **Follow-up-Notiz**, kein Blocker für Pilot.

## Fazit — Endpoint pilot-ready?

**Ja.** Alle Akzeptanz-Kriterien aus Phase 4 sind erfüllt:

| Kriterium | Ergebnis |
|---|---|
| CW-Material-Position liefert CW-Profil-Kandidat | ✓ (CW-Profil 100, Fuzzy 0,68, 8,05 €/m) |
| 40mm-Dämmungs-Position: UT40 ausgeblendet, Sonorock drin | ✓ |
| Nicht-matchbare Position: estimated-Only oder leere Liste | ✓ (Deckensegel + LMD 215) |
| Performance < 1000 ms median | ✓ **< 50 ms** über alle Stichproben |
| Keine Exception/500-Fehler | ✓ |
| Backfill-verifizierte Einträge erscheinen | ✓ (construkt cliq, Sicherungsbügel) |

## Follow-up-Notizen (nicht blockend)

1. Estimated für Kategorie mit existierenden Daten liefert teils
   Preis 0,00 (Daemmung-Fall). Prüfen, ob `unit_matches` im SQL/Python-
   Flow Edge-Cases hat.
2. `Fuzzy`-Kandidaten mit Score < 0,50 wären ggf. besser komplett aus
   der Top-3-Liste ausgeblendet (rein Rauschen). Aktuell werden sie
   angezeigt. UI kann visuelle Unterscheidung machen; Backend-Filter
   als Optimierung denkbar.
3. W628A liefert 6 Materialien — UI muss mit 6 Sektionen umgehen
   können. B+4.3.1 sollte das im Drawer-Design berücksichtigen.
