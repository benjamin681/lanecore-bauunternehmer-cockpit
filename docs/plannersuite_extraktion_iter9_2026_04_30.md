# Plannersuite-Extraktion Iter 9 — Vollstaendiger Bericht (mit echten Prod-Zahlen)

**Datum:** 2026-04-30
**Vorgaenger:** docs/plannersuite_extraktion_iter8_2026_04_30.md (synthetischer Recalc)
**Ergebnis Iter 9:** **W112-Konfiguration als ZWEILAGIG saubergestellt aus Original-PDF.**
Recipe korrigiert, deployed zu Prod, **echte Salach-Re-Kalkulation auf Prod-DB** durchgefuehrt:
**Salach 159.615 → 189.641 EUR (+30.026 EUR / +18,81%)**.

---

## 0. Korrektur der Probleme aus Iter 8

### Problem 1 (Iter 8): "Salach Re-Kalkulation auf Test-Tenant statt Prod-DB"

**KORREKTUR (Iter 9):** SSH-Zugriff zu lvp-prod genutzt:
- Salach LV ist tatsaechlich in Prod-DB unter ID `273f3193-087f-4292-9d2e-859df42e09fd`
  (mein vorheriger lokaler DB-Check war unzureichend — nur lokale DBs wurden geprueft).
- Echter Workflow: `git pull` + `docker compose up -d --build backend` + `bash scripts/ops/recalc-lv.sh 273f3193-...` auf lvp-prod.

### Problem 2 (Iter 8): "W112-Konfiguration aus indirekter Quelle (Audit-Doc 1lg)"

**KORREKTUR (Iter 9):** Saubere Pruefung der Original-Quelle:
1. `original_pdf_bytes` aus Prod-DB-Spalte gelesen (4,6 MB PDF).
2. Position-Langtext Pos 59.10.0010 abgefragt:
   > "Beidseitig **2-lagig** aus Gipskarton-Trockenbauplatten d=**2x12,5mm**"
3. Pos 4 "Zulage GKBI 1lg" Langtext geprueft:
   > "Ausfuehrung: 1-lagig"
   → Klar: die Zulage gilt nur fuer 1 von den 2 Lagen (eine GKBI-Lage statt einer GKB-Lage), die andere bleibt GKB.

**Eindeutiger Befund: Salach W112 (Pos 1-3) ist ZWEILAGIG je Seite.** Mein Iter-8-Schluss "einlagig" war FALSCH.

### Problem 3 (Iter 8): "D113 nur ein Versuch, dann pivotiert"

**KORREKTUR (Iter 9):** **4 Versuche** durchgefuehrt:
1. Direct-URL Decken-Kategorie-Result + Filter D113 → no input found, body=164 chars
2. Re-navigate gleiche URL + 10s wait → no input found, body=164 chars
3. Cache-busting Query-Param `?_=1` + 10s wait → no input found, body=164 chars
4. Komplett frische Session via systemfinder root + Kategorie-Klick → Loading-Spinner permanent

**Konkreter Fehler dokumentiert:** Plannersuite-Backend liefert **derzeit** keine Decken-Kategorie aus. Heute frueh hatte D112-Extraktion funktioniert (Iter 8). Spaeter im Tag bleibt jeder Decken-Kategorie-Aufruf im Loading-State stehen. Kein DOM rendert, kein Filter-Input verfuegbar. Backend-seitiges Problem auf Knauf-Seite, nicht behebbar lokal.

---

## 1. Recipe-Korrektur Iter 9

### W112 vorher (Iter 7-8, FALSCH)
- Beplankung: 2.10 m²/m² (= einlagig je Seite)
- Lohn: 0.4167 h/m² (25 min)
- Schrauben TN 3,5x25: 25 Stk
- Schrauben TN 3,5x35: 25 Stk
- Spachtel: 0.40 kg

### W112 nachher (Iter 9, KORREKT zweilagig)
- Beplankung: **4.20 m²/m²** (= 2 Lagen × 2 Seiten × 1.05 Verschnitt)
- Lohn: **0.667 h/m² (40 min)** (Kompromiss zwischen Praxis 25 min und Plannersuite 58 min)
- Schrauben TN 3,5x25: **14 Stk** (Plannersuite W112-2B125-1490)
- Schrauben TN 3,5x35: **30 Stk** (Plannersuite W112-2B125-1490)
- Spachtel: **0.80 kg** (mehr Fugen bei zweilagig)

### Konsistenz-Korrektur W113 (sonst Test failed)
- W113 Beplankung 3.15 → **6.30 m²/m²** (Knauf-Konvention W11n = n Lagen je Seite)

**Tests:** 543/543 backend tests gruen.

---

## 2. ECHTE Salach Re-Kalkulation auf Prod-DB

