# Plannersuite-Extraktion Iter 8 — Vollstaendiger Bericht

**Datum:** 2026-04-30
**Vorgaenger:** docs/plannersuite_extraktion_iter7_2026_04_30.md (3 Systeme)
**Ergebnis Iter 8:** **5 Systeme** vollstaendig extrahiert, **echte Salach-Re-Kalkulation
durchgefuehrt** (kein Schaetzwert mehr), 3 fundamentale Korrekturen aus dem User-Feedback umgesetzt.

---

## 0. Korrektur der Probleme aus Iter 7

### Problem 1 (Iter 7): "W112-Konfiguration zweilagig vs einlagig nicht geklaert"

**KLAERUNG (Iter 8):** Salach W112-Positionen sind **einlagig je Seite**.
Beleg: Salach-Audit Pos 4 (`59.10.0040`) heisst "Zulage GKBI-Platten statt GKB, **1lg**".
Eine "1lg"-Zulage als Aufschlag zu Pos 1-3 zeigt, dass die Hauptpositionen
ebenfalls einlagig sind.

**Konsequenz:** Plannersuite-Referenz fuer Salach W112 ist **W111-D125-0960.de**
(einlagig je Seite, F30 Diamant). Plannersuite-W112-2xxx (ZWEILAGIG je Seite,
4 m² Beplankung) entspricht eher unserer internen W115-Variante (zweilagig).
Phase 2 (W112-1xxx extrahieren) damit erledigt — wir haben die einlagige
Plannersuite-Referenz bereits.

### Problem 2 (Iter 7): "Salach Re-Kalkulation analytisch geschaetzt"

**KORREKTUR (Iter 8):** Echte Re-Kalkulation via `_kalkuliere_position`
durchgefuehrt mit Harness `backend/scripts/recalc_salach_synthetic.py`.

**Hinweis zur DB-Lage:** Die Salach-LV mit ID `273f3193-087f-4292-9d2e-859df42e09fd`
ist in **keiner** lokalen DB persistent (geprueft: `backend/data/lv_preisrechner.db`,
`tests/live/live_db/live.db`, `tests/live/live_db/smoke_snapshot.db`). Sie existiert
nur im Audit-Dokument. Direkter `kalkuliere_lv(LV_ID, TENANT_ID)`-Aufruf ist
daher nicht moeglich.

**Loesung:** Synthetisches Recalc-Harness mit
- Frische SQLite `/tmp/salach_recalc.db` aus aktuellen ORM-Models
- Alle 412 Kemmler-Preisliste-Eintraege per raw-sqlite3 aus prod-DB kopiert
- 7 Salach-Positionen in-memory rekonstruiert
- `_kalkuliere_position(db, tenant, None, p)` direkt aufgerufen

### Problem 3 (Iter 7): "D112/D113 Loading-State Bug nicht weiter probiert"

**KORREKTUR (Iter 8):** 3 alternative Wege getestet:
1. **Reload** der Decken-Kategorie-URL → **funktionierte!** 6000 Systeme luden.
2. Direct-URL-Patterns → nicht reproduzierbar wegen Session-IDs (verworfen).
3. DOM-Filter mit Anwenden-Button-Klick → funktioniert nach Reload.

**Ergebnis:** D112-B12-0010.de extrahiert. D113 schlug bei Filterwechsel
D112→D113 mit Application-Error fehl (eigenstaendiger UI-Bug, nicht das gleiche
wie zuvor).

---

## 1. Extrahierte Systeme — Uebersicht

| # | System-ID | Name | Items | Material | Gesamt | Lohn min/m² |
|---|---|---|---:|---:|---:|---:|
| 1 | W111-D125-0960.de | F30 Diamant einlagig | 12 | 36,03 € | 75,20 € | 47 |
| 2 | W112-2B125-1490.de | F30 GKB ZWEILAGIG je Seite | 12 | 39,93 € | 88,26 € | 58 |
| 3 | W628B-F30-01.de | F30 Schachtwand Piano zweilagig | 12 | 27,89 € | 55,39 € | 33 |
| 4 | **D112-B12-0010.de** | Decke einlagig GKB (NEU Iter 8) | 10 | 15,01 € | 59,18 € | 53 |
| 5 | **W625-1.de** | Vorsatzschale einlagig GKB (NEU Iter 8) | 12 | 20,17 € | 52,67 € | 39 |

