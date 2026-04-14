# Test-Fixtures — Baupläne

> **ACHTUNG:** Echte Baupläne sind sensible Dokumente. Nicht auf GitHub pushen!
> Diese Dateien stehen in `.gitignore` (*.pdf).

## Verfügbare Test-Pläne

### 1. deckenspiegel_eg_kopfbau_himmelweiler.pdf
- **Typ:** Deckenspiegel (Reflected Ceiling Plan)
- **Projekt:** Himmelweiler III, Franz-Mack-Str. 2, 89160 Dornstadt
- **Geschoss:** EG (Erdgeschoss), Kopfbau
- **Maßstab:** 1:50
- **Format:** A0 (1189 x 841mm) — Letter-Format im PDF
- **Datum:** 17.12.2025, Revision b
- **Besonderheiten:**
  - Enthält "entfällt"-Markierungen (3 gestrichene Positionen)
  - Raumstempel mit NF, RH, OK FF, Deckenbelag
  - Verschiedene Trockenbau-Deckentypen
  - Detail D101: Deckenschürze für Glastrennwände, M 1:10
  - Heiz-Kühldecken (mit/ohne Beplankung)
- **Gerendert als:** deckenspiegel_eg_kopfbau_himmelweiler_400dpi.png (400 DPI)

## E2E-Analyse-Ergebnisse (Claude Opus 4, 14.04.2026)

**Konfidenz:** 72% | **Tokens:** 6.894 in / 4.638 out | **Kosten:** $0.43

### Erkannte Räume

| Raum-Nr | Bezeichnung | NF (m²) | RH (m) | Deckentyp |
|---------|-------------|---------|--------|-----------|
| 0.1.01 | Aufenthaltsraum | 23.17 | 2.75 | GKb-Abhangdecke glatt |
| 0.1.02 | Patientenraum | 14.48 | 2.75 | GKb-Abhangdecke glatt |
| 0.1.03 | Flur | 9.45 | 2.75 | GKb-Abhangdecke glatt |
| 0.1.04 | Künstliche Klasse | 6.35 | 2.75 | GKb-Abhangdecke glatt |
| 0.1.05 | WC-Räume | 4.91 | 2.50 | HKD Aquapanel |
| 0.1.06 | Vorzimmer Börsen | 5.52 | 2.75 | GKb-Abhangdecke glatt |
| 0.1.07 | Ahl-Koord. Börsen | 5.34 | 2.75 | GKb-Abhangdecke glatt |
| 0.1.10 | Büroraum (groß, Mitte/Ost) | — | 2.75 | Heiz-Kühldecke ohne Beplankung |
| 0.1.14 | Besprechung | — | 2.75 | Heiz-Kühldecke ohne Beplankung |
| 0.1.15 | Flurbereich / Kernzone | — | 2.75 | GKb-Abhangdecke glatt |
| 0.1.17 | Empfang / Eingangsbereich | — | — | Sichtbeton (kein Trockenbau) |

### Erkannte Decken

| Raum | Deckentyp | System | Fläche |
|------|-----------|--------|--------|
| Aufenthaltsraum | GKb-Abhangdecke glatt | D112 | 23.17 m² |
| Patientenraum | GKb-Abhangdecke glatt | D112 | 14.48 m² |
| Flur | GKb-Abhangdecke glatt | D112 | 9.45 m² |
| WC-Räume | GKb-Abhangdecke Nassraum | — | 4.91 m² |
| Bürobereich Ost | Heiz-Kühldecke OHNE Beplankung | HKD | — |
| Heiz-Kühldecke | Heiz-Kühldecke MIT Beplankung | — | — |
| Flurbereich | GKb-Abhangdecke glatt | D112 | — |

### Gestrichene Positionen (korrekt erkannt)

| Position | Grund |
|----------|-------|
| TB D02 — Heiz-Kühl-Abhangdecke Nassraum | entfällt (rot durchgestrichen) |
| TB D01 — Mineralfaserdecke | entfällt (rot markiert) |
| TB D05 — Heiz-Kühldecke gelocht | gestrichen (rot markiert) |

### Warnungen (15 gesamt)

Wichtigste:
- Auflösung zu niedrig für alle Raumstempel
- Abhängehöhen NICHT direkt ablesbar
- Östliche Bürobereiche ohne lesbare Flächenangaben
- Empfangsbereich möglicherweise Sichtbeton (Bestätigung empfohlen)

> Manuelle Überprüfung der Werte am 17.04. beim Termin in Ulm durchführen.
