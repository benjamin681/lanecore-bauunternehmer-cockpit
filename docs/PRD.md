# Product Requirements Document (PRD)
## LaneCore AI — Bauunternehmer-Cockpit

**Version:** 0.1 (Draft)
**Stand:** April 2026
**Autor:** Ben (LaneCore AI)
**Status:** In Entwicklung — wird nach Termin 17.04. finalisiert

---

## 1. Produkt-Vision

LaneCore AI ist das KI-Cockpit für mittelständische Trockenbau-Unternehmer. Es automatisiert die zeitintensivste Phase der Angebotserstellung: die Massenermittlung aus Bauplänen. Ziel ist es, die Zeit von Bauplan zu fertigem Angebot von 5–8 Stunden auf unter 30 Minuten zu reduzieren.

---

## 2. Zielgruppe

### Primäre Persona: "Der Kalkulator-Inhaber"
- Name: Hans (60), Inhaber eines Trockenbau-Betriebs
- Betriebsgröße: 10–50 Mitarbeiter, 3–20 Mio. € Umsatz/Jahr
- Entscheider: kauft Software selbst, wenn ROI klar
- Tech-Affinität: niedrig — nutzt Excel und E-Mail, kein Slack, kein Jira
- Pain Point: "Ich verbringe jeden Freitagnachmittag mit Planlesen statt mit der Familie"
- WTP (Willingness to Pay): €300–800/Monat wenn ROI nachweisbar

### Sekundäre Persona: "Die Bürokraft"
- Führt das System im Auftrag des Inhabers aus
- Datei-Upload, Status prüfen, Export — kein technisches Setup

---

## 3. Core Features — MVP (Säule 1)

### F01: PDF-Upload
- Drag & Drop oder Datei-Auswählen
- Mehrere Dateien pro Projekt
- Validierung: nur PDF, max. 50MB
- Fortschritts-Feedback sofort nach Upload

### F02: KI-Bauplan-Analyse
- Automatische Erkennung: Grundrisse vs. andere Seiten
- Extraktion: Räume (Name, Fläche), Wände (Typ, Länge), Decken (Typ, Fläche)
- Maßstab-Erkennung und -Validierung
- Konfidenz-Score pro Ergebnis
- Warnungen für unsichere Bereiche

### F03: Ergebnis-Anzeige
- Tabellarische Übersicht: Wände nach Typ (W112, W115, W118)
- Raumliste mit Flächen
- Deckenmassen
- Warnungen sichtbar und erklärend
- Gesamtsumme Wandfläche nach Typ

### F04: Manuelle Korrektur
- Nutzer kann einzelne Werte überschreiben
- Korrekturen sind gespeichert und exportierbar

### F05: Export
- Excel-Export: Massen nach Wandtyp
- Druck-freundliche Ansicht (für Besprechungen)

### F06: Projekt-Management
- Projekte erstellen, benennen
- Pläne einem Projekt zuordnen
- Analyse-Historie pro Projekt

---

## 4. Geplante Features (v2 — nicht MVP)

### G01: Preislisten-Import (Säule 2)
- PDF/Excel-Preislisten von Knauf, Rigips, etc. importieren
- Automatisches Matching: Wandtyp → Materialliste → Preise

### G02: Angebots-Generierung (Säule 3)
- VOB-konformes LV automatisch befüllen
- Export: Excel, PDF, (später GAEB)

### G03: Multi-User
- Rollen: Admin (Inhaber), User (Bürokraft)
- Einladungs-Link für neue Nutzer

---

## 5. Nicht-funktionale Anforderungen

| Anforderung | Zielwert |
|-------------|----------|
| Analyse-Dauer | <3 Min. für Standard-Grundriss (1 Seite, A1) |
| Analyse-Genauigkeit | <2% Abweichung zu manueller Messung |
| Verfügbarkeit | 99.5% (Bürozeiten Mo–Fr) |
| Ladezeit Frontend | <2s (First Contentful Paint) |
| Datenspeicherung | DSGVO-konform, Server in EU |

---

## 6. Metriken (Erfolgsmetriken)

### Pilotphase (Mai–Juni 2026)
- NPS des Pilot-Kunden ≥ 8/10
- Analyse-Genauigkeit: ≥ 90% der Analysen mit <5% Abweichung
- Nutzungs-Frequenz: ≥ 3 Baupläne analysiert in den ersten 4 Wochen
- Time-to-Value: Nutzer erhält erstes nützliches Ergebnis in <10 Min. nach Erstregistrierung

### North Star Metric
Zeit von Bauplan-Upload zu fertigem Angebot (erst v2)
