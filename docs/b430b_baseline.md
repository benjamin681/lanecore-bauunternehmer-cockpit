# B+4.3.0b — Candidates-Endpoint Baseline & Design-Spec

**Stand:** 22.04.2026 | **Scope:** Backend-Endpoint, der für eine
einzelne LV-Position die Top-N Preis-Kandidaten plus einen virtuellen
Schätzungs-Kandidaten liefert. Frontend-Drawer kommt in B+4.3.1.

## Design-Entscheidungen (fixiert)

| Nr. | Entscheidung | Detail |
|---|---|---|
| a | **Limit via Query-Parameter** | `?limit=N`, Default **3**, Min **1**, Max **5**. `?limit=0` / `?limit=6` → 422 |
| b | **Confidence als Float** | `match_confidence: 0.0 … 1.0`. UI-Mapping („fast sicher" / „wahrscheinlich passend") passiert im Frontend |
| b' | **Stage-Name grob** | `supplier_price` / `fuzzy` / `estimated`. Zusätzlich `match_reason`-Freitext (z. B. „Artikelnummer exakt", „Fuzzy 0,82 auf Produktname + Einheit ~m") |
| c | **UT-Blacklist-Kandidaten ausblenden** | `should_exclude_by_blacklist` wird auf die Kandidaten-Liste angewendet. Herausgefilterte Einträge erscheinen **nicht** im Response |
| d | **Stage-4-Schätzung als virtueller Kandidat** | Immer angehängt, auch wenn echte `supplier_price`-Matches existieren. Erscheint als **letzter** Eintrag mit `stage="estimated"`, `match_reason` z. B. „Ø aus Kategorie Profile (42 Einträge, 12 Monate)" |
| e | **Kein Performance-Pre-Filter** | Brute-force über ~327 Einträge ist akzeptabel (~1300 Scoring-Ops pro Call) |

**Wichtig für das API-Contract:** Wenn `limit=3` **drei echte** `supplier_price`-Kandidaten liefert, enthält das Response-Array **vier** Einträge (3 echte + 1 estimated). Das wird im Docstring und in der Response-Doc klar gemacht.

## Offene Punkte der Spec (geklärt unten)

1. ID-Typ: `lv_id` und `pos_id` sind **UUID-Strings**, nicht ints. Der
   Prompt hatte `int` in Beispiel-Signaturen, aber der bestehende
   `app/models/position.py` nutzt `str`. Handler-Signatur:
   `lv_id: str, pos_id: str`.
2. Tenant-Check folgt dem bestehenden Muster aus `lvs.py` (LV →
   Tenant-Match → 404 bei Miss; Position → `Position.lv_id == lv_id`).
3. Fremder Tenant: 404, nicht 403 — damit die Existenz nicht leakt.

## API-Spec (OpenAPI-ähnlich)

### Request

```
GET /api/v1/lvs/{lv_id}/positions/{pos_id}/candidates
```

| Parameter | Ort | Typ | Pflicht | Beschreibung |
|---|---|---|---|---|
| `lv_id` | path | str (UUID) | ✓ | LV-ID (muss zum eigenen Tenant gehören) |
| `pos_id` | path | str (UUID) | ✓ | Position-ID (muss zu `lv_id` gehören) |
| `limit` | query | int | ✗ | Max. Anzahl echter Kandidaten; Default 3, Min 1, Max 5 |
| `Authorization` | header | Bearer Token | ✓ | Aus `/auth/login` |

### Response 200

```json
{
  "position_id": "550e8400-e29b-41d4-a716-446655440000",
  "material_name": "CW 100",
  "candidates": [
    {
      "pricelist_name": "Kemmler — Ausbau 2026-04",
      "candidate_name": "CW-Profil 100x50x0,6 mm BL=2600 mm 8 St./Bd.",
      "match_confidence": 0.95,
      "stage": "supplier_price",
      "price_net": 8.05,
      "unit": "m",
      "match_reason": "Fuzzy 0,95 auf Produktname + Einheit ~m"
    },
    {
      "pricelist_name": "Kemmler — Ausbau 2026-04",
      "candidate_name": "CW-Profil 50x50x0,6 mm BL=2600 mm",
      "match_confidence": 0.78,
      "stage": "supplier_price",
      "price_net": 5.12,
      "unit": "m",
      "match_reason": "Fuzzy 0,78 auf Produktname + Einheit ~m"
    },
    {
      "pricelist_name": "(Schätzung)",
      "candidate_name": "Ø Kategorie Profile",
      "match_confidence": 0.50,
      "stage": "estimated",
      "price_net": 1.28,
      "unit": "m",
      "match_reason": "Ø aus Kategorie Profile (42 Einträge, 12 Monate)"
    }
  ]
}
```

### Response 404

```json
{ "detail": "Position nicht gefunden" }
```

Tritt auf bei:

- `lv_id` gehört nicht zum eigenen Tenant
- `pos_id` existiert nicht oder gehört nicht zu `lv_id`

### Response 422

Bei `?limit=0`, `?limit=6`, `?limit=abc`. Fehler-Detail nach
Standard-FastAPI-Validator.

### Response 401

Bei fehlendem/ungültigem Bearer-Token. Standard-FastAPI.

## Beispiel 2 — Dämmungs-Position mit UT-Filter

