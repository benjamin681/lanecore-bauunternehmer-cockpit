# B+4.3.0b — Candidates-Endpoint Baseline & Design-Spec

**Stand:** 22.04.2026 | **Scope:** Backend-Endpoint, der für eine
einzelne LV-Position die Top-N Preis-Kandidaten plus einen virtuellen
Schätzungs-Kandidaten liefert. Frontend-Drawer kommt in B+4.3.1.

## Design-Entscheidung: Material-Granularität (Variante 2)

Der Endpoint liefert Kandidaten **für alle Materialien der Position**,
nicht nur für das erste Pflicht-Material.

**Begründung:**

- **Manual-Override in B+4.3.1** wird auf Material-Ebene arbeiten:
  der Handwerker kann einen einzelnen Spachtel-Preis überschreiben,
  ohne die CW-Profil-Wahl anzufassen.
- **Volle Transparenz** — im Near-Miss-Drawer sieht der Bieter pro
  Material, warum der Winner gewählt wurde und welche Alternativen
  existieren. Das ist der Kern-Use-Case für „Preis selbst eintragen" /
  „Ähnliche Artikel".
- **Zukunftsfest für B+4.3.2:** der Katalog-Lücken-Report arbeitet auf
  Material-Ebene und kann dieselbe Response-Struktur konsumieren
  (nur mit Filter `stage="estimated"` oder `candidates=[]`).

**Material-Quelle:** das Rezept-System liefert die Materialien über
`resolve_rezept(erkanntes_system, feuerwiderstand, plattentyp)`.
Für eine Position mit `erkanntes_system="W628A"` liefert das die
Liste der `MaterialBedarf`-Objekte: Gipskarton, CW-Profil, UW-Profil,
Dämmung, Schrauben, Spachtel.

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

### Response 200 (Variante 2 — alle Materialien pro Position)

```json
{
  "position_id": "550e8400-e29b-41d4-a716-446655440000",
  "position_name": "W628A",
  "materials": [
    {
      "material_name": "Gipskarton 12,5 mm",
      "required_amount": 1.0,
      "unit": "m²",
      "candidates": [
        {
          "pricelist_name": "Kemmler — Ausbau 2026-04",
          "candidate_name": "Knauf Gipskartonpl. HRAK 2000x1250x12,5 mm",
          "match_confidence": 0.95,
          "stage": "supplier_price",
          "price_net": 3.30,
          "unit": "m²",
          "match_reason": "Fuzzy 0,95 auf Produktname + Einheit ~m²"
        },
        {
          "pricelist_name": "(Schätzung)",
          "candidate_name": "Ø Kategorie Gipskarton",
          "match_confidence": 0.50,
          "stage": "estimated",
          "price_net": 3.50,
          "unit": "m²",
          "match_reason": "Ø aus Kategorie Gipskarton (14 Einträge, 12 Monate)"
        }
      ]
    },
    {
      "material_name": "CW 100",
      "required_amount": 1.8,
      "unit": "lfm",
      "candidates": [
        {
          "pricelist_name": "Kemmler — Ausbau 2026-04",
          "candidate_name": "CW-Profil 100x50x0,6 mm BL=2600 mm 8 St./Bd.",
          "match_confidence": 0.82,
          "stage": "supplier_price",
          "price_net": 8.05,
          "unit": "m",
          "match_reason": "Fuzzy 0,82 auf Produktname + Einheit ~m"
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
    },
    {
      "material_name": "UW 100",
      "required_amount": 0.8,
      "unit": "lfm",
      "candidates": [
        {
          "pricelist_name": "(Schätzung)",
          "candidate_name": "Ø Kategorie Profile",
          "match_confidence": 0.50,
          "stage": "estimated",
          "price_net": 1.28,
          "unit": "lfm",
          "match_reason": "Ø aus Kategorie Profile (42 Einträge, 12 Monate)"
        }
      ]
    },
    {
      "material_name": "Dämmung 40 mm",
      "required_amount": 1.0,
      "unit": "m²",
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
    },
    {
      "material_name": "Schrauben 3.5x25",
      "required_amount": 16.0,
      "unit": "Stk",
      "candidates": [
        {
          "pricelist_name": "Kemmler — Ausbau 2026-04",
          "candidate_name": "ACP Gipsplattenschrauben Bohrs. CE 3,5x45 mm - 500 St./Pak.",
          "match_confidence": 0.72,
          "stage": "supplier_price",
          "price_net": 0.045,
          "unit": "Stk",
          "match_reason": "Fuzzy 0,72 auf Produktname + Einheit ~Stk"
        },
        {
          "pricelist_name": "(Schätzung)",
          "candidate_name": "Ø Kategorie Schrauben",
          "match_confidence": 0.50,
          "stage": "estimated",
          "price_net": 0.035,
          "unit": "Stk",
          "match_reason": "Ø aus Kategorie Schrauben (28 Einträge, 12 Monate)"
        }
      ]
    }
  ]
}
```

**Befunde am Beispiel:**

- **Dämmung 40 mm:** PE-Folie `UT40` ist **nicht** im Response (Blacklist-
  Filter greift). Sonorock gewinnt mit 0,67 Confidence.
- **UW 100:** keine echten Kandidaten in Kemmler → nur der virtuelle
  Schätzungs-Eintrag. Bieter sieht „Richtwert" statt falschem Match.
