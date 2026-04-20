# Hersteller-Kataloge

Offizielle Listenpreise direkt vom Hersteller. Fallback-Ebene wenn weder
Tenant-Override noch Lieferanten-Preis vorhanden ist.

## Geplante Hersteller

- **Knauf** (GKB/GKF/GKFi, Profile CW/UW/CD/UD/UA, Silentboard, Diamant, Fireboard, Aquapanel)
- **Rigips / Saint-Gobain** (Glasroc, Rigidur, Habito, Die Blaue, Die Rote)
- **Siniat** (LaPlura, LaDura Premium, Massivbauplatten)
- **Fermacell / James Hardie** (Gipsfaserplatten, Powerpanel H2O, F-Platte)
- **Rockwool** (Sonorock, Trennwandplatte TP 1, Conlit, Fixrock)
- **Isover / Saint-Gobain** (Akustic TP 1, Calibel, Ultimate)
- **OWA Odenwald** (Bolero, Sinfonia, Cosmos, OWATECTA S 22)
- **Lindner** (LMD ST 215 Streckmetalldecken)
- **Strähle** (Akustik-Deckensegel, System 7300)
- **DUR Lum** (DUR SONIC Quad Wandabsorber)

## Dateiformat (geplant)

```
manufacturers/
├── knauf/
│   ├── katalog-2026.json      (Standard-Listenpreise)
│   ├── systeme-w11.json        (Bereits vorhanden in knowledge/)
│   └── systeme-d11.json
├── rigips/
│   └── katalog-2026.json
└── ...
```

## Quellen

- Knauf: downloads.knauf.de
- Rigips: rigips.de/service-center
- Siniat: siniat.de/service/planungsunterlagen
- Fermacell: fermacell.de/downloads
- OWA: owa.de/service (Ausschreibungstexte frei verfügbar!)

## Wichtig

- Alle Hersteller-Kataloge dürfen committed werden (öffentliche Listenpreise)
- Noch nicht ausgefüllt — wird in späteren Blöcken schrittweise migriert
- Der aktuelle Bestand in `knowledge/knauf-systeme-*.json` ist **System-Wissen**
  (Detailblätter), **nicht** Preise. Kommt später als separate Datei.
