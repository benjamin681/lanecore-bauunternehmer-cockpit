# Knauf-System-Korrekturen — Abweichungs-Liste

> Ergebnis der Bulk-Verifikation am 2026-04-20. Quelle: `knowledge/knauf-systeme-VERIFIZIERT.json`.
>
> **Wichtig:** Diese Abweichungen sind **DOKUMENTIERT, NOCH NICHT gefixt**. Sortiert nach Priorität / Impact.
>
> Fix-Plan: nicht alle auf einmal, sondern in sinnvollen Gruppen (siehe Priorisierung unten).

---

## Zahlen-Übersicht

| Status | Anzahl |
|---|---|
| ✅ OK (Projekt == offiziell) | 7 |
| 🟡 OK mit Detail offen (Kategorie stimmt, Unterteilung nicht) | 1 |
| 🔴 Korrektur nötig (semantisch oder grob falsch) | 18 |
| ⚪ Nicht verifizierbar ohne PDF-Lookup | 2 |

---

## 🔴 GRAVIEREND (sofort fixen — semantisch falsch)

### K-1: **W135 ist Brandwand, nicht Installationswand**
- **Projektstand:** `W135 = Installationswand, breitere UK`
- **Knauf offiziell:** W135.de = Sonderbauwand anstelle Brandwand. Zweilagig + Stahlblecheinlage + mechanische Beanspruchung (F90-A+mB)
- **Impact:** Kann zu falscher Rezept-Wahl bei LV-Positionen mit "W135" führen. Brandschutz-EPs deutlich höher als Installationswand-EPs.
- **Fix-Vorschlag:**
  1. `lv_parser.py` SYSTEM_PROMPT: `"W135" = Sonderbauwand anstelle Brandwand (Einfachständerwerk, 2-lagig + Stahlblech, F90-A+mB)`
  2. `materialrezepte.py`: internes Rezept `W135_Stahlblech` mit `W135` konsolidieren — Stahlblech ist Teil des Systems, nicht optional
  3. resolve_rezept-Alias: `"Installationswand"` → `W116` (Doppelständer, nicht W135)

### K-2: **W623 und W625 sind vertauscht**
- **Projektstand:** W623 = freistehend, W625 = direkt befestigt
- **Knauf offiziell:** W623.de = direkt befestigt (CD 60/27), W625.de = freistehend (CW-Profil)
- **Impact:** Bei LV-Position mit expliziter "W625.de"-Angabe wird das falsche Rezept genommen
- **Fix-Vorschlag:**
  1. Beschreibungen in SYSTEM_PROMPT tauschen
  2. `materialrezepte.py`-Rezepte W623/W625 tauschen (Profile-Pattern: W623 soll CD60/27 statt CW50/75 fordern; W625 umgekehrt)

### K-3: **K21-Familie falsch: K211/K212 sind KEINE Kabelschächte**
- **Projektstand:** `knowledge/knauf-systeme-brandschutz-fireboard.json` listet K211, K212 als Kabelschächte
- **Knauf offiziell:** K21.de = Trapezblech-Decken-Systeme mit Fireboard. Kabelkanäle sind in **K26**-Familie (K261.de, K262.de)
- **Impact:** Nicht direkt im Produktiv-Code (K211/K212 werden aktuell nicht vom Parser referenziert), aber die Wissensdatenbank ist grob falsch — bei LV-Position "K211" würden wir ein Decken-System kalkulieren statt einen Kabelkanal
- **Fix-Vorschlag:**
  1. `knauf-systeme-brandschutz-fireboard.json`: K211/K212-Einträge umbenennen zu K261/K262, Beschreibung aktualisieren
  2. Oder: zwei separate Gruppen anlegen (K21 für Trapezblech, K26 für Kabelkanäle) — sicherer

