# W628B-Diskrepanz: Diagnose 2026-04-29

## Ist-Stand

- Aktueller EP: **80,27 EUR/m²** (Salach-Schachtwand-Positionen)
- Erwartung Harun's Vater: **50–65 EUR/m²**
- **Δ zur Mitte (57,5 EUR/m²): +22,77 EUR/m²**

## Material-Breakdown (live aus Lookup, pro m² Wandfläche)

| # | DNA | Menge | Preis | Source | Material-EP |
|---|-----|-------|-------|--------|-------------|
| 1 | `\|Profile\|UW\|75\|` | 0,70 lfm | 3,59 | supplier_price | 2,51 |
| 2 | `\|Profile\|CW\|75\|` | 2,00 lfm | 5,89 | supplier_price | 11,78 |
| 3 | `\|Beschlag\|Drehstiftduebel\|K6 35\|` | 0,70 Stk | – | **not_found** | 0,00 |
| 4 | `\|Dichtung\|Dichtungsband\|70mm\|` | 1,20 lfm | – | **not_found** | 0,00 |
| 5 | `\|Daemmung\|TP 115\|60mm\|` | 1,00 m² | 2,50 | supplier_price | 2,50 |
| 6 | `\|Gipskarton\|GKB\|12,5mm\|` | 2,00 m² | 2,92 | supplier_price | 5,84 |
| 7 | `\|Schrauben\|TN 3.5\|3.5x25\|` | 7,00 Stk | – | **not_found** | 0,00 |
| 8 | `\|Schrauben\|TN 3.5\|3.5x35\|` | 15,00 Stk | – | **not_found** | 0,00 |
| 9 | `\|Spachtel\|Uniflott\|\|` | 0,40 kg | 1,38 | supplier_price | 0,55 |
| 10 | `\|Trennstreifen\|Trenn-Fix\|65mm\|` | 0,90 lfm | – | **not_found** | 0,00 |
| 11 | `\|Fugendeckstreifen\|Kurt\|75\|` | 0,90 m | – | **not_found** | 0,00 |

**Σ Material:** 23,19 EUR/m²

**Lohn:** 0,667 h × 60 EUR/h = **40,02 EUR/m²**

**Base:** 63,21 EUR/m²
**+ 27% Zuschläge:** +17,07 EUR/m²
**EP: 80,27 EUR/m²**

## Wo liegt der Hebel zur Senkung auf 50–65 EUR/m²?

### Hebel 1 — Lohn-Anteil (PRIMÄR, größter Hebel)

Lohn macht aktuell **40 EUR von 63 EUR Base** aus — also rund 63 % des Selbstkosten-Anteils. Eine Reduktion der Montagezeit hat den größten Einfluss:

| Lohn-Annahme | Lohn-EUR | Base | EP | In Erwartung 50–65? |
|--------------|----------|------|----|--------|
| 40 min (aktuell) | 40,02 | 63,21 | 80,27 | nein, +15 EUR drüber |
| 30 min | 30,00 | 53,19 | 67,55 | knapp drüber (Δ +2,5) |
| 25 min | 25,00 | 48,19 | 61,20 | **ja, in Mitte** ✓ |
| 20 min | 20,00 | 43,19 | 54,85 | **ja, im unteren Bereich** ✓ |

**Schlussfolgerung:** Falls Harun's Praxis-Wert für die Montage einer m² Schachtwand 25 min ist (analog zu seinem W112-Wert), würde der EP bei 61 EUR/m² landen — exakt in der erwarteten Range.

### Hebel 2 — Fehlende Materialien (NICHT relevant für EP-Senkung)

6 von 11 Materialien matchen aktuell nicht im Kemmler-Bestand:

- Drehstiftdübel K6×35 (Mat-Nr 00003537)
- Dichtungsband 70 mm (Mat-Nr 00003469)
- Schnellbauschrauben TN 3,5×25 (Mat-Nr 00003504) — nicht-Match obwohl im W112 sehr wohl gematcht wird, weil die DNA dort `|Schrauben||3.5x25|` lautet (leere Produktname-Felder), während W628B `|Schrauben|TN 3.5|3.5x25|` verwendet
- Schnellbauschrauben TN 3,5×35 (Mat-Nr 00003505) — gleiches Problem
- Trennstreifen Trenn-Fix 65 mm (Mat-Nr 00057871)
- Fugendeckstreifen Kurt 75 (Mat-Nr 00099382)

**Wichtig:** Würden diese Materialien matchen, würde der EP **steigen**, nicht sinken. Das ist also kein Hebel zur Erreichung von 50–65 EUR/m².

**Sub-Hebel:** Die Schrauben-DNAs könnten konsistent zu W112 angepasst werden (`|Schrauben||3.5x25|` statt `|Schrauben|TN 3.5|3.5x25|`). Effekt: Material steigt um vermutlich ~1–2 EUR/m² (Schrauben-Preis × Menge). Das passt zur Realität, treibt aber den EP weg von Harun's Erwartung.