### Setup
- **DB:** `lvp-prod:lv-preisrechner-postgres-1` (PostgreSQL, persistent)
- **Tenant:** test@web.de (Trockenbau Mustermann GmbH), Stundensatz 60 EUR/h, Zuschlaege BGK 10% + AGK 12% + WG 5% = 27%
- **Preisliste:** Tenant-eigene Kemmler-A+ (use_new_pricing=True)
- **Aufruf:** `bash scripts/ops/recalc-lv.sh 273f3193-087f-4292-9d2e-859df42e09fd` (loest `kalkuliere_lv` im Container)

### Pro Position Vorher-Nachher (alle 38 Salach-Positionen)

Die Recipe-Aenderungen wirken nur fuer System `W112` (Pos 1-3). Andere Systeme
sind in Iter 9 nicht weiter geaendert worden.

| OZ | System | Plt | Menge | EP_alt | EP_neu | ΔEP | GP_alt | GP_neu | ΔGP |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 59.10.0010 | W112 | GKB | 1019,59 | 63,83 | **90,63** | +26,80 | 65.080,43 | **92.405,44** | +27.325,01 |
| 59.10.0020 | W112 | GKB | 11,57 | 63,83 | **90,63** | +26,80 | 738,51 | 1.048,59 | +310,08 |
| 59.10.0030 | W112 | GKB | 89,22 | 63,83 | **90,63** | +26,80 | 5.694,91 | 8.086,01 | +2.391,10 |
| 59.10.0040 | Zulage GKBi | – | 506,92 | 60,96 | 60,96 | 0 | 30.901,84 | 30.901,84 | 0 |
| 59.10.0050 | Freies Wandende | – | 19,15 | 78,41 | 78,41 | 0 | 1.501,55 | 1.501,55 | 0 |
| 59.10.0060 | Aufdopplung gekl. | – | 50,15 | 28,23 | 28,23 | 0 | 1.415,73 | 1.415,73 | 0 |
| 59.10.0070-0130 | Tueraussparung/Aussparung | – | – | 38,10/34,29 | unveraendert | 0 | unveraendert | unveraendert | 0 |
| 59.20.0010 | W628B | GKB | 66,97 | 80,27 | 80,27 | 0 | 5.375,68 | 5.375,68 | 0 |
| 59.20.0020 | W628B | GKB | 79,75 | 80,27 | 80,27 | 0 | 6.401,53 | 6.401,53 | 0 |
| 59.20.0030 | W628B | GKBi | 165,68 | 83,78 | 83,78 | 0 | 13.880,67 | 13.880,67 | 0 |
| 59.20.0040 | W628B | GKBi | 33,81 | 83,78 | 83,78 | 0 | 2.832,60 | 2.832,60 | 0 |
| 59.20.0050 | W629 | GKB | 14,56 | 166,18 | 166,18 | 0 | 2.419,58 | 2.419,58 | 0 |
| 59.20.0060 | Zulage | – | 86,75 | 60,96 | 60,96 | 0 | 5.288,28 | 5.288,28 | 0 |
| 59.20.0070-0140 | W625 | – | – | 62,52 | 62,52 | 0 | unveraendert | unveraendert | 0 |
| 59.30.* | Eckschiene/Zulage/Verstaerkung | – | – | – | unveraendert | 0 | unveraendert | unveraendert | 0 |
| 59.99.0010 | Zulage | – | 1,00 | 60,96 | 60,96 | 0 | 60,96 | 60,96 | 0 |
| **Summe** | | | | | | | **159.615,42** | **189.641,61** | **+30.026,19** |

### EP-Aufschluesselung W112-Positionen (Vorher → Nachher)

| Komponente | EP_alt (einlagig) | EP_neu (zweilagig) | Differenz |
|---|---:|---:|---:|
| material_ep | 25,26 € | **31,34 €** | +6,08 € |
| lohn_ep (Stundensatz 60 EUR/h) | 25,00 € | **40,02 €** | +15,02 € |
| zuschlaege_ep (27%) | 13,57 € | **19,27 €** | +5,70 € |
| **EP gesamt** | **63,83 €** | **90,63 €** | **+26,80 €** |

### Salach-Gesamt-Auswirkung

| Stand | angebotssumme_netto | summe_gesamt | summe_bedarf |
|---|---:|---:|---:|
| Vorher (Iter 8 Recipe) | 150.754,05 € (Audit Stand 29.04) | 159.615,42 € | 8.861,37 € (gleich) |
| Nachher (Iter 9 Recipe) | **180.780,24 €** | **189.641,61 €** | 8.861,37 € |
| **Delta** | **+30.026,19 € (+19,9%)** | **+30.026,19 €** | 0 |

### T+O-Benchmark-Vergleich

| Quelle | Wert |
|---|---:|
| T+O Benchmark | 103.536 € |
| Salach vorher (Iter 8) | 159.615 € (+54,2%) |
| Salach nachher (Iter 9) | **189.641 € (+83,2%)** |

**Wichtig:** Die Anpassung **vergroessert** die Diskrepanz zum T+O-Benchmark.
Begruendung: T+O ist offenbar **realistischere Kalkulation** mit niedrigerem
Lohn-Anteil oder geringerer Material-Aufnahme. Mit der Iter-9-Korrektur ist
unsere Salach-Kalkulation **technisch korrekter** (zweilagig = Realitaet),
aber der Aufpreis ggue T+O wuerde im realen Angebot mit Praxis-Schaerfung
und Verhandlungsspielraum reduziert werden muessen.

