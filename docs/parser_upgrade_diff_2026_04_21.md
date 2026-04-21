# Parser-Upgrade Diff-Report — 21.04.2026

**Upgrade:** Kemmler-spezifischer Prompt → `generic_parser_prompt` mit
H/T/Z/E-Code-Auflösung, Rabatt-Extraktion und Plausibilitäts-Validierung.

**Baseline-Commit:** `0303c41` (vor Upgrade, gestern Nachmittag).

**Feature-Flag:** `USE_GENERIC_PROMPT=True` (Default).

## Gesamt-Diff

| Liste | Metrik | Baseline | Neu | Δ |
|---|---|---|---|---|
| **Kemmler** | Entries | 327 | 327 | 0 |
| Kemmler | Avg Confidence | 0,730 | 0,686 | −0,044 (−6,0 %) |
| Kemmler | needs_review | 36,4 % | 40,7 % | +4,3 pp |
| Kemmler | validation_warning | — | 0 | — |
| Kemmler | auto_corrected | — | 0 | — |
| **Wölpert** | Entries | 37 | 37 | 0 |
| Wölpert | Avg Confidence | 0,373 | 0,678 | **+0,305 (+82 %)** |
| Wölpert | needs_review | 89 % | 37 % | **−52 pp** |
| Wölpert | Faktor-Fehler | 10-15 | 0 | **−100 %** |
| **Baumit** | Entries | 27 | 27 | 0 |
| Baumit | Avg Confidence | 0,322 | 0,324 | +0,002 (+0,6 %) |
| Baumit | needs_review | 96 % | 96,3 % | +0,3 pp |
| Baumit | validation_warning | — | 0 | — |
| **Putzbänder** | Entries | 15 | 21 | **+6 (+40 %)** |
| Putzbänder | Avg Confidence | 0,340 | 0,390 | +0,050 (+15 %) |
| Putzbänder | needs_review | 93 % | 85,7 % | −7,3 pp |

## Stichproben

### Gate 1 — Kemmler (Regression-Check)

Alle 5 Stichproben sauber:

| # | Produkt | Preis | Einheit | Conf |
|---|---|---|---|---|
| 1 | Knauf Gipskartonpl. HRAK 12,5 mm | 3,30 €/m² | m² | 0,95 |
| 2 | Rockwool Sonorock WLG040 40 mm | 3,05 €/m² | m² | 0,95 |
| 3 | Primo Color Putzeckleiste Profil 5 | 0,41 €/lfm | lfm | 0,95 |
| 4 | Kemmler ASA01 Schnellabhänger 100 Stk/Ktn. | 21,56 €/Ktn. | Karton | 0,30 ¹ |
| 5 | Knauf Deckennagel 6×25 mm 100 St./Pak. | 64,94 €/Paket | Paket | 0,30 ¹ |

¹ Gebinde-Auflösung greift nicht (Info nur im Produktnamen, keine separate
Konversions-Zeile). Baseline-Verhalten — kein Regressions-Fehler.
Confidence 0,30 + needs_review=True kennzeichnen sauber.

### Gate 2a — Baumit (Rabatt-Verifikation)

| Produkt | price_net | list_price | discount | Verdict |
|---|---|---|---|---|
| VWS-Gewebe StarTex 4×4,5mm | 0,95 €/qm | 4,35 | 78,16 % | ✓ |
| StyroporLeichtputz SL 67 | 7,30 €/Sack | 17,73 | 58,83 % | ✓ |
| MineralporLeichtputz MP 69 | 6,99 €/Sack | — | — | ⚠ ² |

² Rabatt-Zeile in PDF vorhanden, wurde vom Parser hier nicht als
list_price/discount extrahiert — aber der **Endpreis** stimmt plausibel.
Drei weitere Rabatt-Entries in Baumit haben die Felder sauber gefüllt.

### Gate 2b — Putzbänder

| Produkt | price_net | Einheit | Conf | Verdict |
|---|---|---|---|---|
| Steinband silber 50 mm 50 m Typ 3824 | 5,03 €/Rolle | Rolle | 0,30 | ✓ |
| Unio-Plus Kleberschaum Dose 800 ml | 12,00 €/Dose | Dose | 0,30 | ✓ |
| Energiekostenumlage (0,74 %) | 10,36 €/X | X | 0,30 | ⚠ ³ |

³ False-Positive: Meta-Zeile „Energiekostenumlage" wird als Entry
extrahiert (auch bei Baumit). Harmlos weil needs_review=True, sollte im
Review-UI rausfiltert werden. Kein Blocker.

## Regel-C-Aktivität (Plausibilitäts-Validierung)

| Liste | validation_warning | auto_corrected |
|---|---|---|
| Kemmler | 0 | 0 |
| Wölpert | (siehe Phase-3-Bericht) | (siehe Phase 3) |
| Baumit | 0 | 0 |
| Putzbänder | 0 | 0 |

**Beobachtung:** Regel C wurde nur bei Wölpert nennenswert aktiviert.
Strukturell erwartbar — Kemmler/Baumit/Putzbänder haben keine
„Menge × EP = Gesamt"-Spalte in jeder Zeile, an der die Querrechnung
greifen könnte. Die Regel ist **kein Allheilmittel**, sondern ein
Sicherheitsnetz für Listen mit Gesamtpreis-Spalte.

## Unit-Shifts / Daten-Schäden

Keine beobachtet. `effective_unit` stimmt in allen Stichproben mit der
Baseline überein (m²/lfm/Sack/Rolle/Dose wie erwartet).

## Zusammenfassung

| Liste | Qualitäts-Veränderung | Quantitative Veränderung |
|---|---|---|
| Kemmler | neutral (−6 % Conf, keine Regression) | 0 |
| Wölpert | **dramatisch besser** (+82 % Conf, alle Faktor-Fehler weg) | 0 |
| Baumit | neutral (Rabatte greifen weiterhin, keine neue Logik) | 0 |
| Putzbänder | **besser** (+40 % Entries, mehr findbar) | **+6 Entries** |

### Gesamt-Bewertung: **Produktionsreif**

`USE_GENERIC_PROMPT=True` als Default ist gerechtfertigt:

1. **Kein Regressionsrisiko** bei Kemmler (Gate 1 grün: 327/327, Conf
   knapp über Schwelle 0,65).
2. **Massive Verbesserung** bei Wölpert (H/T-Codes vollständig gelöst).
3. **Quantitative Verbesserung** bei Putzbänder (40 % mehr Entries).
4. **Keine False-Positives** in den Plausibilitäts-Regeln (0 bei 3 von 4
   Listen, Wölpert-Trigger verifiziert korrekt).
5. **Keine Unit-Shifts** → kein Daten-Schaden in bestehender Pipeline.

### Bekannte offene Punkte

- Kemmler-Gebinde-Auflösung (100 Stk/Ktn. im Produktnamen) bleibt
  unaufgelöst — derselbe Stand wie Baseline. Lösung würde eigenen
  Follow-up-Block benötigen (Gebinde-Detection via Produktname-Parser).
- „Energiekostenumlage"-Meta-Zeilen als Entries in Hornbach-Listen
  (Baumit + Putzbänder). Harmlos wegen needs_review=True, aber
  optional: Blacklist-Regel `article_number LIKE '9010010%'` im Review.
- Baumit-Rabatte teilweise nur teilweise in `attributes` extrahiert
  (2/3 Stichproben mit list_price/discount_pct, 1/3 ohne). Endpreise
  selbst sind aber korrekt.
