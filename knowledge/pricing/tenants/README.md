# Tenant-spezifische Preis-Overrides

Kundenspezifische Preis-Anpassungen. **Vertrauliche Daten** — JSON-Inhalte
werden nicht ins Git-Repo committed.

## Zweck

Ein Tenant (Trockenbau-Betrieb) hat typischerweise:
- einen oder mehrere **Stammlieferanten** (z.B. Kemmler) mit **Rahmenvertrag-Rabatten**
- einzelne **Artikel-Overrides** (z.B. "GKB 12,5mm kostet bei mir 2,80 EUR statt 3,50")
- eine **bevorzugte Hersteller-Wahl** für bestimmte Gewerke

Statt das direkt in der DB zu modellieren (Tabellen für Stammlieferant-Zuordnung,
Rabatte, Overrides), werden diese Daten hier als JSON pro Tenant abgelegt —
Migration in die DB kommt im späteren Block 2C.

## Struktur (geplant)

```
tenants/
├── {tenant_id}/
│   ├── stammlieferant.json     (Stammlieferant + globaler Rabatt-%)
│   ├── overrides.json          (Artikel-Überschreibungen via Rahmenvertrag)
│   └── notes.md                (interne Notizen, optional)
```

## Beispiel `stammlieferant.json`

```json
{
  "primary_supplier": "kemmler",
  "rabatt_prozent_auf_listenpreis": 8.5,
  "gueltig_ab": "2026-01-01",
  "gueltig_bis": "2026-12-31",
  "notes": "Jahresrahmenvertrag 2026 - Signalwerte bleiben ohne Rabatt"
}
```

## Beispiel `overrides.json`

```json
[
  {
    "produkt_dna": "Knauf|Gipskarton|GKB|12.5mm|",
    "preis_pro_basis": 2.80,
    "basis_einheit": "m²",
    "quelle": "rahmenvertrag-kemmler-2026",
    "gueltig_ab": "2026-04-01"
  }
]
```

## Preis-Lookup-Reihenfolge

1. Override in `tenants/{tid}/overrides.json`?        → nehmen
2. Stammlieferanten-Rabatt (Listenpreis × (1-rabatt)) → nehmen
3. Stammlieferanten-Listenpreis (aus `suppliers/`)    → nehmen
4. Hersteller-Katalog (aus `manufacturers/`)          → nehmen
5. Nichts davon?                                      → Fehler werfen (keine Halluzination)

## Wichtig

- `.gitignore` schließt `tenants/{tenant_id}/*.json` explizit aus
- Nur die `README.md`-Datei wird committed (Struktur-Dokumentation)
- Tenant-Daten bleiben auf dem lokalen Rechner bzw. auf dem produktiven
  Server (Render-Persistent-Disk später, oder als DB-Tabelle in Block 2C)
