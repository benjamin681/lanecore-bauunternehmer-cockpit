# Abschluss B+4.2.6 + B+4.2.7 — Option C

**Datum:** 22.04.2026
**Remote-HEAD nach erstem Push:** `e5d150d`
**Tests:** 389 grün
**Branch:** `claude/beautiful-mendel` (gepusht)

## Gelöste Blocker

### B+4.2.6 — UT40-Regression

Die PE-Folien-Regression aus dem Matcher-Fix vom 21.04. wurde über
**Option C** aufgelöst: parser-seitige strukturelle Produktcode-
Extraktion (`attributes.product_code_type/dimension/raw`) plus ein
kleiner, chirurgischer Blacklist-Pre-Filter in Stage 2c. Blacklist
`{UT}` — minimal-invasiv, nur bei konkretem Regressions-Fall mit
Golden-Test erweiterbar.

Wichtigste Befunde:

- Kemmler 04/2026 hat null echte CW/UW/UA-Codes im Extraktions-
  Sinn; der Hauptwert der Extraktion liegt in den Nicht-Whitelist-
  Codes, die jetzt sauber vom Fuzzy-Pool abgegrenzt werden.
- CW-Profil-Fuzzy-Fallback bleibt erhalten — der Kemmler-CW-Entry
  „CW-Profil 100x50x0,6 mm" matcht weiterhin über den klassischen
  Fuzzy-Score wie bei B+4.2.6.
- Der Blacklist-Pre-Filter läuft *vor* dem Scoring, spart Rechenzeit
  und verhindert zufällige High-Score-Gewinne durch Schatten-
  Kandidaten.

### B+4.2.7 — Bundle-per-Length + Backfill

- `resolve_pieces_per_length` entpackt €/m-Bundle-Preise (CW-Profil
  167,40 → 8,05 €/m).
- Worker-Integration: `backfill_effective_units` läuft nach jedem
  Parse.
- Backfill auf bestehende Kemmler-Liste: 80 Entries korrigiert
  (11 Pfad B neu + 69 Pfad A technische Schuld).
- E2E-Material netto am 21.04. abends: 204 k € (−62 % vs. nur
  B+4.2.6-Stand von 536 k €).

### Option-C-Parser-Extraktion

- `product_code_extractor.extract_product_code(name)` als pure
  Python-Funktion, deterministisch, ohne API-Call.
- Integration in `pricelist_parser._build_entry`.
- Backfill-Skript `scripts/backfill_product_codes.py` hat 126
  Kemmler-Entries nachträglich mit `product_code_*` ausgestattet.

## Stuttgart-LV-Baseline nach allen Fixes

| Metrik | Wert |
|---|---|
| Material netto (bindend) | **134.278 €** |
| Angebotssumme netto | **975.267 €** |
| Positionen gesamt | 102 |
| Positionen EP > 0 | 77 |
| needs_price_review | 78 |
| supplier_price Matches (Material-Zeilen) | **118** |
| estimated (Stufe 4) | 62 |
| not_found | 64 |

Das entspricht einer realistischen Stuttgart-Trockenbau-Angebotssumme
im niedrigen Millionenbereich — ohne künstliche Preis-Explosion und
ohne Unterschätzung durch Richtwerte.

## Meilenstein in Zahlen (seit Baseline-Morgenstand 21.04.)

| Messgröße | Morgen 21.04. | Jetzt 22.04. | Δ |
|---|---|---|---|
| supplier_price Matches | 95 | 118 | +23 |
| not_found | 79 | 64 | −15 |
| Material netto | 122.666 € | 134.278 € | +11.612 € |
| Angebotssumme | 959.558 € | 975.267 € | +15.709 € |
| Backend-Tests | 349 | 389 | +40 |

## Nächste Schritte für Planungs-Session

### B+4.3.1 Frontend-Erweiterung
- **Near-Miss-Drawer** für jede Position (Top-3-Kandidaten aus dem
  Matcher-Pfad anzeigen, neuer Endpoint `GET /lvs/{id}/positions/
  {pos_id}/candidates`).
- **Manual-Override-UI** inkl. optionaler Persistenz als
  `TenantPriceOverride`.
- **Katalog-Lücken-Report** (Tab oder Sidebar): Liste der
  Positionen mit `needs_price_review`, gruppiert nach System.
- **Wording-Migration** gemäß `lv-preisrechner/docs/ui_wording_guide.md`
  (Stage-Badges: „Preis gefunden" / „Ähnlicher Artikel" / „Richtwert"
  / „Fehlt im Katalog").

### Deployment + Pilot
- **Hetzner-Deployment-Setup** (Backend + Frontend + DB).
- **Pilot-Onboarding-Materialien** (Leitfaden, Kurzvideo,
  Kalkulations-Template für Yildiz / Bau-Cockpit).

### Technik-Follow-ups (niedrigere Priorität)
- Tenant-/supplier-spezifische Blacklist-Erweiterung (Hornbach/
  Wölpert bringen ggf. neue Suffix-Codes mit).
- Ein weiterer E2E-Run direkt nach Pilot-Onboarding mit echtem
  Kunden-LV (nicht Stuttgart-Synthetik).
