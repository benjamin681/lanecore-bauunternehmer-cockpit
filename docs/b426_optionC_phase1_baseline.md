# B+4.2.6 Option C — Phase 1: Baseline & Schema-Design

**Stand:** 21.04.2026 (End-of-Day III) | **Scope:** Parser-seitige
strukturelle Produktcode-Extraktion. Matcher bleibt unverändert.

## Aktueller Zustand

### `attributes`-Schema (SupplierPriceEntry)

- Typ: `Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)`
- Aktueller Inhalt (durch `generic_parser_prompt` + Parser-Logik gesetzt):

| Key | Quelle | Semantik |
|---|---|---|
| `raw_price` | Prompt | Originalpreis vor Auto-Korrektur |
| `price_unit_code` | Prompt | E/Z/H/T-Code von Wölpert-artigen Listen |
| `list_price` | Prompt | Listenpreis vor Rabatt |
| `discount_pct` | Prompt | Rabatt-Prozent |
| `validation_warning` | Prompt | Plausibilitäts-Flag (`FACTOR_100_SUSPECTED` etc.) |
| `auto_corrected` | Prompt | `True` wenn der Parser den price_net selbst korrigiert hat |

Neu geplante Keys aus Phase 1 sind **additiv**; keine Kollision mit den
bestehenden.

### Parser-Prompt-Struktur

`app/prompts/generic_parser_prompt.py` (323 Zeilen) gliedert sich in:

1. Rolle + Aufgabe (deutscher Baumarkt-Preislisten-Experte)
2. JSON-Schema-Vorgabe
3. Einheiten-Regeln (1–7)
4. Code-Einheiten-Auflösung (H/T/Z/E)
5. Rabatt-Extraktion
6. Plausibilitäts-Validierung
7. Gebinde-Einheiten
8. Attribute-Felder (`dimensions`, `thickness`, `packaging`, …)

Für Phase 1b wird ein **neuer Block „PRODUKTCODE-EXTRAKTION"** oberhalb
des `attributes`-Blocks eingefügt. Semantische Erklärungen im Prompt
bleiben bewusst knapp (der Prompt-Ballast ist bereits hoch; Claude soll
nur den `attributes`-Teil erweitern).

## Design-Entscheidung: Python-Post-Processor, nicht LLM

Die Extraktion eines Produktcode-Musters wie `[A-Z]{2,3}\d+(?:/\d+)?`
aus einem Produktnamen ist ein **regelbasiertes Problem**. Wir brauchen
keine semantische Inferenz über Mehrdeutigkeit, Kontext oder Bedeutung
— wir brauchen nur eine konsistente Tokenisierung. Deshalb:

| Option | Begründung | Entscheidung |
|---|---|---|
| **LLM extrahiert in attributes** | flexibler bei neuen Formaten, aber nicht testbar ohne API-Call, LLM-Drift, zusätzliche Token im Prompt | **Nein** |
| **Python-Post-Processor** (Regex, läuft nach `_build_entry`) | deterministisch, 100 % Unit-getestet, keine API-Kosten, rückwirkend auf bestehende Entries anwendbar via Backfill | **Ja** |

Die Funktion wird:
- als pure Funktion in `app/services/product_code_extractor.py` leben,
- im `_build_entry` nach der Attribut-Übernahme aufgerufen,
- die neuen Keys in `attributes` hinzufügen, **falls ein Code erkannt
  wurde** (sonst bleibt der Dict unverändert).

**Prompt-Konsequenz:** Der Prompt wird **nur informell** um einen
Hinweis erweitert, dass Produktcodes separat extrahiert werden und der
Parser sie nicht in `attributes` duplizieren muss. Das hält den Prompt
schlank; der Post-Processor macht die eigentliche Arbeit.

## Ziel-Schema

Neue Keys in `attributes` (nur gesetzt, wenn erkannt):

