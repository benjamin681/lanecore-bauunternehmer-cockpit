# Plannersuite-Extraktion Iter 7 — Vollstaendiger Bericht

**Datum:** 2026-04-30
**Vorgaenger:** docs/plannersuite_extraktion_2026_04_29.md (Iter 6, 1 System)
**Ergebnis Iter 7:** **3 Systeme** vollstaendig extrahiert mit je 12 Material-Positionen,
Lohn-Entscheidung Variante B (Praxis), materialrezepte.py kalibriert, 543 Tests gruen.

---

## 1. Was hat sich gegenueber Iter 6 geaendert

| Aspekt | Iter 6 (2026-04-29) | Iter 7 (2026-04-30) |
|---|---|---|
| Extrahierte Systeme | 1 (W111-D125-0960, partiell) | 3 (W111 + W112-2B125-1490 + W628B-F30-01) |
| Items pro System | 7/12 (truncated) | 12/12 vollstaendig |
| materialrezepte.py | nur Validierungs-Kommentar | W628B aktiv kalibriert + W112 erweitert |
| Lohn-Daten erfasst | ja (W111: 47 min/m²) | ja (W112-zweilagig 58 min, W628B 33 min) |
| Mat-Nr Cross-Ref | 6/9 Treffer | 8/11 Treffer + Katalog-Gap-Liste |
| Tests | 543 gruen | 543 gruen |

---

## 2. Phase 1: Navigations-Methodik

Initial gescheiterter UI-Filter wurde **geloest** durch Kombination von zwei
Schritten:

1. JS-Setter auf Input `Systemvariantennummer` mit `Object.getOwnPropertyDescriptor(...).set` (React-kompatibel) **plus**
2. **Klick auf "Anwenden"-Button** in der gleichen Filter-Sektion (depth-3-parent vom Input)

Vorher (Iter 6): nur JS-Setter + Enter — Filter wurde nicht angewendet.
Nun (Iter 7): Filter funktioniert reaktiv, 338 W112-Varianten + 524 Schachtwand-Varianten + Top-15-Auswahl moeglich.

Alternative Strategien getestet:
- **API-Reverse**: Plannersuite hat keinen erreichbaren JSON-API. Network-Tab zeigt nur Datadog-Telemetry + auth-session. Daten kommen vom SSR-Backend.
- **Direct-URL-Deeplink**: Detail-URL `/systemdetail/<sys_id>_<numeric>` braucht den numeric-Suffix (Session-spezifisch). Nicht reproduzierbar ohne UI-Klick.
- **Kategorie-Navigation**: Funktionert fuer Innenwaende und Schachtwaende. **Decken-Kategorie blieb dauerhaft im Loading-State** ("System auswaehlen (0)") — als Plannersuite-Bug dokumentiert; mit dokumentiertem Grund uebersprungen.

---

## 3. Phase 2+3: Extrahierte Systeme

### W111-D125-0960.de (carry-over Iter 6, vollstaendig)

- F30 einlagig je Seite Diamant GKFI 12,5 mm, CW 50 @ 625mm
- Material 36,03 EUR/m² + Lohn 39,17 EUR/m² = 75,20 EUR/m² (47 min @ 50 EUR/h)
- Datei: `backend/data/knauf_quellen/plannersuite_extracts/W111-D125-0960.json`

### W112-2B125-1490.de (NEU Iter 7, 12 Items)

- F30 ZWEILAGIG je Seite Bauplatte GKB 12,5 mm, CW 50 @ 625mm
- Material 39,93 EUR/m² + Lohn 48,33 EUR/m² = **88,26 EUR/m²** (58 min @ 50 EUR/h)
- 12/12 Items vollstaendig erfasst
- **Wichtige Nomenklatur-Erkenntnis**: Plannersuite-W112-2xxx = ZWEI Lagen je Seite (4 m² Beplankung).
  Unser materialrezepte.py W112 hat 2,10 m² Beplankung — entspricht W112-1xxx (einlagig je Seite).
