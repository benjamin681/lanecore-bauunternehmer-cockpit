# B+4.2.6 — End-of-Day-Status, 21.04.2026

**Branch:** `claude/beautiful-mendel`
**Remote-HEAD:** `5d41ef0` (docs: UI wording guide + Mockup v1)
**Lokaler HEAD:** `879b9f6` (fix(matcher) …)
**Differenz lokal → remote:** 3 Commits (nicht gepusht)
**Gesamttests:** 349 passed

## Commit-Stack (lokal, ungepusht)

| Hash | Titel |
|---|---|
| `879b9f6` | fix(matcher): B+4.2.6 separate dimension tokens in DNA pattern and scoring |
| `f3c5d10` | test: B+4.2.6 golden + guard tests for CW/UW matcher |
| `b490081` | docs: B+4.2.6 baseline before matcher fix |

## Was in diesem Stand funktioniert

- **DNA-Pattern-Trennung** in `materialrezepte.py`: alle CW/UW/CD-Pattern
  vom Format `|Profile|CW75|` auf `|Profile|CW|75|` umgestellt.
  Konsistent mit bestehendem UA-Pattern-Format.
- **Legacy-Matcher (`dna_matcher.py`)** bleibt kompatibel: der
  Hard-Code-Check (`"cw75"`, `"uw100"`, …) bekommt die Typ+Dim-Rück-
  Fusion, sodass bestehende Rezepte weiterhin korrekt scoren.
- **6 Golden-Tests** in `tests/unit/matcher/test_cw_uw_matching.py` grün:
  - 3 reproduzieren den Original-Bug (CW-100-Match, CW-75-Winner, Typ-
    vor-Dimension-Priorität).
  - 3 Guard-Tests gegen False-Positives (TP75-Türpfosten, UA-Anschluss-
    winkel, Katalog-Lücke).
- **Alle 349 bestehenden Tests** grün (inkl. `test_dna_matcher.py`,
  `test_kalkulation_integration.py`, `test_kemmler_real_lookup.py`,
  `test_price_lookup.py`, `test_package_lookup.py` usw.).
- **`score_query_against_candidate`-Änderung** mit Whitelist-Gate:
  60/25/15-Scoring nur bei Profil-Code-Queries (Typ ∈
  `{cw, uw, ua, cd, ud}` + genau eine numerische Dimension).
  Produktnamen wie „Rotband Pro" oder „GKB 12.5" bekommen weiterhin
  den klassischen Coverage-Score.

## Was in diesem Stand **nicht** funktioniert

Der E2E-Lauf auf dem Stuttgart-LV mit aktiven 4 Preislisten zeigt eine
verdeckte Regression:

| Metrik | vor B+4.2.6 | mit B+4.2.6 | Δ |
|---|---|---|---|
| supplier_price Matches | 95 | 103 | +8 (erwünscht) |
| Material netto (Σ) | 122 666 € | 536 078 € | **+337 %** (nicht erwünscht) |
| Angebotssumme | 959 558 € | 1 433 335 € | +49 % |

Ursache des Material-EP-Sprungs:

1. **False-Positive „PE-Folie UT40 als Dämmung"** — für alle Dämmungs-
   Rezepte (`|Daemmung||40mm|`, Query „40mm" → Token `{40}`) wählt der
   Matcher jetzt den Produktcode-Suffix-Entry `UT40` (PE-Folie
   18,90 €/m²) statt der korrekten Rockwool-Sonorock (3,05 €/m²).
   Betroffene Positionen: ~20 (alle Wand- und Deckenrezepte).
2. **CW-100-Bundle-Preis-Sichtbarkeit** — der einzige echte CW-Entry im
   Kemmler-Katalog trägt Preis 167,40 €/m, was vermutlich ein Bundle-
   Preis (8 Stück × 2,60 m) statt Laufmeter-Preis ist. Mein Fix macht
   diesen Eintrag erstmals zum Match-Kandidaten und legt damit das
   bekannte **B+4.2.7-Gebinde-Auflösungs-Problem** frei. Das ist kein
   Matcher-Fehler, sondern ein separater Parser/Entry-Preis-Defekt.

## Design-Konflikt im `_explode_alnum`

Der `_explode_alnum`-Helfer zerlegt Alpha+Digit-Tokens wie `"cw75"`
in `"cw 75"`. Er wurde in Iteration 1–3 auf **beide** Seiten
(Query + Candidate) angewandt und ist jetzt der Engpass:

- **Notwendig auf Candidate-Seite** — reale Kemmler-Produktnamen
  tragen verschmolzene Codes (`KKZ30`, `SLP30`, `MP75L`). Ohne
  Candidate-seitiges Explode matchen getrennte Queries (`"KKZ30 30kg"`)
  nicht gegen diese Entries. Der Entfernen-Versuch in Iteration 4 hat
  5 Tests in `test_kemmler_real_lookup.py` und `test_package_lookup.py`
  rot gemacht und wurde sofort revertiert.
- **Schädlich auf Candidate-Seite** — Produktcode-Suffixe wie `UT40`
  werden zu `{ut, 40}` zerlegt und matchen Anfragen nach reinen
  Zahlen wie `"40"`. Das ist der Ursprung der PE-Folie-Regression.

Ein simpler Scope-Fix (eine von beiden Seiten abschalten) führt nicht
zum Ziel. Das ist kein Gewichts-Tuning, sondern ein struktureller
Design-Konflikt.

## Lösungsrichtungen für morgen

Nicht-triviale Ansätze, aus denen morgen einer gewählt werden muss.
Die 6 Golden-Tests müssen in jedem Szenario grün bleiben — sie sind
der Regression-Schutz gegen jede dieser Lösungen.

### Option A — Semantische Produktcode-Klassifizierung

Whitelist bekannter Typ-Codes (z. B. `CW`, `UW`, `UA`, `CD`, `UD`,
`KKZ`, `SLP`, `MP`, `GKB`, `GKF`, `GKFI`, `GKP`) expliziert
definieren. Nur Tokens mit diesen Präfixen werden expand-behandelt.
Suffixe wie `UT40` bleiben unangetastet.

Vorteil: deterministisch, vollständig testbar.
Nachteil: Wartungskosten — jeder neue Lieferant bringt potenziell
neue Codes mit, die händisch aufgenommen werden müssen.

### Option B — Kontext-abhängige Explode-Strategie

Der Explode wird nicht immer, sondern nur bei spezifischen Query-
Mustern angewandt:

- Wenn die Query ein klassischer Profil-Code-Pattern ist (`CW 75`,
  `UW 100`) → Candidate-Seite explode aktivieren.
- Wenn die Query eine freie Beschreibung ist (`Rotband Pro`,
  `40mm`) → Candidate-Seite unverändert lassen.

Vorteil: keine Whitelist-Wartung.
Nachteil: verlässt sich auf die Struktur des `material_name`, der aus
dem Rezept kommt. Neue Rezept-Pattern-Formate könnten die Heuristik
brechen.

### Option C — Saubere Tokenisierung im Parser

Die verschmolzenen Produktcodes (KKZ30, SLP30, MP75L, UT40) werden
bereits beim **Parser-Schritt** (Claude-Vision-Prompt) zerlegt und
als strukturierte Felder im `SupplierPriceEntry` abgelegt
(`product_code`, `product_size`, `product_variant`). Der Matcher
sieht dann nur saubere Tokens, und `_explode_alnum` ist nicht mehr
nötig.

Vorteil: der saubere architektonische Weg; löst das Problem an der
Wurzel.
Nachteil: Eingriff in den Parser-Prompt. Alle bestehenden Preislisten
müssten neu geparst werden, um die neuen Felder zu befüllen.

## Empfehlung für den nächsten Schritt

Morgen zuerst **Option B** prüfen (minimaler Eingriff, deterministisch
testbar). Scheitert B an einem Edge-Case, **Option A** als Fallback.
**Option C** ist der architektonisch sauberste Weg, aber nur sinnvoll,
wenn der Parser sowieso angefasst wird (z. B. im Kontext B+4.2.7
Gebinde-Auflösung).

In jedem Fall: die 6 Golden-Tests bleiben als Regression-Schutz. Die
349 bestehenden Tests müssen grün bleiben. Kein Push des aktuellen
Stacks, bis die E2E-Regression gelöst ist.

## Was morgen konkret auf dem Tisch liegt

1. Option A oder B implementieren, E2E-Lauf wiederholen.
2. Material-EP-Summe zurück auf erwarteten Bereich (~120 000 € bis
   ~160 000 €) bringen. Erlaubte Differenz gegenüber heute Morgen:
   +15 000 bis +35 000 € durch CW-100-Match (B+4.2.7 bleibt Follow-up).
3. Dann `origin` pushen.
4. Anschließend in B+4.2.7 den CW-100-Bundle-Preis-Fehler auflösen
   (separates Thema).