| Key | Typ | Beispiel | Beschreibung |
|---|---|---|---|
| `product_code_type` | str | `"CW"` | 2–3-Buchstaben-Prefix (Großbuchstaben) |
| `product_code_dimension` | str | `"75"`, `"60/27"` | Numerischer Teil, optional mit `/` |
| `product_code_raw` | str | `"CW75"` | Kompakte Form, Grossbuchstaben, Bindestriche/Leerzeichen entfernt |

**`raw`-Format:** **kompakt ohne Trennzeichen (`CW75` statt `CW-75`)**.
Begründung: das ist die Form, die der Matcher beim Lookup erwartet, und
sie erlaubt einen O(1)-Equality-Check zwischen Query-Code und Katalog-
Code ohne zusätzliche Normalisierung.

## Beispiele mit erwarteter Extraktion

| Produktname | type | dimension | raw | Bemerkung |
|---|---|---|---|---|
| `CW-Profil 100x50x0,6 mm BL=2600 mm 8 St./Bd.` | `CW` | `100` | `CW100` | Bindestrich wird weggekürzt |
| `CW 75x50x0,6 mm` | `CW` | `75` | `CW75` | Leerzeichen-getrennt |
| `Trennwandpl. Sonorock WLG040, 1000x625x40 mm` | `WLG` | `040` | `WLG040` | ¹ |
| `PE-Folie S=0,20 mm - 4000 mm x 50 m/Ro. farbstichig - UT40` | `UT` | `40` | `UT40` | Suffix-Code wird als Typ behandelt — bewusst, die Semantik entscheidet der Matcher |
| `Baumit Multicontact 25 kg/Sack` | — | — | — | Kein Pattern `[A-Z]{2,3}\d+` |
| `Kemmler KKZ30 Kalkzementputz 30 kg/Sack` | `KKZ` | `30` | `KKZ30` | |
| `Kemmler SLP30 Styroporleichtputz 30 kg/Sack` | `SLP` | `30` | `SLP30` | |
| `Knauf MP75 Leichtputz` | `MP` | `75` | `MP75` | |
| `TP75 Türpfosten-Steckwinkel f. 75 mm CW/UA-Prof` | `TP` | `75` | `TP75` | Typ = **erstes Vorkommen**, nicht „das prominentere CW" |
| `ASA01 Ankerschnellabhänger für CD-Profil - 60/27 - 100 Stk/Ktn.` | `ASA` | `01` | `ASA01` | Auch „ASA01"-Code trifft |

¹ **Entscheidung für beschreibende Codes (WLG040):** auch die Wärmeleit-
Gruppen-Codes erfüllen das Muster `[A-Z]{2,3}\d+` und werden extrahiert.
Der Matcher morgen wird über `product_code_type IN whitelist` filtern,
welche Codes für Matching relevant sind (CW/UW/UA/CD/UD/KKZ/SLP/MP) und
welche ignoriert werden (WLG = Wärmeleitgruppe, keine Matching-Relevanz).

## Kern-Regeln für den Extraktor

1. **Basis-Regex:** `[A-Z]{2,3}\d+` (Typ = 2–3 Großbuchstaben, direkt
   gefolgt von Zahlen). **Keine Spezialbehandlung von `/27`-Suffixen**
   (siehe Trade-off unten).
2. **Trennzeichen-Toleranz:** vor dem Regex-Match werden im Produktnamen
   `-` und `_` zwischen Alpha und Digit entfernt; `"CW-75"` und
   `"CW_75"` werden somit beide zu `CW75`. Leerzeichen bleiben
   **erhalten** (Trennung erfolgt bei Wort-Grenzen) — aber der Regex
   matcht auch `CW 75`, wenn die Leerstelle zwischen Alpha-Token und
   Digit-Token trivial überbrückbar ist (siehe Implementierung).
3. **Erstes Vorkommen gewinnt** — bei mehreren Matches im Namen.
4. **Kein Match → Keys fehlen in `attributes`** (nicht `None`, nicht
   leerer String).

