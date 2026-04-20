# Storage für Lieferanten-Preislisten

Uploads werden hier abgelegt:

```
storage/pricelists/{tenant_id}/{supplier_name_slug}/{original_name}_{timestamp}.{ext}
```

- Inhalte sind **vertraulich** (Kunden-Rahmenverträge, Händler-Einkaufspreise).
- **Nichts wird committed** (siehe `.gitignore`).
- In Produktion wird das Verzeichnis via Docker-Volume / Render-Persistent-Disk gemappt.
- Bei Upload via `POST /api/pricing/upload` wird die Datei hier gespeichert,
  zusammen mit einem SHA256-Hash in der DB-Tabelle `lvp_supplier_pricelists`.

## Lokales Testen

Für Tests mit Fixture-Dateien nutze `tests/fixtures/` — dort darf auch
committed werden. Dieses Verzeichnis hier ist nur für **echte** Upload-Daten.