- Datei: `backend/data/knauf_quellen/plannersuite_extracts/W112-2B125-1490.json`

### W628B-F30-01.de (NEU Iter 7, 12 Items)

- F30 zweilagig Piano GKF, CW 50, **ohne Daemmung**
- Material 27,89 EUR/m² + Lohn 27,50 EUR/m² = **55,39 EUR/m²** (33 min @ 50 EUR/h)
- 12/12 Items vollstaendig erfasst
- **Erkenntnis**: Plannersuite-Standard W628B nutzt CW 50 (kleinste Variante);
  unser Rezept verwendet CW 75 fuer Salach-typische Schachtbreiten.
- **Erkenntnis**: Plannersuite hat KEINE Daemmung im Standard — unsere TP 115 60mm
  ist Praxis-Aufschlag von Harun's Vater.
- Datei: `backend/data/knauf_quellen/plannersuite_extracts/W628B-F30-01.json`

### Nicht extrahiert (mit Begruendung)

| System | Grund |
|---|---|
| D112, D113 | Decken-Kategorie blieb in Plannersuite im Loading-State (UI-Bug) |
| F12 | Nicht extrahiert (Tool-Budget — Estrich ist bei Salach nicht kritisch) |
| W113, W115, W625, W629, W635 | Tool-Budget — fokussiert auf hoechste-ROI Salach-Systeme |
| W628B-Variante CW 75 | W628B-F30-01 mit CW 50 ist die Plannersuite-Default-Variante; CW 75 wuerde W628B-F30-49 oder hoeher entsprechen |

---

## 4. Phase 4: Mat-Nr Cross-Reference Kemmler

Pro extrahierter Plannersuite-Mat-Nr Pruefung in `lvp_supplier_price_entries`
(Kemmler Ausbau Neu-Ulm 04/2026, 415 Eintraege).

| Plannersuite-Mat-Nr | Beschreibung | Kemmler-Treffer | Status |
|---|---|---:|---|
| 00099223 | Deckennagel | 1 | OK |
| 00003251 | CW-Profil 50/50/06 | 1 | OK |
| 00003372 | UW-Profil 50/40/06 | **0** | **KATALOG-GAP** |
| 00003461 | Trennwandkitt 550 ml | 1 (mit Knauf-Mat-Nr im Produktnamen) | OK |
| 00002884 | Bauplatte GKB 12,5 (HRAK/SFK) | **0** | **KATALOG-GAP** |
| 00002891 | Piano GKF 12,5 | 2 | OK |
| 00669563 | Schnellbauschraube TN 3,5x25 Feingewinde | 2 | OK |
| 00669564 | Schnellbauschraube TN 3,5x35 Feingewinde | 3 | OK |
| 00003114 | Uniflott 25 kg | **0** | **KATALOG-GAP** (Multifinish vorhanden als Alternative) |
| 00099382 | Fugendeckstreifen Kurt 75 m | 2 | OK |
| 00057871 | Trenn-Fix 65 mm 50 m | 1 | OK |

**Katalog-Gaps fuer Benjamin (Kemmler nachbestellen oder alternativen Lieferanten finden):**
- UW-Profil 50/40/06 (Mat-Nr 00003372) — fehlt komplett im Kemmler-Bestand
- Bauplatte GKB 12,5 mm in Knauf-Spezifikation (Mat-Nr 00002884) — fehlt; nur generische Variante vorhanden
- Uniflott 25 kg (Mat-Nr 00003114) — fehlt; Multifinish (3010300013) ist Alternativ-Spachtel

---

## 5. Phase 5: materialrezepte.py — Lohn-Entscheidung Variante B (Praxis)

### Lohn-Vergleich

