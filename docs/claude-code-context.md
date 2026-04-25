# Claude Code Context — Kalkulane / LV-Preisrechner

> **Ziel:** Eine Session-startende Referenz, damit zukünftige Sessions nicht
> erst mit Schema-Drift, Pfaden und Credentials kämpfen müssen. Stand
> dieses Dokuments: 2026-04-25.
>
> **Wenn du diese Datei aktualisierst:** halte sie *kurz* und faktisch.
> Ausführliche Diskussionen gehören in andere Dokumente unter `docs/`.

---

## 1. Infrastructure

| Element | Wert |
|---|---|
| SSH-Host | `lvp-prod` (Hetzner Cloud, alias in `~/.ssh/config`) |
| Working Dir | `/home/appuser/lvp/lv-preisrechner` |
| Storage (Bind-Mount) | `/home/appuser/lvp-storage` (entspricht im Container `/home/appuser/storage`) |
| Backups | `/home/appuser/backups` (täglicher pg_dump, 14 Tage Retention) |
| Production-URL | https://kalkulane.lanecore-ai.de |
| Docker-Compose-Dir | gleich wie Working Dir |

**Compose-Service-Namen:**
- `postgres` — PostgreSQL 16 (Container: `lv-preisrechner-postgres-1`)
- `backend` — FastAPI / Uvicorn (Container: `lv-preisrechner-backend-1`)
- `frontend` — Next.js 14 standalone (Container: `lv-preisrechner-frontend-1`)
- `caddy` — Reverse Proxy + TLS

---

## 2. Database

| Element | Wert |
|---|---|
| User | `lvpuser` |
| Database | `lvpreisrechner` |
| Tabellen-Präfix | `lvp_` |
| Postgres-Version | 16-alpine |

**Connection-Pattern:**

```bash
ssh lvp-prod "cd /home/appuser/lvp/lv-preisrechner && \
  docker compose exec -T postgres psql -U lvpuser -d lvpreisrechner -c '<QUERY>'"
```

Heredoc-Variante für mehrzeilige Queries:

```bash
ssh lvp-prod "cd /home/appuser/lvp/lv-preisrechner && \
  docker compose exec -T postgres psql -U lvpuser -d lvpreisrechner <<'SQL'
SELECT ...;
UPDATE ... ;
SQL"
```

**Backup ad-hoc:**
```bash
docker compose exec -T postgres \
  pg_dump -U lvpuser -d lvpreisrechner > /home/appuser/backups/foo.sql
```

---

## 3. Schema-Quirks (Stand 2026-04-25)

Hier landen Inkonsistenzen, an denen wir uns schon mal die Zähne ausgebissen
haben. Bitte ergänzen wenn neue auftauchen.

| Tabelle | Quirk |
|---|---|
| `lvp_supplier_pricelists` | Hat `uploaded_at` (kein `updated_at`). Hat `parse_error` (Text), `parse_error_details` (JSON, B+4.5) und `parse_progress` (JSON, B+4.7 — Live-Fortschritt eines Parses). |
| `lvp_supplier_price_entries` | Hat **kein** `created_at` / `updated_at`. Spalte `currency` ist `varchar(10)` seit Migration `f8a2b3e91d04` (vorher `varchar(3)`, hat Re-Parses gekillt). |
| `lvp_positions.materialien` | JSON-Array; Material-Items nutzen **teils `dna`, teils `dna_pattern`** als Key — beide tolerieren wenn man drin liest (siehe `compute_lv_gaps`). |
| `lvp_tenant_price_overrides` | Synthetische `article_number` mit Pattern `DNA:<dna_pattern>` für Gap-Resolves (B+4.6). Der Matcher in `kalkulation.py` schickt diesen Key an `lookup_price`, damit Stage-1-Override greift. |
| `PricelistStatus`-Enum | Enthält `PARTIAL_PARSE` (B+4.5) — Status zwischen `PARSED` und `REVIEWED`. Pricelists mit Teilfehlern bleiben benutzbar. |

---

## 4. Wichtige UUIDs

Diese werden in vielen E2E-Validierungs-Skripten und Smoke-Tests referenziert.
Nicht in den Code committen — nur hier dokumentiert.