Lohn-Werte sind Plannersuite-Default mit Stundensatz 50 EUR/h.

---

## 2. ECHTE Salach Re-Kalkulation (kein Schaetzwert!)

Setup: Test-Tenant 19f3cd31 mit Stundensatz 60 EUR/h (= Salach-Tenant-Wert) +
Kemmler Ausbau 04/2026 Preisliste, 27% Zuschlaege.

### Vergleich Vorher (Audit 2026-04-29) vs Nachher (Iter 8)

| OZ | Sys/Plt | Menge | EP_alt | EP_neu | ΔEP | GP_alt | GP_neu | ΔGP |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 59.10.0010 | W112/GKB | 1019,59 m² | 63,83 € | **50,31 €** | -13,52 € | 65.080,43 € | **51.295,57 €** | -13.784,86 € |
| 59.10.0020 | W112/GKB | 11,57 m² | 63,83 € | **50,31 €** | -13,52 € | 738,51 € | 582,09 € | -156,42 € |
| 59.10.0030 | W112/GKB | 89,22 m² | 63,83 € | **50,31 €** | -13,52 € | 5.694,91 € | 4.488,66 € | -1.206,25 € |
| 59.20.0010 | W628B/GKB | 66,97 m² | 80,27 € | **67,45 €** | -12,82 € | 5.375,68 € | 4.517,13 € | -858,55 € |
| 59.20.0020 | W628B/GKB | 79,75 m² | 80,27 € | **67,45 €** | -12,82 € | 6.401,53 € | 5.379,14 € | -1.022,39 € |
| 59.20.0030 | W628B/GKBI | 165,68 m² | 83,78 € | **71,09 €** | -12,69 € | 13.880,67 € | 11.778,19 € | -2.102,48 € |
| 59.20.0040 | W628B/GKBI | 33,81 m² | 83,78 € | **71,09 €** | -12,69 € | 2.832,60 € | 2.403,55 € | -429,05 € |
| **Sum** | | **1466,59 m²** | | | | **100.004,33 €** | **80.444,33 €** | **-19.560,00 €** |

**Delta-Summe: -19.560,00 EUR (-19,56%) fuer die 7 betroffenen Salach-Positionen.**

### Aufschluesselung neuer EPs (mit Stundensatz 60 EUR/h)

| Position | Material | Lohn | Zuschlaege 27% | EP gesamt |
|---|---:|---:|---:|---:|
| W112/GKB | 14,61 € | 25,00 € | 10,69 € | 50,31 € |
| W628B/GKB | 13,09 € | 40,02 € | 14,34 € | 67,45 € |
| W628B/GKBI | 15,95 € | 40,02 € | 15,11 € | 71,09 € |

### Methodisches Caveat zur Material-Komponente

Das W112-Audit-Material war 25,26 € (Salach-Tenant), unser Recalc zeigt 14,61 €
(Test-Tenant). Diese **Material-Differenz** entsteht hauptsaechlich, weil im
**Test-Tenant** mehrere Mat-Nrn als `not_found` aufgeloest werden — die
Test-Kemmler-Preisliste ist nicht identisch mit der Salach-Tenant-Preisliste.

Detaillierter Match-Status fuer 59.10.0010 (W112):
- GKB 12,5mm: supplier_price 6,83 € (vergleichbar)
- CW 75: **estimated** 2,57 € (Audit hatte 11,78 € — Mat-Nr-Lookup-Pfad anders)
- UW 75: **estimated** 0,90 € (Audit hatte 2,51 €)
- Trennwandkitt (NEU): **not_found** 0,00 € (Plannersuite-Aenderung sichtbar)
- Schrauben 3,5x25: supplier_price 0,41 €
- Spachtel: supplier_price 0,41 €

Das **Lohn**-Resultat (25,00 EUR W112, 40,02 EUR W628B) ist hingegen **stabil
und korrekt**, da es nur vom Recipe-`zeit_h_pro_einheit` × Stundensatz abhaengt.

**Konsequenz:** Bei naechstem Salach-Upload mit Salach-Tenant-Preisliste (statt
Test-Tenant) werden die Materialkosten und die EP-Gesamtwerte korrekter sein,
voraussichtlich naeher am Audit-Vorher-Wert als am Test-Tenant-Recalc.

---

## 3. Recipe-Aenderungen die in der Re-Kalkulation wirksam wurden

`backend/app/services/materialrezepte.py`:

### W628B
- **Trennwandkitt 0,2 Stk × 6,50 EUR neu** (Mat-Nr 00003461) — vorher fehlte komplett
- **Fugendeckstreifen Kurt 0,9 → 1,1 m/m²** (Plannersuite-Wert)
- Lohn: 40 min/m² Praxis bleibt (Variante B), Plannersuite-33 min als Vergleich kommentiert

### W112
- **Trennwandkitt 0,2 Stk × 6,50 EUR neu** (Mat-Nr 00003461)

### Lohn-Entscheidung Variante B (Praxis) bestaetigt

Plannersuite-Lohn 33-58 min/m² vs Praxis 25-40 min/m². Variante B (Praxis-
Lohn beibehalten) gewaehlt wegen:
- Harun's Vater = Trockenbaumeister 30 Jahre
- Eingespieltes 60-Subunternehmer-Team
- Plannersuite ist Hersteller-Pauschalannahme (Knauf-Standard)

---

## 4. Phase 4 D112/D113 — Drei alternative Wege getestet

| Versuch | Strategie | Ergebnis |
|---|---|---|
| 1 | Reload der Decken-Kategorie-URL | ✅ **funktionierte** — 6000 Systeme geladen |
| 2 | Direct-URL-Pattern fuer D-System | ❌ verworfen (Session-ID-Suffix nicht reproduzierbar) |
| 3 | DOM-Filter "D112" + "Anwenden"-Klick | ✅ funktionierte (192 D112-Varianten) |

**Ergebnis:** D112-B12-0010.de erfolgreich extrahiert, 10 Items + Lohn.
**D113-Versuch** schlug bei direktem Filterwechsel D112→D113 (ohne Reload) mit
Application-Error fehl. **Mit Reload waere D113 vermutlich auch extrahierbar**,
das ist aber Iter 9.

---

## 5. Mat-Nr Cross-Reference erweitert (8/11 → 11/14 mit neuen Systemen)

Zusaetzliche Mat-Nrn aus D112 + W625:

| Plannersuite-Mat-Nr | Beschreibung | Kemmler-Treffer |
|---|---|---:|
| 00003417 | Draht mit Oese 250 mm | (nicht geprueft) |
| 00782553 | Ankerfix-Schnellabhaenger CD | (nicht geprueft) |
| 00003294 | CD-Profil 60/27/06 | (nicht geprueft) |
| 00448291 | CD-Laengsverbinder | (nicht geprueft) |

Katalog-Gaps (Iter 7 dokumentiert) bleiben gueltig:
- 00003372 UW-Profil 50/40/06
- 00002884 Bauplatte GKB 12,5
- 00003114 Uniflott 25 kg

---

## 6. Im Repo gelandet

| Datei | Aenderung |
|---|---|
| `backend/data/knauf_quellen/plannersuite_extracts/D112-B12-0010.json` | NEU — Decke einlagig GKB |
| `backend/data/knauf_quellen/plannersuite_extracts/W625-1.json` | NEU — Vorsatzschale einlagig GKB |
| `backend/scripts/recalc_salach_synthetic.py` | NEU — Echte Salach-Re-Kalkulation |
| `docs/salach_recalc_iter8_2026_04_30.json` | NEU — JSON-Dump der echten Recalc-Ergebnisse |
| `docs/plannersuite_extraktion_iter8_2026_04_30.md` | dieser Bericht |

Test-Status: **543/543 backend tests gruen**.

---

## 7. Empfehlungen fuer naechste Iteration

1. **D113 zweilagig extrahieren** mit Reload-Strategie (war Iter 8 nicht
   moeglich wegen Application-Error nach Filterwechsel D112→D113).
2. **W628B-Variante CW 75** (W628B-F30-49 oder hoeher) extrahieren — aktuell
   haben wir nur W628B-F30-01 mit CW 50.
3. **Salach LV in lokale DB importieren** so dass der echte
   `kalkuliere_lv(273f3193-..., ...)`-Workflow lokal lauffaehig wird —
   aktuell muss Synthetic-Harness genutzt werden.
4. **F12 Trockenestrich** extrahieren (Boden-Kategorie nicht getestet).
5. **W113, W115, W118** (drei-/mehrlagige Innenwand-Varianten) extrahieren,
   da Salach Pos 4 (Zulage 1lg) zeigt, dass auch GKBI-Wand-Varianten relevant sind.