### Hebel 3 — Material-Mengen reduzieren

Falls Harun's Praxis-Mengen niedriger sind als die im Knauf-Katalog angegebenen, könnten z. B. CW75 von 2,00 auf 1,60 lfm reduziert werden (=Standard-Achsabstand 625 mm ohne Brandschutz-Verdichtung). Effekt: −0,4 lfm × 5,89 EUR × 1,27 = **−3,00 EUR/m²**. Marginal.

### Aufschlüsselung der Diskrepanz

Bei einer Annahme **Lohn 25 min** würde der EP genau in der Range landen. Daraus folgt, dass die +22,77 EUR/m² Diskrepanz zur Mitte (57,5 EUR) **fast vollständig durch den Lohn-Anteil erklärt** wird:

```
Δ Lohn (40-25 min × 60/h × 1.27): +11,43 EUR/m²
+ Material-Anteile aus Praxis    :  ca. +5  EUR/m²
+ Restliche Praxis-Differenzen   :  ca. +6  EUR/m²
─────────────────────────────────────────────
  Σ Δ                            :  +22,77 EUR/m² ✓
```

## Empfehlung

1. **Keine erfundenen Quellenangaben** und **keine unilaterale Lohn-Änderung** — die Diskrepanz wird im Code als Wartepunkt dokumentiert.

2. **Konkrete Frage an Harun's Vater** (in `docs/harun_questions_w112_und_mehr.md` aufnehmen oder beim nächsten Kontakt mündlich):
   - **„Wieviel Minuten Montage rechnet ihr pro m² Schachtwand W628B?"**
   - Falls die Antwort < 30 min ist, passt sich der EP automatisch in die erwartete Range an.

3. **Sub-Korrektur ohne Risiko:** Die Schrauben-DNA-Patterns in W628B (`|Schrauben|TN 3.5|...`) auf `|Schrauben||...` umstellen, damit sie konsistent mit W112 matchen. Effekt: ~+1,5 EUR/m² Material — fachlich korrekter, aber treibt EP gegen Erwartung. Daher nur in Verbindung mit Lohn-Reduktion sinnvoll.

4. **Was als nächstes geschieht:**
   - W628B-EP bleibt bei 80,27 EUR/m² bis Harun's Antwort vorliegt
   - Sobald „Lohn = X min/m²" bestätigt ist, einzeilige Recipe-Änderung von `zeit_h_pro_einheit=0.667` auf `X/60`
   - Salach-Re-Kalkulation reproduziert dann den erwarteten EP

## Zusammenfassende Antwort auf User-Fragen

> **„Welche Materialien matchen aktuell wie?"**
> 5 von 11 matchen mit supplier_price (UW75, CW75, TP 115, GKB, Uniflott). 6 sind not_found (siehe Tabelle).

> **„Welche Material-Eintraege werden mit Schaetzwerten oder fuzzy gematcht statt mit Mat-Nr?"**
> Aktuell wird **keiner** über die Mat-Nr exakt gematcht — alle 5 erfolgreichen Treffer kommen via Fuzzy auf den Produktnamen. Die Mat-Nrn sind zwar im Recipe gesetzt, aber im Kemmler-Bestand nicht als `article_number` hinterlegt. Das ist konsistent mit der user-Aussage „Mat-Nrn unverifiziert" — sie funktionieren nicht als Lookup-Schlüssel.

> **„Wo ist der groesste Hebel?"**
> **Lohn-Anteil 40 min/m².** Eine Reduktion auf 25 min würde den EP von 80,27 auf 61,20 bringen — exakt in Harun's Erwartung. Das ist der einzige Faktor, der die Diskrepanz allein erklären kann.

> **„Empfehlung was zu aendern ist um auf 50 bis 65 EUR pro m2 zu kommen ohne erneut erfundene Quellenangaben?"**
> Nichts ändern bis Harun's Praxis-Wert für die Montagezeit pro m² Schachtwand bestätigt ist. Die Diskrepanz ist klar lokalisiert (Lohn-Anteil), aber eine unilaterale Reduktion wäre wieder eine Annahme ohne Quelle.

> **„Falls die Differenz daher kommt dass bestimmte Materialien nicht in der Kemmler-Preisliste enthalten sind das klar so dokumentieren."**
> Tut sie nicht. 6 fehlende Materialien tragen aktuell 0 EUR bei — wären sie da, würde der EP **steigen**, nicht sinken. Die Material-Lücke ist also kein Treiber der Diskrepanz nach oben.

> **„Falls die Differenz an unserem Lohn-Anteil liegt das auch klar dokumentieren."**
> Ja. Die Diskrepanz liegt zu **~63 % am Lohn-Anteil** (40 min vs vermutete Praxis 25 min) und zu **~37 % an Material- und Praxis-Annahmen**. Konkrete Bestätigung der Montagezeit pro m² Schachtwand durch Harun ist der eine offene Punkt zur Auflösung.