| Was | UUID |
|---|---|
| Tenant `test@web.de` | `f7769a68-ce23-477b-9610-6a1d158ac7bc` |
| Salach-LV (Beta-Referenz) | `273f3193-087f-4292-9d2e-859df42e09fd` |
| Beta-Preisliste `test2` (A+ Kemmler) | `c2cf526a-1b1c-4456-b2a5-f05e6c50ae77` |
| Legacy-Preisliste A+ | `de945bac-65fe-4424-9c26-39c5dea65fe0` |

Aktuelle Salach-Summe (Referenz): **172.588 EUR netto** (Stand nach B+4.6
Gap-Resolves). T&O-Benchmark: 103.536 EUR.

---

## 5. Common Operations — SQL-Templates

### Entry-Count je Pricelist
```sql
SELECT pl.id, pl.list_name, pl.status, pl.entries_total,
       COUNT(e.id) AS real_count
FROM lvp_supplier_pricelists pl
LEFT JOIN lvp_supplier_price_entries e ON e.pricelist_id = pl.id
GROUP BY pl.id ORDER BY pl.uploaded_at DESC;
```

### LV-Status-Snapshot
```sql
SELECT id, projekt_name, status, angebotssumme_netto,
       (SELECT COUNT(*) FROM lvp_positions WHERE lv_id = lv.id) AS pos_count,
       (SELECT COUNT(*) FROM lvp_positions
        WHERE lv_id = lv.id AND needs_price_review = true) AS review_count
FROM lvp_lvs lv WHERE id = '<lv-id>';
```

### Offene Gaps eines LV (per Position-Material)
```sql
SELECT p.oz, p.kurztext, p.ep, p.price_source_summary
FROM lvp_positions p
WHERE p.lv_id = '<lv-id>'
  AND (p.price_source_summary ILIKE '%not_found%'
       OR p.ep = 0)
ORDER BY p.oz;
```

### Aktive Tenant-Overrides
```sql
SELECT id, article_number, manufacturer, override_price, unit, notes
FROM lvp_tenant_price_overrides
WHERE tenant_id = '<tenant-id>'
ORDER BY created_at DESC;
```

---

## 6. Common Operations — Python-Snippets

Alle Snippets gehen davon aus, sie laufen via
`docker compose exec -T backend python -c '...'` oder als Datei via
`docker compose exec -T backend python /home/appuser/storage/<script>.py`.

### LV neu kalkulieren
```python
from app.core.database import SessionLocal
from app.services.kalkulation import kalkuliere_lv

LV_ID = "..."
TENANT_ID = "..."
db = SessionLocal()
try:
    lv = kalkuliere_lv(db, LV_ID, TENANT_ID)
    db.commit()
    print(f"Summe: {lv.angebotssumme_netto}")
finally:
    db.close()
```

### Pricelist neu parsen
```python
from app.core.database import SessionLocal
from app.services.pricelist_parser import PricelistParser

PRICELIST_ID = "..."
db = SessionLocal()
try:
    parser = PricelistParser(db=db, batch_size=3)
    result = parser.parse(PRICELIST_ID)
    print(result.parsed_entries, result.needs_review_count, result.errors)
finally:
    db.close()
```

### Gap manuell resolven
```python
from app.services.catalog_gaps import resolve_gap_manual_price
audit = resolve_gap_manual_price(
    db=db, lv=lv, tenant_id=TENANT_ID, user_id=user.id,
    material_dna="|Profile|Eckschutzschiene||",
    price_net=2.87, unit="lfm",
)
db.commit()
```

---

## 7. Standard-Workflows

### Vor jeder riskanten DB-Änderung

```bash
ssh lvp-prod "mkdir -p /home/appuser/backups/pre_<aktion>_$(date +%Y%m%d_%H%M%S) && \
  cd /home/appuser/lvp/lv-preisrechner && \
  docker compose exec -T postgres pg_dump -U lvpuser -d lvpreisrechner \
  > /home/appuser/backups/pre_<aktion>_$(date +%Y%m%d_%H%M%S)/db.sql"
```

### Nach Code-Change auf Prod deployen