**Query:** Position „Dämmung 40 mm", Material-Name `40mm`.

**Response:**

```json
{
  "position_id": "…",
  "material_name": "40mm",
  "candidates": [
    {
      "pricelist_name": "Kemmler — Ausbau 2026-04",
      "candidate_name": "Trennwandpl. Sonorock WLG040, 1000x625x40 mm - 7,5 m²/Pak.",
      "match_confidence": 0.67,
      "stage": "supplier_price",
      "price_net": 3.05,
      "unit": "m²",
      "match_reason": "Fuzzy 0,67 auf Produktname + Einheit ~m²"
    },
    {
      "pricelist_name": "(Schätzung)",
      "candidate_name": "Ø Kategorie Dämmung",
      "match_confidence": 0.50,
      "stage": "estimated",
      "price_net": 4.12,
      "unit": "m²",
      "match_reason": "Ø aus Kategorie Dämmung (18 Einträge, 12 Monate)"
    }
  ]
}
```

**Wichtig:** der PE-Folien-Eintrag `UT40` **erscheint nicht** im
Response, weil `should_exclude_by_blacklist` ihn aus dem Pool
entfernt. Der Bieter sieht nur Sonorock und den Schätzwert.

## Beispiel 3 — Position ohne echten Treffer

**Query:** exotisches Material, kein Kandidat über Threshold.

**Response:**

```json
{
  "position_id": "…",
  "material_name": "Deckensegel 1.2x4.0",
  "candidates": [
    {
      "pricelist_name": "(Schätzung)",
      "candidate_name": "Ø Kategorie Decken-Spezial",
      "match_confidence": 0.50,
      "stage": "estimated",
      "price_net": 45.0,
      "unit": "Stk",
      "match_reason": "Ø aus Kategorie Decken-Spezial (4 Einträge, 12 Monate)"
    }
  ]
}
```

Nur der virtuelle Schätzwert; keine echten Kandidaten.

## Scope-Grenzen

- ✗ **Kein** Katalog-Lücken-Report in diesem Block.
- ✗ **Kein** Frontend-Code (Drawer kommt in B+4.3.1).
- ✗ **Keine** Änderung an `lookup_price` oder `_try_supplier_price` —
  neue `list_candidates` ist eine Schwester-Funktion.
- ✓ Neuer Endpoint in `lvs.py`.
- ✓ Neues Schema-Modul `candidates.py`.
- ✓ Neue Service-Funktion `price_lookup.list_candidates`.
- ✓ Neue Test-Datei `test_lvs_candidates.py` (8 Golden-Tests).

## Implementierungs-Plan

### `price_lookup.list_candidates(...)` — Signatur

```python
def list_candidates(
    *,
    db: Session,
    tenant_id: str,
    material_name: str,
    unit: str,
    manufacturer: str | None = None,
    category: str | None = None,
    limit: int = 3,
) -> list[CandidateRaw]
```

Gibt eine sortierte Liste zurück. Reihenfolge:

1. `supplier_price` (Stage 2a exakt zuerst, dann 2b Name+Hersteller,
   dann 2c Fuzzy), nach `match_confidence` absteigend
2. `estimated` als letzter Eintrag, **immer dabei**

Die Funktion wiederverwendet:
- Bestehende Query auf `active_lists` + `SupplierPriceEntry`
- `unit_matches` aus `unit_normalizer`
- `should_exclude_by_blacklist` (UT-Filter)
- Fuzzy-Score via `material_normalizer.score_query_against_candidate`
- `_estimate_price` (Stage 4)

### Response-Mapping im Handler

Der Handler iteriert über `position.materialien` — für den ersten
(Haupt-)Material-Eintrag wird `list_candidates` aufgerufen und das
Ergebnis ins Response-Schema gemappt.

**Offene Detail-Frage:** soll der Endpoint für **alle** Material-
Zeilen einer Position die Kandidaten liefern, oder nur für das
Hauptmaterial? Das Mockup zeigt einen einzelnen Kandidaten-Block pro
Position. → **Entscheidung:** nur für das **erste Pflicht-Material**
der Position. Das ist in der Regel der sichtbar preistreibende
Eintrag (GK-Platte, CW-Profil). Weitere Materialien werden im B+4.3.2
nachgeliefert, falls Benjamin das braucht.

## Test-Plan (Phase 2)

8 Golden-Tests mit erwarteten Initialzuständen:

| # | Test | Initial | Nach Fix |
|---|---|---|---|
| 1 | Happy Path Default-Limit (3 + estimated) | rot | grün |
| 2 | Custom Limit `?limit=5` | rot | grün |
| 3 | UT40 aus Dämmungs-Query ausgeblendet | rot | grün |
| 4 | Stage-4-Schätzung als letzter Eintrag | rot | grün |
| 5 | 404 bei nicht-existenter Position | rot | grün |
| 6 | 401 ohne Auth | rot | grün |
| 7 | 404 bei fremdem Tenant | rot | grün |
| 8 | Limit-Validierung (0/6 → 422, 3 → 200) | rot | grün |

## Offener Rahmen für Phase 2+

- Phase 2 schreibt alle 8 Tests ROT.
- Phase 3 implementiert Service + Handler, grün.
- Phase 4 E2E-Smoke gegen Stuttgart-LV (3 echte Positionen).
- Phase 5 Push-Freigabe von Benjamin.
