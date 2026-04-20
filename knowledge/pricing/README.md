# Preislisten-Architektur

Drei-Schichten-Preismodell:

1. **manufacturers/** — Offizielle Hersteller-Kataloge
   (Knauf, Rigips, Siniat, Fermacell)
   Fallback wenn kein Lieferanten-Preis verfügbar.

2. **suppliers/** — Baustoffhändler-Preislisten
   (Kemmler, Hornbach, Wölpert, Sonepar etc.)
   Jahres-Listenpreise der regionalen Händler.

3. **tenants/{tenant_id}/** — Kundenspezifische Overrides
   Drei Formen:
   - Stammlieferant-Zuordnung (Verweis auf suppliers/)
   - Rabatt-Prozent auf Stammlieferant
   - Einzelartikel-Überschreibungen (Rahmenvertrag-Preise)

## Preis-Lookup-Logik

1. Tenant-Override? → nehmen
2. Tenant-Rabatt auf Stammlieferant? → Listenpreis × (1-Rabatt)
3. Stammlieferanten-Preis? → nehmen
4. Hersteller-Kataloge? → nehmen
5. Nichts davon? → Fehler werfen (keine Halluzination)

---

**WICHTIG:** Noch keine DB-Änderungen machen. Das ist nur die Dateisystem-
Struktur für JSON-Daten. DB-Migration für die Tenant-Override-Logik kommt
in Block 2C.

Die Datei-Formate werden in `suppliers/*/README.md`, `manufacturers/README.md`
und `tenants/README.md` dokumentiert.