### K-4: **W133 ist Einfachständer-dreilagig, nicht Doppelständer**
- **Projektstand:** W133 = "zweischalige Brandwand (zwei getrennte Profilreihen)"
- **Knauf offiziell:** W133.de = Einfachständerwerk **dreilagig** + Stahlblech. Die Zahl "3" bezieht sich auf Beplankung, nicht auf Profilreihen
- **Impact:** Falsche Beschreibung, führt bei Kalkulation zu möglicher Doppelzählung der UK
- **Fix-Vorschlag:** SYSTEM_PROMPT: `"W133" = Brandwand Einfachständerwerk dreilagig + Stahlblecheinlage (F90-A+mB)`

### K-5: **W131 mit Stahlblech statt ohne**
- **Projektstand:** W131 = "Brandwand (eigenständig, schwerer Aufbau, F90/F120)" — kein Stahlblech erwähnt
- **Knauf offiziell:** W131.de = Einfachständerwerk 2-3-lagig + **Stahlblecheinlage je Seite** (F90-A+mB)
- **Impact:** Rezept `W131` fordert 2x GKF + CW100 + UW100, OHNE Stahlblech. Das System wäre material-unvollständig
- **Fix-Vorschlag:**
  1. SYSTEM_PROMPT + Rezept-Beschreibung: Stahlblech immer als Teil von W131
  2. `materialrezepte.py` W131-Rezept: Stahlblech als Pflichtmaterial ergänzen (`|Stahlblech|...|`, `|Daemmung|...|` bleibt)

---

## 🟠 MITTEL (vor neuem LV mit D11-Positionen fixen)

### K-6: **D112/D113 falsch differenziert**
- **Projektstand:** D112 = "1-lagig GKB", D113 = "2-lagig"
- **Knauf offiziell:** D112.de = Metall-UK (Standard), D113.de = Metall-UK **niveaugleich** (niedrige Aufbauhöhe). Beide erlauben 1- und 2-lagig
- **Impact:** Bei LV-Positionen mit "D113" kalkulieren wir fälschlich 2-lagig. Reale D113 kann auch 1-lagig sein
- **Fix-Vorschlag:**
  1. SYSTEM_PROMPT umstellen: D112/D113 nach UK-Art definieren, Beplankung orthogonal als Feld `plattentyp_doppelt`
  2. Rezepte entsprechend: Materialmengen nicht aus Name ableiten, sondern aus `feuerwiderstand` + expliziter Plattenangabe

### K-7: **D131 ist spezifisch für Holzbalkendecke**
- **Projektstand:** D131 = "selbstständige Decke F30 (Membrandecke)"
- **Knauf offiziell:** D131.de = Freitragende Decke **unter Holzbalkendecke** (nur an Wänden befestigt)
- **Impact:** Anwendungsfall zu breit gefasst. Bei LV mit "Membrandecke ohne Holzbalkendecke" würde D131 trotzdem matchen
- **Fix-Vorschlag:** Beschreibung präzisieren, evtl. Alias-Keyword "Holzbalken" als Trigger

### K-8: **W628A Beschreibung ungenau**
- **Projektstand:** "erhöhte Wandhöhe bis 8.9m"
- **Knauf offiziell:** "freispannend bis 2m Schachtbreite, unbegrenzte Höhe"
- **Impact:** Nicht falsch, nur ungenau
- **Fix-Vorschlag:** SYSTEM_PROMPT-Beschreibung ersetzen

### K-9: **W116 Beschreibung unklar**
- **Projektstand:** "Doppelständerwand (akustisch entkoppelt)"
- **Knauf offiziell:** "Doppelständerwerk verlascht" — Profilreihen mechanisch verbunden
- **Impact:** Semantik weicht ab. W115 ist "entkoppelt", W116 ist "verlascht"
- **Fix-Vorschlag:** Beschreibung: `W116 = Doppelständerwerk verlascht (beide Reihen verbunden, Installationswand-Variante)`