| System | Plannersuite-Lohn @ 50 EUR/h | Praxis-Lohn @ 60 EUR/h |
|---|---:|---:|
| W111 (einlagig F30) | 47 min/m² → 39,17 EUR/m² | nicht erfasst |
| W112 (Praxis = einlagig je Seite) | (Plannersuite W111-Vergleich) 47 min | 25 min/m² → 25,00 EUR/m² |
| W112-zweilagig | 58 min/m² → 48,33 EUR/m² | nicht erfasst |
| W628B | 33 min/m² → 27,50 EUR/m² | 40 min/m² → 40,00 EUR/m² |

### Entscheidung: Variante B (Praxis-Lohn beibehalten)

**Begruendung:**
- Harun's Vater ist Trockenbaumeister mit 30 Jahren Erfahrung und hat ein eingespieltes Team mit 60 Subunternehmern. Sein Praxis-Wert ist konkreter als die Plannersuite-Pauschalannahme.
- Plannersuite arbeitet mit deutschem Standard-Tarif (50 EUR/h) — Harun's Tenant hat 60 EUR/h. Dadurch sind die EUR/m²-Werte naeher zusammen als die min/m²-Werte vermuten lassen.
- Konsistenz der bisherigen Salach-Audit-Doku (Lohn = Praxis) bleibt erhalten.

**Ergebnis Phase 5: Mengen-Updates (Variante B Lohn unveraendert):**

| Aenderung | System | Vorher | Nachher | Quelle |
|---|---|---|---|---|
| Trennwandkitt hinzugefuegt | W628B | nicht enthalten | 0,2 Stk/m² × 6,50 EUR | Plannersuite |
| Trennwandkitt hinzugefuegt | W112 | nicht enthalten | 0,2 Stk/m² × 6,50 EUR | Plannersuite |
| Fugendeckstreifen Kurt | W628B | 0,9 m/m² | **1,1 m/m²** | Plannersuite |

---

## 6. Phase 6: Salach Re-Kalkulation (analytisch)

**Hinweis:** Salach-LV ist in der aktuellen DB nicht persistent (nur in `docs/salach_audit_2026_04_29.md` dokumentiert). Direkte DB-EP-Aktualisierung ist daher nicht moeglich. Re-Kalkulation analytisch:

### Material-Anstieg pro m²

- Trennwandkitt 0,2 × 6,84 EUR/Stk = **+1,37 EUR/m²** Material (Kemmler-Preis fuer 00003461 → 6,84)
- Fugendeckstreifen Kurt: +0,2 m × 0,33 EUR = +0,07 EUR/m² Material
- **Total Material-Anstieg: ~1,44 EUR/m²**

### Salach-Auswirkung

Betroffene Positionen:

| Pos | OZ | System | Menge | Material-Anstieg |
|---|---|---|---:|---:|
| 1 | 59.10.0010 | Innenwand 100mm (W112) | 1019,59 m² | 1467,09 EUR |
| 2 | 59.10.0020 | Innenwand 175mm (W112) | 11,57 m² | 16,66 EUR |
| 3 | 59.10.0030 | Innenwand 200mm (W112) | 89,22 m² | 128,47 EUR |
| 14 | 59.20.0010 | Schachtwand 75mm (W628B) | 66,97 m² | 96,44 EUR |
| 15 | 59.20.0020 | Schachtwand 100mm (W628B) | 79,75 m² | 114,84 EUR |
| 16 | 59.20.0030 | Schachtwand GKBI 75mm (W628B) | 165,68 m² | 238,58 EUR |
| 17 | 59.20.0040 | Schachtwand GKBI 100mm (W628B) | 33,81 m² | 48,69 EUR |
| **Sum** | | | **1466,59 m²** | **2110,77 EUR** Material |

Plus 27% Zuschlaege (BGK 10 + AGK 12 + WG 5) → **+2680,68 EUR brutto**

### Vorher-Nachher

