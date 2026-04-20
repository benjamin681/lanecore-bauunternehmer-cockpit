# Live-Tests (manuell, nicht in CI)

Dieser Ordner ist fuer **manuelle Live-Tests mit echten Daten**.

## Konventionen

- PDFs, JSONs, Logs werden **nie eingecheckt** (siehe `.gitignore`).
- Nur Skripte / Runner werden versioniert.
- Jeder Live-Test legt seine DB in `live_db/` (lokal) an und raeumt nach.

## Skripte

### `test_kemmler_parse.py`

Simuliert den kompletten Upload + Parse-Flow fuer eine echte Kemmler-Preisliste.

**Usage:**

```bash
# PDF vorher lokal ablegen (nicht committed):
cp ~/Downloads/kemmler_ausbau_neu_ulm_2026_04.pdf lv-preisrechner/tests/live/

# Vom backend-Verzeichnis aus:
cd lv-preisrechner/backend
.venv/bin/python ../tests/live/test_kemmler_parse.py ../tests/live/kemmler_ausbau_neu_ulm_2026_04.pdf

# Oder via ENV-Var:
KEMMLER_PDF_PATH=../tests/live/kemmler_ausbau_neu_ulm_2026_04.pdf \
  .venv/bin/python ../tests/live/test_kemmler_parse.py
```

**Output:**
- Report mit Parsed/Skipped/Needs-Review-Counts
- Confidence-Histogramm in 10er-Buckets
- Top-Hersteller, Top-Einheiten
- Beispiel-Eintraege High/Low-Confidence
- Geschaetzte API-Kosten + Laufzeit

**Kosten:** ~0,30 USD fuer eine 24-seitige Preisliste (Claude Sonnet 4.6 Vision).