- Jedes Material hat **seinen eigenen** letzten `estimated`-Eintrag,
  mit Kategorie-Mittelwert.

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

## Beispiel 2 — Zulagen-Position ohne Rezept-Materialien

Manche Positionen haben kein zugeordnetes Rezept (z. B. freie
Zulage, Regiestunde). In diesem Fall ist die Materialien-Liste leer.

**Response:**

```json
{
  "position_id": "…",
  "position_name": "Regiestunde",
  "materials": []
}
```

UI kann dann einen Hinweis „Keine Material-Kandidaten für diese
Position — Lohn- und Zuschlags-basierte Position" rendern.

## Beispiel 3 — Position mit seltenem System (keine Matches)

**Query:** Position „Deckensegel 1.2×4.0" mit System
`Deckensegel` — im Kemmler-Katalog nicht geführt.

**Response:**

```json
{
  "position_id": "…",
  "position_name": "Deckensegel",
  "materials": [
    {
      "material_name": "Akustik-Deckenelement 1200x4000",
      "required_amount": 1.0,
      "unit": "Stk",
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
  ]
}
```

Nur der virtuelle Schätzwert; keine echten Kandidaten.

## Performance-Erwägungen

Mit Variante 2 wird pro API-Call über alle Materialien der Position
iteriert:

- **5–8 Materialien** pro Position typisch (W-System-Rezepte haben
  Gipskarton + 1–2 Profile + Dämmung + Schrauben + Spachtel).
- **~1300 Score-Berechnungen** pro Material (Kemmler-Pool ~327
  Einträge × 4 Score-Passes).
- **Worst-Case:** 8 Materialien × 1300 = **~10.400 Score-Berechnungen**
  pro API-Call.
- **Python-Zeit:** erwartet **< 800 ms** auf Entwicklungs-Hardware.

**Zielwerte:**

- Grün: < 500 ms median, < 1 s p99
- Gelb: 500–1000 ms median — OK für B+4.3.1-Pilot, aber
  Follow-up-Ticket für Pre-Filter oder Caching
- Rot: > 1 s median — STOPP, Optimierung zwingend

Die Tests in Phase 2 messen die Dauer nicht automatisch; ein
manueller Smoke-Test in Phase 4 gegen Stuttgart-W628A-Position mit
~5 Materialien bringt eine realistische Messung.

**Falls später Optimierung nötig:**

- DB-seitiger Index auf `(tenant_id, is_active)` für den Pricelist-
  Lookup (prüfen, ob bereits vorhanden).
- Pre-Filter: Kandidaten ohne `unit`-Match aus SQL statt Python.
- Caching: Score-Ergebnisse pro `(material_dna, pricelist_id)` in
  einem LRU-Cache zwischen API-Calls.

Heute: nicht nötig, Follow-up-Ticket.

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

### `price_lookup.list_candidates(...)` — Signatur (pro Material)

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

Gibt eine sortierte Liste zurück (ein Material, bis zu `limit` echte
Kandidaten + 1 virtueller `estimated`). Reihenfolge innerhalb:

1. `supplier_price` (Stage 2a exakt zuerst, dann 2b Name+Hersteller,
   dann 2c Fuzzy), nach `match_confidence` absteigend
2. `estimated` als letzter Eintrag, **immer dabei**

Die Funktion wiederverwendet:
- Bestehende Query auf `active_lists` + `SupplierPriceEntry`
- `unit_matches` aus `unit_normalizer`
- `should_exclude_by_blacklist` (UT-Filter)
- Fuzzy-Score via `material_normalizer.score_query_against_candidate`
- `_estimate_price` (Stage 4)

### Handler-Flow (Variante 2)

1. LV + Position laden, Tenant-Check, 404 bei Miss.
2. Rezept auflösen via `resolve_rezept(position.erkanntes_system,
   position.feuerwiderstand, position.plattentyp)`.
3. Wenn Rezept `None` oder `materialien`-Liste leer: Response mit
   `materials: []` (siehe Beispiel 2).
4. Für jedes `MaterialBedarf`-Objekt aus dem Rezept:
   - DNA-Pattern parsen (`_parse_dna_pattern` aus `kalkulation.py`)
   - `material_name` / `unit` / `manufacturer` / `category` bauen
   - `list_candidates(...)` aufrufen
   - Ergebnis in `MaterialWithCandidates` mappen (inkl.
     `required_amount = menge_pro_einheit`)
5. Ergebnis-Response zusammenstellen, mit
   `position_name = position.erkanntes_system`.

**Zusammenfassung Aufwand (revidiert):**

| Teil | Aufwand |
|---|---|
| `list_candidates` in `price_lookup.py` + Unit-Tests | 1 h |
| Schemas `CandidateOut` + `MaterialWithCandidates` + `PositionCandidatesOut` | 0,5 h |
| Handler mit Rezept-Iteration über alle Materialien | 1 h |
| Test-Suite (8 Tests, jetzt mit materials-Struktur) | 1,5 h |
| E2E-Smoke + Messung gegen Stuttgart-W628A-Position | 0,5 h |
| **Gesamt** | **~4,5 h** (gegenüber ~3,5 h bei Variante 1) |

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