### K-10: **W113 Beschreibung unklar (2-lagig vs 3-lagig)**
- **Projektstand:** (im w11-d11.json) "zweilagig beplankt + Verstärkung"
- **Knauf offiziell:** W113.de = Einfachständerwerk **dreilagig**
- **Impact:** Falsche Materialmengen in entsprechendem Rezept (wenn es existiert)
- **Fix-Vorschlag:** Beschreibung + Rezept auf 3-lagig umstellen

---

## 🟡 KLEIN (im Rahmen späterer Aufräumung)

### K-11: **W626 ist mehrlagig-CW, nicht geklebt**
- **Projektstand:** W626 = "geklebt (Ansetzgips Perlfix)"
- **Knauf offiziell:** W626.de = CW-Profil **mehrlagig**. Geklebte Platten haben keine eigene W-Nummer
- **Fix-Vorschlag:** W626 neu definieren, geklebte Vorsatzschale als eigenes Rezept `Vorsatzschale_geklebt` ohne W-Nummer

### K-12: **Interne "S-Suffix"-Codes haben kein offizielles Pendant**
- **Betroffen:** W625S, W626S, W631S, W632
- **Knauf offiziell:** Schachtwände sind W628A.de, W628B.de, W629.de, W635.de
- **Impact:** Bei LV mit exakter Knauf-Nomenklatur (z.B. "W629.de") findet unser Parser nichts Passendes
- **Fix-Vorschlag:**
  1. Interne Codes auf die offiziellen mappen (W625S → W628A oder W628B je nach Profil, W632 → W629 oder W635)
  2. `knauf-systeme-w62-w63-schachtwaende.json` komplett neu strukturieren mit offiziellen Namen

---

## ⚪ NICHT VERIFIZIERT (PDF-Lookup nötig)

### K-13: **W118**
- Existiert NICHT in der offiziellen W11.de-Übersicht
- Möglich: historisch, oder intern erfunden
- **Fix-Vorschlag:** Entweder PDF-Detailblatt direkt suchen (Knauf-Archiv), oder W118 komplett entfernen und durch `W113` (3-lagig) ersetzen

### K-14: **W631**
- Nicht in W61- noch in W62-Übersicht
- Projekt hat zwei widersprüchliche Definitionen (Schutz-Vorsatzschale UND Schachtwand zweiseitig)
- **Fix-Vorschlag:** Älteres Knauf-PDF suchen oder als eigenes W-System entfernen

---

## Empfohlene Fix-Reihenfolge

**Stufe 1 (als ein Commit):** K-1 bis K-5 (gravierende semantische Fehler mit direktem Impact)
- `lv_parser.py` SYSTEM_PROMPT: 5-6 Zeilen-Korrekturen
- `materialrezepte.py`: W135/W131 Stahlblech-Integration, W623/W625 tauschen
- Tests dürfen nicht brechen → Golden-Test ggf. neu laufen lassen

**Stufe 2 (als zweiter Commit):** K-6 bis K-10 (mittlere Präzisierungen)
- SYSTEM_PROMPT: Beschreibungen präzisieren
- Rezepte: Unwesentliche Anpassungen
- Mit erneutem Stuttgart-Golden-Test absichern

**Stufe 3 (optional, später):** K-11 bis K-14 (interne Namen auf offizielle umstellen, PDF-Lookup)
- Größere Umstellung der Knowledge-JSON-Struktur
- Braucht eigenen Research-Sprint für W118/W631

---

## Schätzung Zeitaufwand pro Stufe

| Stufe | Code-Änderungen | Tests | Gesamt |
|---|---|---|---|
| **Stufe 1** (K-1 bis K-5) | ~30 Min | Golden-Rerun (~7 Min) | **~45 Min** |
| **Stufe 2** (K-6 bis K-10) | ~20 Min | Full-Suite (~5 Sek) | **~30 Min** |
| **Stufe 3** (K-11 bis K-14) | ~60 Min Research + Umstellung | Golden-Rerun | **~90 Min** |

**Summe aller 3 Stufen:** ~165 Min = ~2.75 h
