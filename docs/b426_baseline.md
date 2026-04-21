# B+4.2.6 — Baseline vor dem CW/UW-Matcher-Fix

**Stand:** 21.04.2026  |  **Branch:** `claude/beautiful-mendel`

## Ausgangslage (Ist-Zustand, ohne Fix)

### `price_lookup.py` — Stage-2c-Flow

- Konstante: `FUZZY_MATCH_THRESHOLD = 0.85` (Zeile 46)
- Stage 2c (Zeile 334–346) filtert nach Unit (`unit_matches`) + ggf.
  Hersteller, ruft dann `_best_fuzzy(...)` auf.
- `_best_fuzzy(...)` (Zeile 618–650) nutzt
  `material_normalizer.score_query_against_candidate` (Import mit
  SequenceMatcher-Fallback). Score ist Anteil der Query-Tokens, die
  auch im Kandidaten-Text vorkommen, normiert auf [0 … 1].
- Unterhalb 0,85 → Stage 4 (`estimated`) oder `not_found`.

### `material_normalizer.py` — Token-Coverage

- `normalize_product_name()` (Zeile 97): lowercase, Artikel-Nummern
  raus, Dezimal-Komma → Punkt, `2000x1250x12,5` wird via
  `_DIM_X_RE` in **getrennte Tokens** zerlegt (`2000 1250 12.5`),
  `mm`-Einheit wird entfernt.
- `normalize_dna_pattern()` (Zeile 154): splittet am `|`, verwirft
  Kategorie, joint die Reste mit `normalize_product_name`. Für
  Pattern `"|Profile|CW75|"` entsteht der Text **`"cw75"`** — ein
  **einzelnes Token**.
- `score_query_against_candidate(query, candidate)` (Zeile 220+):
  asymmetrische Token-Set-Coverage, Query vs. Candidate.

### `materialrezepte.py` — DNA-Pattern für Profile

Aktuelle Pattern haben **Dimension und Typ verschmolzen**:

```
|Profile|CW75|          -> produktname="CW75"
|Profile|UW75|          -> produktname="UW75"
|Profile|CW100|         -> produktname="CW100"
|Profile|UW100|         -> produktname="UW100"
|Profile|CW50|          -> produktname="CW50"
|Profile|CD60/27|       -> produktname="CD60/27"
|Profile|UA|50|         -> produktname="UA", abmessungen="50" (anders!)
```

**Inkonsistent:** UA-Profile haben die Dimension als **separates
Pipe-Feld** (`|Profile|UA|50|`), CW/UW/CD haben sie **mit dem Typ
verschmolzen** (`|Profile|CW75|`).

In `kalkulation._resolve_material_via_lookup` (Zeile 66–72) wird der
`material_name` als `f"{produktname} {abmessungen} {variante}".strip()`
gebildet. Für UA kommt sauber `"UA 50"` heraus, für CW kommt nur
`"CW75"`.

## Kemmler-Katalog-Realität (04/2026, 327 Entries)

Alle CW/UW/UA-haltigen Einträge:

| product_name | unit | price_net | category |
|---|---|---|---|
| Anschlusswinkel f. UA-Profil 100 mm - Nr. 00708451 | €/Paket | 15,65 | Unterkonstruktion |
| Anschlusswinkel f. UA-Profil 48 mm - Nr. 00708449 | €/Paket | 15,13 | Unterkonstruktion |
| **CW-Profil 100x50x0,6 mm BL=2600 mm 8 St./Bd.** | **€/m** | **167,40** | Trockenbauprofile |
| TP100 Türpfosten-Steckwinkel f. 100 mm CW/UA-Prof | €/Satz | 11,10 | Unterkonstruktion |
| TP50 Türpfosten-Steckwinkel f. 50 mm CW/UA-Prof | €/Satz | 10,41 | Unterkonstruktion |
| TP75 Türpfosten-Steckwinkel f. 75 mm CW/UA-Prof | €/Satz | 11,62 | Unterkonstruktion |
| (zusätzlich: 9 Aquapanel-Einträge mit „AquaPanel …" — keine Profile) |

**Befund:**

- **Nur 1 echter CW-Profil-Eintrag** im gesamten Kemmler-Katalog:
  `CW-Profil 100x50x0,6 mm BL=2600 mm 8 St./Bd.` (EUR 167,40 €/m,
  Bundle 8 St./Bund — der Preis ist vermutlich der Bundle-Preis, nicht
  der Laufmeter-Preis; separate Analyse).
- **Null UW-Profil-Einträge** (weder 50, 75, noch 100).
- **Zwei UA-Anschlusswinkel** (48 mm, 100 mm) — Meta-Artikel zur
  Verstärkung, nicht die tragenden CW/UW-Profile selbst.
- **Drei TP-Türpfosten-Steckwinkel** (50/75/100) — enthalten den
  String „CW" im Produktnamen, sind aber **Türpfosten**, keine Profile.

**Produkt-Implikation:** Selbst ein perfekter Matcher-Fix kann für
UW-Profile und CW-75 / CW-50 aus diesem Katalog keinen Treffer
liefern. Das Katalog-Lücken-Problem ist real und muss separat gelöst
werden (UI-Anzeige „Fehlt im Katalog" + ggf. zusätzliche Preislisten).

## Matcher-Bug — Concrete Trace

### Fall A: CW-100 gegen den echten Kemmler-Eintrag

| Schritt | Wert |
|---|---|
| DNA-Pattern (Rezept) | `"|Profile|CW100|"` |
| `normalize_dna_pattern` → | `"cw100"` (ein Token) |
| `material_name` in `lookup_price` | `"CW100"` |
| `normalize_product_name("CW100")` → | `"cw100"` |
| q_tokens | `{cw100}` |
| Candidate (Kemmler) | `"CW-Profil 100x50x0,6 mm BL=2600 mm 8 St./Bd."` |
| `normalize_product_name(...)` | `"cw profil 100 50 0.6 8"` |
| c_tokens | `{cw, profil, 100, 50, 0.6, 8}` |
| Schnittmenge | `{}` — **cw100 steht nicht in c_tokens** |
| Score | **0 %** |
| Ergebnis | Stage 2c fails → Stage 4 (`estimated`) |

### Fall B: CW-75 gegen den echten Kemmler-Eintrag

Identische Analyse, q_tokens `{cw75}`, c_tokens `{cw, profil, 100, 50, 0.6, 8}`.
Schnittmenge leer, Score 0 %. **Gewünscht:** kein Match (es ist nicht
das 75er Profil). Aktuell: fällt trotzdem auf Stage 4 zurück.

### Fall C: UA-50 (zum Vergleich — funktionierendes Pattern)

| Schritt | Wert |
|---|---|
| DNA-Pattern | `"|Profile|UA|50|"` (Dimension als eigenes Feld) |
| `normalize_dna_pattern` → | `"ua 50"` (zwei Tokens) |
| Candidate „Anschlusswinkel f. UA-Profil 48 mm …" | `"anschlusswinkel f. ua profil 48"` |
| q_tokens | `{ua, 50}` |
| c_tokens | `{anschlusswinkel, f., ua, profil, 48}` |
| Schnittmenge | `{ua}` (50 ≠ 48) |
| Score | 50 % — **unter Threshold**, aber Struktur stimmt |

Pattern mit **getrennten** Typ-/Dimensionstokens verhält sich bereits
korrekt — es findet echte Teil-Treffer. Pattern mit **verschmolzenen**
Tokens (`cw75`) liefert IMMER 0 %.

## Planung für Test-Cases (Phase 2)

Datei: `tests/unit/matcher/test_cw_uw_matching.py`

| # | Pattern | Kandidaten | Erwartung |
|---|---|---|---|
| 1 | CW 100 | `["CW-Profil 100x50x0,6 mm BL=2600 mm"]` | Stage 2c, score ≥ 0,85 (Happy Path) |
| 2 | CW 75 | `["CW-Profil 100", "CW-Profil 75", "UW-Profil 75"]` (synth.) | `CW-Profil 75` gewinnt |
| 3 | CW 75 | `["TP75 Türpfosten-Steckwinkel"]` | Score < 0,85 (False-Positive-Schutz) |
| 4 | CW 75 | `["CW-Profil 100", "UW-Profil 100"]` | Kein Match (echte Katalog-Lücke) |

Alle 4 Tests müssen **auf dem aktuellen Code rot sein**, bevor der
Fix kommt.

## Fix-Richtung (Phase 3)

1. **`materialrezepte.py`** — alle CW/UW/CD-Pattern umschreiben von
   `|Profile|CW75|` auf `|Profile|CW|75|` (analog UA-Pattern).
   Backward-Kompatibilität: keine — diese Pattern werden nur vom
   internen Matcher gelesen, kein externer Konsument.

2. **`material_normalizer.fuzzy_match_score` / `score_query_against_candidate`** —
   erweitern um **Dimensions-Matching-Bonus**: wenn das Pattern eine
   numerische Dimension enthält (z. B. `75`, `100`), und der Kandidat
   ebenfalls einen numerischen Token hat, fließt die Übereinstimmung
   zusätzlich gewichtet ein. Exakte Gewichtung (50 % Typ / 30 % Dim /
   20 % Textual Similarity) wird im Fix-Commit festgelegt.

3. **Garantie für existierende Tests:** 343 bestehende Tests (inkl.
   Normalizer-Fixtures in `kemmler_real_names.json`) müssen grün
   bleiben. Strategie: neue Logik **additiv**, nicht substituierend.

## Abhängigkeiten / Risiken

- `_parse_dna_pattern` in `kalkulation.py` splittet am `|` und hat
  das Schema `[hersteller, kategorie, produktname, abmessungen,
  variante]`. Pattern-Wechsel von 4→5 Pipe-Delimitern ist abwärts-
  kompatibel, solange `abmessungen`-Feld korrekt benutzt wird.
- `dna_matcher.py` (Legacy-Pfad) nutzt dieselben Pattern. Muss
  gegengelesen werden — wenn er die verschmolzenen Tokens erwartet,
  wird der Legacy-Pfad brechen, sobald Patterns geändert werden.

## Baseline-Messung

| Position aus E2E-Lauf 21.04. morgen | CW/UW-Material-Zeilen | Stage |
|---|---|---|
| W112/W116/W625/W628A/W630/W635/D112 etc. | jeweils 2 (CW + UW) | Alle `estimated` (Stage 4) |
| **Summe Stage-4-Einträge** (laut e2e_multi_supplier_2026_04_21.md) | **70 Material-Zeilen** | — |

Ziel nach Fix: CW-100-Fälle gehen auf Stage 2c (`supplier_price`),
CW-50/75 und alle UW bleiben `estimated` (Katalog-Lücke).
