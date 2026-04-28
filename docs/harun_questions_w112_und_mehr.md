# Fragen an Harun's Vater zur Rezept-Kalibrierung

Stand: 2026-04-28
Pilot-LV: Salach Ensemble-Höfe 1.BA (38 Positionen, aktuell 158.881,89 € netto)

Hintergrund: Wir haben in den letzten Tagen die Materialrezepte im
LV-Preisrechner kalibriert. Einige Werte sind plausibel, andere weichen
von Industrie-Faustformeln oder von eurem Praxis-Richtwert ab. Bevor
wir an Iteration 5 (Schlussrechnung) weiterarbeiten, brauchen wir eure
Bestätigung oder Korrektur zu folgenden Punkten.

Bitte einfach unter jeder Frage eine kurze Antwort. Reicht in Stichworten.

---

## Frage 1 — W112 Lohn pro m²

**Kontext:** W112 ist eure Standard-Trennwand (1-lagig beplankt beidseitig
auf CW75-Ständer). In Salach habt ihr ca. 1.120 m² davon.

**Aktueller Wert in unserer Berechnung:** 25 Minuten Lohn pro m²
(0,42 h × 60 €/h Stundensatz = 25 € Lohn-Anteil).
Damit kommen wir auf einen EP von **63,83 €/m²** — was du als „guten
Richtwert" um 62 € bestätigt hast.

**Was uns stört:** Industrie-Faustformeln (rechnerplus.de) sehen
0,7–1,2 h/m² (also 42–72 Minuten) für eine komplette zweilagige
Trennwand: Unterkonstruktion + Beplankung + Dämmung + Spachteln.
Mit 0,7 h kämen wir auf ~85 €/m², mit 1,2 h auf ~110 €/m².

**Frage:** Stimmen die 25 Minuten? Oder kalkuliert ihr in Wirklichkeit
mit mehr Zeit und gleicht das über andere Faktoren aus (z. B. niedrigere
Material-Aufschläge, kleinerer BGK/AGK-Zuschlag, Stundensatz)? Wenn die
Zeit höher ist — wieviel Minuten sind realistisch für komplette W112
zweilagig beidseitig inkl. Dämmung + Spachtel?

**Antwort:** _____________________

---

## Frage 2 — W112 Schraubenmenge

**Aktueller Wert (gerade korrigiert):**
- 25 Stk Schnellbauschrauben TN 3,5 × 25 mm pro m² (für 1. Plattenlage)
- 25 Stk Schnellbauschrauben TN 3,5 × 35 mm pro m² (für 2. Plattenlage)
- = **50 Stk Schrauben gesamt pro m²** Wandfläche

**Quelle:** Knauf W11.de Detailblatt 01/2024 Seite 67, Befestigungs-
abstände-Tabelle für 2-lagige Beplankung (1. Lage 750 × 250 mm,
2. Lage 250 × 200 mm).

**Frage:** Stimmt das ungefähr mit eurem Verbrauch überein, oder
verschraubt ihr enger/weiter? Falls ihr eine andere Praxis-Erfahrung
habt: wieviel Schrauben rechnet ihr pro m² für W112?

**Antwort:** _____________________

---

## Frage 3 — W112 Spachtelmasse

**Aktueller Wert:** 0,4 kg Universal-Spachtel pro m² Wandfläche

**Industrie-Standard:** 0,7–1,0 kg/m² für 2-lagige Beplankung beidseitig
(zwei Spachtelgänge auf jeder Seite — Q1 oder Q2).

**Frage:** Was rechnet ihr für Uniflott bzw. Spachtelmasse pro m² W112?
Schließt das schon das Verspachteln aller Fugen + Flächen-Spachtelung
mit ein, oder nur die Fugen?

**Antwort:** _____________________

---

## Frage 4 — Knauf-Mat-Nrn UW 75 und CW 75

**Aktuelle Werte (unverifiziert):**
- UW-Profil 75 → Mat-Nr **00003376**
- CW-Profil 75 → Mat-Nr **00003261**
- GKB-Platte 12,5 mm → Mat-Nr **00002892**

Diese Nummern sind aus einer früheren Diskussion und nicht durch eine
echte Knauf-Publikation belegt. Im Knauf-Detailblatt W11.de stehen
keine Mat-Nrn.

**Frage:** Welche Knauf-Mat-Nrn habt ihr auf euren Lieferscheinen oder
in eurer Kemmler-Bestellung tatsächlich für UW75, CW75 und GKB 12,5 mm?
Falls ihr nicht direkt Knauf, sondern andere Hersteller verwendet
(Rigips, Protektor, Saint-Gobain) — bitte auch das mitteilen.