### Design-Trade-off: CD60/27 wird auf CD60 verkürzt

Kemmler-Pattern wie `CD60/27` (Metrik: 60 mm Kopf, 27 mm Steg) werden
vom Extraktor bewusst auf `type="CD"`, `dimension="60"`, `raw="CD60"`
verkürzt. Der `/27`-Teil fällt weg.

**Begründung:**

- Der Regex bleibt einfach (`[A-Z]{2,3}\d+`, kein optionales
  `(?:/\d+)?`-Tail).
- Der Matcher-Lookup morgen kann ohne `/27`-Genauigkeit funktionieren:
  `CD60` reicht als Typ-Identifier, die genaue CD-Variante liest der
  Matcher aus `package_size`/`package_unit` oder der Produktbeschreibung
  nach, wenn tatsächlich Bedarf besteht.
- In der Praxis liefert Kemmler nur einen CD-Profil-Typ (CD 60/27), es
  gibt keine konkurrierenden Varianten wie `CD 50/27` oder `CD 60/30`.
  Der Information-Verlust ist produktseitig unproblematisch.

**Wenn später doch gebraucht:** Matcher kann bei Bedarf aus
`package_size` (z. B. 2,6 m) oder einer Regex-Nachlese auf dem
Produktnamen den `/27`-Suffix rekonstruieren. Heute: nicht nötig, nicht
gebaut.

## Edge-Cases für die Test-Suite (Phase 1c)

- Leerer String, nur Leerzeichen → kein Match.
- Nur Zahlen (`30`, `12.5`) → kein Match.
- Sehr langer Code (`DIAMANTI1000`) → Typ muss ≤ 3 Zeichen sein → match
  `DIA` + `MANTI1000`? **Nein.** Regex `[A-Z]{2,3}\d` erzwingt, dass
  nach 2–3 Großbuchstaben **direkt** eine Zahl kommt. `DIAMANTI1000`
  scheitert, weil nach `DIA` ein `M` folgt.
- Kleinbuchstaben (`cw75`) → kein Match (Regex erzwingt Großbuchstaben).
- Code mit Dezimalpunkt (`W3.0`) → wird nicht gematcht (Punkt im
  Number-Teil), bewusst — das ist keine Trockenbau-Profil-Dimension.
- Umlaute im Präfix (`Ö30`) → kein Match (Regex zielt auf ASCII-A–Z).

## Scope-Begrenzung für Phase 1

- ✗ Keine Matcher-Änderung (`material_normalizer.py` unberührt).
- ✗ Kein Re-Parse der Kemmler-Liste (API-Kosten vermeiden).
- ✗ Kein Backfill-Skript auf bestehende Entries. Die neuen Keys
  erscheinen nur in **zukünftig geparsten** Entries. Für bestehende
  Entries kommt ein Backfill-Schritt in Phase 2 (morgen), wenn der
  Matcher darauf umgestellt ist.
- ✓ Parser-Prompt erweitert (informell, kein semantischer Konflikt).
- ✓ Python-Post-Processor mit Unit-Tests.
- ✓ Integration in `_build_entry` (nach Attribut-Übernahme).

## Nächste Phasen

- **Phase 1b:** Parser-Prompt-Änderung (nur informell), Post-Processor-
  Modul, Integration in `_build_entry`.
- **Phase 1c:** 15–20 Unit-Tests gegen die Extraktor-Funktion. Alle 362
  bestehenden Tests bleiben grün.
- **Phase 2** *(morgen)*: Matcher liest `attributes.product_code_*`
  statt verschmolzene Tokens. `_explode_alnum` kann abgeschaltet oder
  auf Whitelist reduziert werden. PE-Folie-UT40-Regression löst sich,
  weil der Matcher Typ-Codes aus einer Whitelist liest (`UT` ist nicht
  drin).