1. Lokal: Tests + ggf. `npm run build` (Frontend).
2. `git push origin <branch>` → von Prod-User pullen lassen.
3. `ssh lvp-prod "cd … && git pull && docker compose build <service> && \
   docker compose up -d <service>"`
4. Migration läuft per Entrypoint automatisch beim Start
   (`alembic upgrade head`).
5. Health-Check: `docker compose ps` muss `(healthy)` zeigen, oder
   `curl -I https://kalkulane.lanecore-ai.de/`.

### Re-Parse einer Preisliste

Verwende `scripts/ops/reparse-pricelist.sh <pricelist-id>` (siehe Phase 2).
Dauer typisch 18–22 Min für eine ~26-seitige PDF mit `batch_size=3`.

---

## 8. Known Gotchas

- **Beta-Parser commit-Zeitpunkt:** Der `PricelistParser` persistiert
  Entries **erst am Ende** des Parse-Laufs in einem einzigen Bulk-INSERT,
  nicht inkrementell. Während des Parsens zeigt die DB 0 Entries. Erwartet
  ist also langes "0 entries", dann auf einen Schlag der Endwert.
  Live-Fortschritt zeigt `parse_progress` (B+4.7) — wird in eigener
  DB-Session pro Batch geschrieben, **nicht** über die Hauptsession,
  damit nicht versehentlich ungetragte Entries committed werden.
- **Volume-Mount muss existieren:** Vor erstem Container-Start auf Host
  `mkdir -p /home/appuser/lvp-storage/{pricelists,lvs}` ausführen, sonst
  ist der Mount-Point leer und Uploads scheitern.
- **A+-Preisliste Ressourcen-Profil:** 26 Seiten ÷ batch_size 3 = 9 Batches,
  pro Batch ~2 Min Claude-Vision-Latenz, total **18–22 Min**. Kosten
  ca. **15–20 USD** pro Re-Parse.
- **`pytest` ist nicht im Prod-Image** (dev-Dependency). Für Tests im
  Backend-Container ad-hoc installieren mit `pip install pytest pytest-asyncio httpx`,
  Tests via `docker cp /home/appuser/lvp/lv-preisrechner/backend/tests
  lv-preisrechner-backend-1:/home/appuser/app/tests` reinkopieren.
- **`.next/`-Konflikt im Frontend-Worktree:** `npm run build` und
  `npm run dev` teilen sich `.next/`. Nach einem Production-Build muss
  vor dem Dev-Server-Start `rm -rf .next/` und `preview_stop` +
  `preview_start`, sonst `Cannot find module './vendor-chunks/next.js'`.
- **DNA-Pattern-Schema:** `materialien`-JSON ist nicht ganz konsistent —
  ältere Items haben `dna_pattern`, neuere `dna`. Code muss beides lesen.

---

## 9. Wo Dinge stehen (Code-Map)

| Konzept | Pfad |
|---|---|
| Parser-Pipeline | `backend/app/services/pricelist_parser.py` |
| Claude-Client | `backend/app/services/claude_client.py` |
| LV-Kalkulation | `backend/app/services/kalkulation.py` |
| Material-Rezepte | `backend/app/services/materialrezepte.py` |
| DNA-Matcher (Legacy) | `backend/app/services/dna_matcher.py` |
| Price-Lookup (Beta) | `backend/app/services/price_lookup.py` |
| Profile-Equivalence | `backend/app/services/profile_equivalence.py` |
| Catalog-Gaps + Resolve | `backend/app/services/catalog_gaps.py` |
| Product-Corrections | `backend/app/services/product_corrections.py` |
| Pricing-API | `backend/app/api/pricing.py` |
| LV-API | `backend/app/api/lvs.py` |
| Models (Beta) | `backend/app/models/pricing.py`, `backend/app/models/lv.py` |
| Migrations | `backend/alembic/versions/` |
| Operations-Scripts | `lv-preisrechner/scripts/ops/` |

---

## 10. Pflege

Diese Datei lebt mit dem Repo. Jede Session, die ein Schema ändert,
einen Workflow neu definiert oder einen Gotcha findet, sollte diese
Datei in derselben Session aktualisieren — sonst ist die Stelle bis
zur nächsten Bug-Hunt-Session vergessen. Kein neuer Doc, keine
neue Datei — Updates direkt hier rein.