| | Vorher (Audit 2026-04-29) | Nachher (Iter 7) | Delta |
|---|---:|---:|---:|
| Salach-Gesamtsumme netto | 150.754,05 EUR | **~153.434,73 EUR** | +2680,68 EUR (+1,8%) |

**Bewertung:** Anstieg ist klein, aber das Rezept ist nun **Plannersuite-validiert** und enthaelt
das vorher fehlende Trennwandkitt + korrigierten Fugendeckstreifen. Die T+O-Benchmark-Diskrepanz
(103.536 EUR) wird durch diese Praezisierung **nicht** beseitigt — sie liegt in den Mengen-Annahmen
und ggf. Lohn-Entscheidung. Substanzielle Naeherung an T+O wuerde Lohn-Variante A (Plannersuite-
Lohn 33 min statt 40 min fuer W628B) bringen, was bei 346 m² W628B-Positionen ~2400 EUR Lohn-Senkung
plus Zuschlaege ergaebe — aber gegen die Praxis-Aussage des Trockenbaumeisters.

---

## 7. Phase 7: Aufmass + Final-Offer

Salach-LV ist nicht in der aktuellen DB. Aufmass + Final-Offer-Aktualisierung
ist daher nicht direkt durchfuehrbar — fuer das naechste Kundengespraech mit
Harun muss die LV neu hochgeladen + neu berechnet werden, dann zeigen sich die
Plannersuite-Effekte automatisch in den EPs.

---

## 8. Phase 8: Tests

`pytest tests/ -q` → **543 passed in 74,87s**. Keine Regressionen durch
materialrezepte.py-Aenderungen.

---

## 9. Was im Repo gelandet ist

| Datei | Aenderung |
|---|---|
| `backend/data/knauf_quellen/plannersuite_extracts/W112-2B125-1490.json` | NEU — 12 Items, Kosten, Lohn |
| `backend/data/knauf_quellen/plannersuite_extracts/W628B-F30-01.json` | NEU — 12 Items, Kosten, Lohn |
| `backend/data/knauf_systeme/w112_de.yaml` | Block `plannersuite_kalibrierung` (~30 Zeilen) + Erkenntnis-Liste |
| `backend/data/knauf_systeme/w628b_de.yaml` | Block `plannersuite_kalibrierung` (~75 Zeilen) + 6 Erkenntnis-Statements |
| `backend/app/services/materialrezepte.py` | W628B kalibriert (Trennwandkitt + Fugenstreifen-Korrektur), W112 mit Trennwandkitt |
| `docs/plannersuite_extraktion_iter7_2026_04_30.md` | dieser Bericht |

---

## 10. Empfehlungen fuer naechste Iteration

1. **Decken-Kategorie-Bug umgehen**: D112/D113 sind aus Plannersuite nicht
   ueber UI extrahierbar (Loading-State). Knauf D11.de Detailblatt-PDF
   strukturell parsen und in YAML hinterlegen — bereits in `d11_de.yaml`
   vorhanden, dort ggf. Mengen verifizieren.
2. **W628B-Variante mit CW 75 extrahieren** (W628B-F30-49 oder hoeher) — relevanter
   fuer Salach-Schachtwaende > 2m Schachtbreite.
3. **Lohn-Plausibilisierung mit Harun**: Plannersuite-Werte (33-58 min/m²)
   zeigen, dass Praxis-Aussage 25-40 min/m² am unteren Ende liegt. Im Gespraech
   pruefen, ob Praxis-Werte fuer Standard-Konfiguration weiterhin gelten oder
   bei komplexeren F30/F90-Varianten Plannersuite-Werte plausibler sind.
4. **Katalog-Gaps schliessen**: 3 Mat-Nrn (UW-Profil 50, GKB-Bauplatte 12,5,
   Uniflott 25 kg) fehlen im Kemmler-Bestand. Mit Harun klaeren ob Kemmler
   nachfuehren kann oder alternativer Lieferant erforderlich ist.
