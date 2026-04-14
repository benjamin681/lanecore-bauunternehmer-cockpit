# Test-Fixtures — Baupläne

> **ACHTUNG:** Echte Baupläne sind sensible Dokumente. Nicht auf GitHub pushen!
> Diese Dateien stehen in `.gitignore` (*.pdf, *.png).

## Verfügbare Test-Pläne

### 1. deckenspiegel_eg_kopfbau_himmelweiler.pdf
- **Typ:** Deckenspiegel (Reflected Ceiling Plan)
- **Projekt:** Himmelweiler III, Franz-Mack-Str. 2, 89160 Dornstadt
- **Geschoss:** EG (Erdgeschoss), Kopfbau
- **Maßstab:** 1:50
- **Format:** A0 (1189 × 841mm)
- **Datum:** 17.12.2025
- **Besonderheiten:**
  - Enthält "entfällt"-Markierungen (durchgestrichene Revisionen)
  - Raumstempel mit NF, RH, OK FF, Deckenbelag
  - Verschiedene Trockenbau-Deckentypen (GKb-Abhangdecke, HKD Aquapanel)
  - Detail D101: Deckenschürze für Glastrennwände, M 1:10
  - CD-Profile 60/27 Referenzen
- **Gerendert als:** deckenspiegel_eg_kopfbau_himmelweiler_400dpi.png (400 DPI)

## Erwartete Analyse-Ergebnisse (Ground Truth)

Für Benchmark-Tests müssen die erwarteten Werte manuell erfasst und hier dokumentiert werden.

| Raum | Raum-Nr | NF (m²) | RH (m) | Deckentyp |
|------|---------|---------|--------|-----------|
| Aufenthaltsraum | 0.1.11 | ? | ? | ? |
| Vorraum Herren | 0.1.17 | 2.87 | 2.65 | ? |
| WC Herren | 0.1.13 | ? | ? | HKD Aquapanel |
| ... | ... | ... | ... | ... |

> TODO: Nach Termin 17.04. mit Harun's Vater die Ground-Truth-Werte manuell ausfüllen.
