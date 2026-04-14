# Lastenheft — LaneCore AI Bauunternehmer-Cockpit

**Auftraggeber (Pilot):** [Name Unternehmen Harun's Vater], Ulm
**Auftragnehmer:** LaneCore AI (Ben Feichtenbeiner)
**Erstellungsdatum:** April 2026
**Version:** 0.1 (Entwurf — wird nach Termin 17.04. finalisiert)

---

## 1. Ausgangssituation

### 1.1 Unternehmen
- Trockenbau-Unternehmen in Ulm
- [Anzahl] Festangestellte, [Anzahl] Subunternehmer
- Kerngeschäft: Trennwände, Unterdecken, Fassadenverkleidung
- Auftraggeber: [öffentlich / privat / gemischt]
- Projektrregion: Ulm, [Radius]

### 1.2 Aktueller Kalkulations-Prozess (IST)
- Baupläne liegen vor als: [ ] PDF  [ ] Papier  [ ] DWG
- Massenermittlung erfolgt durch: [Name/Rolle]
- Durchschnittliche Dauer: ___ Stunden pro Ausschreibung
- Verwendete Tools heute: [ ] Excel  [ ] Word  [ ] [Branchensoftware]
- Häufigste Fehlerquelle: [frei lassen für Termin]
- Ausschreibungen pro Monat: ___ davon gewonnen: ___ %

---

## 2. Projektziel (SOLL)

### 2.1 Primärziel
Automatische Massenermittlung aus PDF-Bauplänen: Der Nutzer lädt einen Grundriss hoch und erhält innerhalb von 10 Minuten eine vollständige Aufstellung der Materialmengen (nach Wandtyp, Fläche, Länge).

### 2.2 Sekundärziele (v2, nach MVP)
- Preisvergleich: automatisches Matching der Massen mit aktuellen Lieferantenpreisen
- Angebotserstellung: automatisches Befüllen eines LV-Templates

---

## 3. Anforderungen (wird im Termin ausgefüllt)

### 3.1 Musskriterien (MVP)
- [ ] PDF-Baupläne hochladbar (bis ___ MB)
- [ ] Erkennung von Wandtypen: ___________________
- [ ] Ausgabe: Wandlängen in m pro Typ
- [ ] Ausgabe: Raumflächen in m²
- [ ] Konfidenz-Anzeige (unsichere Bereiche markiert)
- [ ] Export: ___________________
- [ ] Sprache: Deutsch
- [ ] Betrieb als Web-Applikation (kein Install)

### 3.2 Sollkriterien
- [ ] Mehrere Pläne pro Projekt hochladbar
- [ ] Manuelle Korrektur von KI-Ergebnissen
- [ ] Projekt-Archiv mit Suchfunktion
- [ ] Mehrere Benutzer (z.B. Bürokraft + Inhaber)

### 3.3 Kannkriterien (v2)
- [ ] Direkte Verbindung zu [Branchensoftware]
- [ ] Automatischer Preisimport von [Lieferant]
- [ ] Angebotsgenerator

### 3.4 Ausschlusskriterien (nicht im Umfang)
- Keine Statik-Berechnung
- Kein BIM/AutoCAD-Support (zunächst)
- Keine Buchhaltungs-Integration
- Kein Mobile-App

---

## 4. Qualitätsanforderungen

### 4.1 Genauigkeit
- Massenermittlung: Abweichung zur manuellen Berechnung ≤ ___ %
- (Erfahrungswert manuelle Methode: ± 5%)

### 4.2 Performance
- Analyse Standard-Grundriss (1 Seite, A1, 1:100): < ___ Minuten

### 4.3 Verfügbarkeit
- Erreichbarkeit: ___ % (z.B. Bürozeiten Mo–Fr 7–18h)

---

## 5. Rahmenbedingungen

### 5.1 Datenschutz
- Baupläne enthalten sensible Gebäudedaten
- Speicherort: [ ] Deutschland  [ ] EU  [ ] Egal
- Datenlöschung nach: ___ Monaten

### 5.2 Technische Voraussetzungen (Pilotbetrieb)
- Internet-Anschluss: vorhanden
- Browser: Chrome / Firefox (aktuell)
- Endgeräte: Desktop-PC, ___ Nutzer gleichzeitig

### 5.3 Pilotierungskonditionen
- Dauer: 3 Monate kostenlos
- Gegenleistung: regelmäßiges Feedback, Referenz-Kundenstatus
- Danach: ___ €/Monat

---

## 6. Abnahmekriterien

Das System ist abgenommen wenn:
1. 5 echte Baupläne des Unternehmens analysiert wurden
2. Abweichung zur manuellen Ermittlung ≤ ___ % in ≥ 4 von 5 Fällen
3. Harun's Vater (oder benannter Nutzer) kann das System selbstständig bedienen
4. Keine kritischen Fehler in 2 Wochen Testbetrieb

---

## 7. Meilensteine

| Meilenstein | Datum |
|-------------|-------|
| Anforderungen finalisiert | 18.04.2026 |
| Prototyp verfügbar | ca. 05.05.2026 |
| MVP live (Pilot-Start) | 26.05.2026 |
| Pilot-Review | 26.06.2026 |

---

*Dieses Lastenheft wird nach dem Termin am 17.04.2026 ausgefüllt und als Grundlage für die Entwicklung verwendet.*

**Unterschrift Auftraggeber:** ___________________________ Datum: ___________

**Unterschrift LaneCore AI:** ___________________________ Datum: ___________
