# Kemmler Baustoffe — Preislisten

Regionaler Baustoffhändler in Baden-Württemberg, Hauptniederlassung Tübingen.
Relevant für den Pilot-Kunden (Harun's Vater, Ulm).

## Struktur

Eine JSON-Datei pro Preisliste-Jahrgang:

- `preisliste-YYYY-MM.json` (z.B. `preisliste-2026-04.json`)
- Format: Liste von Produkt-Einträgen mit Hersteller + Kategorie + Produktname
  + Abmessungen + Variante + Preis + Einheit (analog `kemmler-preise-042026.json`
  im `knowledge/`-Root, das als Fixture-Quelle bis zur Migration hier rüberzieht).

## Quelle

PDF-Preislisten werden vom Händler bezogen (A-Liste + A+ Liste). Parsing erfolgt
durch den Upload-Service im Dashboard oder manuell mit `stuttgart_diagnostic.py`-
ähnlichem Ansatz.

## Wichtig

- Diese Daten dürfen committed werden (öffentliche Listenpreise)
- Einkaufsrabatte / Rahmenvertrag-Preise kommen in `tenants/{tenant_id}/`, NICHT hier