**Antwort:** _____________________

---

## Frage 5 — Schachtwand W628B Differenz

**Aktueller EP in unserer Berechnung:** 80 €/m² (mit GKB-Default,
ohne Brandschutz). Bei F30 + GKF: ~84 €/m².

**Erwartet von dir:** 50–65 €/m² für nicht-brandgeschützte Schachtwände.

**Diskrepanz:** ~15 €/m² zu hoch. In Salach sind das bei 346 m²
Schachtwand insgesamt ~5.000 € Differenz.

**Mögliche Ursachen:**
1. Manche Materialien aus Knauf-Katalog Seite 240 sind nicht im
   Kemmler-Bestand (Drehstiftdübel, Dichtungsband 70 mm, Trenn-Fix,
   Fugendeckstreifen Kurt) — der Lookup setzt sie auf 0 € oder
   Schätzpreis.
2. Unser Rezept ist zu reichhaltig (zu viele Posten oder zu hohe
   Mengen).
3. Lohn 40 min/m² ist zu hoch für eure Praxis.

**Frage:** Welche der drei Ursachen ist am wahrscheinlichsten? Welches
Posten könnte aus eurer Sicht weg oder reduziert werden? Stimmt der
40 Minuten Montage-Anteil pro m² Schachtwand mit eurer Praxis?

**Antwort:** _____________________

---

## Frage 6 — Türöffnung Differenz

**Aktueller EP:** 137 €/Stk

**Erwartet von dir:** 80–100 €/Stk

**Diskrepanz:** ~40–60 €/Stk zu hoch. In Salach sind das bei 82 Tür-
öffnungen ca. 3.000–5.000 € Differenz.

**Ursache:** Unser Rezept enthält 2 lfm UA75 + 1 lfm UW75 +
0,5 h Lohn. Der Lookup matcht UA75 auf einen relativ teuren
Profil-Eintrag (~38 €/lfm), was unrealistisch erscheint.

**Frage:** Welche genauen Knauf-Mat-Nrn nutzt ihr für UA-Profile
(UA50, UA75, UA100)? Welche Mengen rechnet ihr typischerweise pro
Türöffnung — also wieviel lfm UA pro Türöffnung im Schnitt? Plus
wieviel Lohn-Minuten pro Türöffnung?

**Antwort:** _____________________

---

## Frage 7 — Welche Systeme baut ihr in 80% eurer Aufträge?

**Kontext:** Wir haben aktuell ein gutes Dutzend Trockenbau-Systeme
hinterlegt (W112, W113, W115, W628A, W628B, W629, W635, D112, D113,
D116, D131, OWA-Mineralfaser, Aquapanel, W131, W133). Bei manchen
ist die Datenbasis dünn — andere kalibrieren wir vielleicht
unnötig, wenn ihr sie kaum baut.

**Frage:** Welche 4–6 Systeme machen den **Hauptanteil eurer Arbeit**
(80%-Regel)? Eine kurze Reihenfolge nach Häufigkeit reicht.

Beispiel-Antwort: „1. W112 (60%), 2. W628B (15%), 3. D112 (10%),
4. Türöffnungen + Eckschienen als Zulagen, 5. selten W115/W131/Aquapanel".

Damit können wir die Kalibrierungs-Reihenfolge priorisieren statt
blind alle Knauf-Systeme abzuarbeiten.

**Antwort:** _____________________

---

## Bonus — Was gerade nicht kritisch ist, aber praktisch wäre

Wenn ihr Zugang zum **Knauf-Konfigurator** oder **Systemfinder**
([tools.knauf.de](https://tools.knauf.de/tools/)) habt, könnt ihr dort
eine W112-Standard-Konfiguration eingeben (z. B. Wandlänge 4 m,
Wandhöhe 2,75 m) und das ausgespuckte Stücklisten-PDF an Benjamin
schicken. Damit hätten wir die echten Knauf-Mat-Nrn in einem Rutsch.

---

**Zusammenfassung — was Harun beantworten soll:**
- 7 Fragen, jede mit 2–3 Sätzen oder Stichworten beantwortbar
- Frage 7 (System-Priorisierung) ist die wertvollste — danach richten
  wir alle weiteren Kalibrierungen aus.
- Bonus (Konfigurator-Stückliste) wäre Gold wert, ist aber kein Muss.