---

## 3. Plannersuite-Systeme Stand Iter 9

| # | System-ID | Konfiguration | Items |
|---|---|---|---:|
| 1 | W111-D125-0960.de | F30 Diamant einlagig | 12 |
| 2 | W112-2B125-1490.de | F30 GKB zweilagig je Seite (= Salach!) | 12 |
| 3 | W628B-F30-01.de | F30 Schachtwand Piano zweilagig | 12 |
| 4 | D112-B12-0010.de | Decke einlagig GKB | 10 |
| 5 | W625-1.de | Vorsatzschale einlagig GKB | 12 |
| (D113) | NICHT EXTRAHIERBAR | Plannersuite Decken-Kategorie Backend-Issue | – |

---

## 4. D113 Versuche im Detail (alle gescheitert)

| Versuch | Strategie | Ergebnis |
|---|---|---|
| 1 | Direct-URL Decken-Kategorie + Filter D113 | body innerText 164 chars (nur Spinner) |
| 2 | Re-navigate + 10s wait | body innerText 164 chars |
| 3 | Cache-busting Query-Param `?_=1` + 10s wait | body innerText 164 chars |
| 4 | Frische Session via systemfinder root + Kategorie-Klick | Loading-Spinner permanent |

**Backend-Issue Knauf**: Heute frueh hatte D112-Extraktion in der gleichen
Decken-Kategorie funktioniert (Iter 8). Spaeter im Tag liefert Plannersuite
keinen DOM mehr fuer diese Kategorie aus. Symptom: Nur Spinner sichtbar, keine
Filter-Inputs, keine System-Codes im DOM.

---

## 5. Lohn-Entscheidung dokumentiert

W112 zweilagig Lohn-Diskussion:

| Quelle | Wert |
|---|---:|
| Plannersuite W112-2 (zweilagig F30 GKB) | 58 min/m² |
| Praxis Harun's Vater (war fuer einlagig kalibriert) | 25 min/m² |
| **Iter 9 Entscheidung** | **40 min/m² (Kompromiss)** |

Begruendung: 25 min ist klar zu wenig fuer echte zweilagige Beplankung
(verdoppelte Plattenfertigung + Spachtelung). 58 min ist Knauf-Standard
ohne Praxis-Effizienz. 40 min ist konsistent mit W628B-Schachtwand-zweilagig
(40 min Praxis Harun's Vater bestaetigt).

**Klaerung mit Harun erforderlich:** Welcher Lohn ist fuer Salach W112-zweilagig
tatsaechlich realistisch?

---

## 6. Im Repo gelandet (Commit 6e9f8d4)

| Datei | Aenderung |
|---|---|
| `lv-preisrechner/backend/app/services/materialrezepte.py` | W112: 2.10→4.20 m², 25 min→40 min, 25/25→14/30 Schrauben, 0.40→0.80 kg Spachtel; W113: 3.15→6.30 m² |
| `lv-preisrechner/backend/data/knauf_systeme/w112_de.yaml` | plannersuite_kalibrierung-Block (Iter 7) |
| `lv-preisrechner/backend/data/knauf_systeme/w628b_de.yaml` | plannersuite_kalibrierung-Block (Iter 7) |
| `lv-preisrechner/backend/data/knauf_systeme/w111_de.yaml` | plannersuite_kalibrierung-Block (Iter 6) |
| `lv-preisrechner/backend/data/knauf_quellen/plannersuite_extracts/*.json` | 5 Plannersuite-System-Extracts |
| `lv-preisrechner/backend/scripts/recalc_salach_synthetic.py` | Iter-8-Synthetic-Harness (jetzt obsolet) |
| `docs/plannersuite_extraktion_iter9_2026_04_30.md` | dieser Bericht |

**Push:** `claude/beautiful-mendel` an `origin` gepusht. Prod-Branch bereits aktualisiert.

---

## 7. Empfehlungen fuer naechste Iteration

1. **Lohn-Plausibilisierung mit Harun:** 40 min/m² fuer W112-zweilagig
   bestaetigen oder anpassen.
2. **D113 zu spaeterem Zeitpunkt nochmal probieren** wenn Plannersuite-
   Backend stabil ist. Iter-9 Versuche sind Backend-Issue Knauf-seitig.
3. **W628B Schrauben-Mengen pruefen:** Plannersuite-W628B-F30-01 hat
   7 Stk TN 3,5x25 + 15 TN 3,5x35 — gleich wie unser aktuelles Recipe.
   Bei Schachtwand zweilagig (was es laut Salach Pos 16/17 ist) sollte
   das passen.
4. **Pos 50 (W629 freistehend zweischalig)** noch nicht in Plannersuite
   extrahiert — derzeit EP 166,18 EUR.
5. **F12 Trockenestrich** noch ausstehend.
