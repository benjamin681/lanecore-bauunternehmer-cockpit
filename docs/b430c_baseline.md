# B+4.3.0c — Katalog-Lücken-Report: Baseline & Spec

**Stand:** 22.04.2026, vor Implementierung.
**Abhängigkeiten:** B+4.2 (Position.materialien-JSON mit price_source
pro Material), B+4.3.0b (Candidates-Endpoint als Nachbar-Route).
**Kontext-Doc:** `docs/b430c_catalog_gaps_context.md`.

---

## 1. Scope & Abgrenzung

### In-Scope

- Neuer Read-Endpoint `GET /api/v1/lvs/{lv_id}/gaps`
- Per-Material-granulare Sicht: pro Lücken-Eintrag genau ein Material
- Nutzt ausschließlich bestehende Datenquellen:
  - `Position.materialien[i].price_source` (seit B+4.2)
  - `Position.materialien[i].match_confidence` (seit B+4.2)
  - `Position.materialien[i].needs_review` (seit B+4.2)
  - `Position.materialien[i].source_description` (seit B+4.2)
  - `Position.materialien[i].dna` (seit B+4.2)
- Tenant-Isolation wie bei anderen LV-Routes (404 auf fremde LVs)
- Query-Parameter `?include_low_confidence=false` (Default)

### Out-of-Scope (verschoben)

- Tenant-weite Aggregation (`/tenants/me/gaps` oder ähnlich)
- Historisierung (Snapshot-Vergleich zwischen LVs)
- Schreibende Operationen (Marker als „gelöst" o. ä.)
- UI-Arbeit für den Katalog-Lücken-Tab (B+4.3.1)
- Matcher- oder Parser-Änderungen

### Nicht geändert wird

- Model `Position`
- Schema `PositionOut`
- Bestehende Endpoints (`/lvs/{id}`, `/pricing/…`)
- Datenbank-Migrationen

---

## 2. Endpoint-Spec

### Request

```
GET /api/v1/lvs/{lv_id}/gaps
    ?include_low_confidence=false  (optional, default false)

Headers:
    Authorization: Bearer <token>
```

- `lv_id`: UUID-String des LVs
- `include_low_confidence`: bool; wenn `true`, werden zusätzlich
  supplier_price-Matches mit `match_confidence < 0.5` als
  `severity="low_confidence"` aufgeführt

### Response

**Status 200:** `LVGapsReport` (siehe Schema unten)
**Status 401:** Fehlende/ungültige Authentifizierung
**Status 404:** LV nicht gefunden oder gehört zu anderem Tenant

---

## 3. Schema

```python
from enum import Enum
from pydantic import BaseModel

class GapSeverity(str, Enum):
    missing = "missing"              # price_source == "not_found"
    low_confidence = "low_confidence"# supplier_price + confidence < 0.5
    estimated = "estimated"          # price_source == "estimated"

    # Deterministische Sortier-Ordnung (Priorität absteigend):
    # missing > low_confidence > estimated
    # Die UI kann darüber filtern oder sortieren.


class CatalogGapEntry(BaseModel):
    position_id: str                 # UUID-String
    position_oz: str                 # z. B. "1.2.3"
    position_name: str               # erkanntes_system oder kurztext[:60]
    material_name: str               # aus DNA-Pattern abgeleitet (siehe §5)
    material_dna: str                # vollständiges DNA-Pattern (Fallback)
    required_amount: float
    unit: str
    severity: GapSeverity
    price_source: str                # raw String aus Materialien-JSON
    match_confidence: float | None   # None, wenn price_source=="not_found"
    source_description: str
    needs_review: bool


class LVGapsReport(BaseModel):
    lv_id: str
    total_positions: int
    total_materials: int
    gaps_count: int
    missing_count: int               # severity=missing
    estimated_count: int             # severity=estimated
    low_confidence_count: int        # severity=low_confidence (nur wenn include_low_confidence=true)
    gaps: list[CatalogGapEntry]      # sortiert: siehe §6
```

### Severity-Definitionen

| Severity | Bedingung | Opt-in? |
|---|---|---|
| `missing` | `price_source == "not_found"` | Default an |
| `estimated` | `price_source == "estimated"` | Default an |
| `low_confidence` | `price_source == "supplier_price"` AND `match_confidence < 0.5` | nur mit `?include_low_confidence=true` |

### Nicht als Gap markiert

- `price_source == "supplier_price"` mit `confidence ≥ 0.5` — valider Match
- `price_source == "override"` — manueller Override, bewusst gesetzt
- `price_source == "legacy_price"` oder `"legacy"` — Legacy-Pfad, eigene UX
- Materialien ohne `price_source`-Key — vor B+4.2 gerechnete Positionen,
  werden ignoriert (keine Fehlerwertung)

---

## 4. Response-Beispiele

### 4.1 LV mit gemischten Gaps

**Request:** `GET /api/v1/lvs/9d9fda20.../gaps`
**Query:** keine

```json
{
  "lv_id": "9d9fda20-0ba7-47da-ae77-5518068097cb",
  "total_positions": 102,
  "total_materials": 486,
  "gaps_count": 126,
  "missing_count": 64,
  "estimated_count": 62,
  "low_confidence_count": 0,
  "gaps": [
    {
      "position_id": "c3f8...",
      "position_oz": "01.02.01",
      "position_name": "Metallstaenderwand W628A",
      "material_name": "Fireboard 12,5 mm",
      "material_dna": "Knauf|Gipskarton|Fireboard|12.5|",
      "required_amount": 2.10,
      "unit": "m²",
      "severity": "missing",
      "price_source": "not_found",
      "match_confidence": null,
      "source_description": "Kein Katalog-Eintrag fuer Fireboard 12,5 mm",
      "needs_review": true
    },
    {
      "position_id": "d4a9...",
      "position_oz": "01.03.05",
      "position_name": "Daemmung W628A",
      "material_name": "Mineralwolle 40 mm",
      "material_dna": "|Daemmung||40mm|",
      "required_amount": 1.05,
      "unit": "m²",
      "severity": "estimated",
      "price_source": "estimated",
      "match_confidence": 0.5,
      "source_description": "Ø aus Kategorie Daemmung (17 Eintraege): 2,84 €/m²",
      "needs_review": true
    }
  ]
}
```

### 4.2 LV ohne Gaps

**Request:** `GET /api/v1/lvs/abc.../gaps`

```json
{
  "lv_id": "abc12345-…",
  "total_positions": 8,
  "total_materials": 34,
  "gaps_count": 0,
  "missing_count": 0,
  "estimated_count": 0,
  "low_confidence_count": 0,
  "gaps": []
}
```

### 4.3 LV mit include_low_confidence=true, nur low_confidence

**Request:** `GET /api/v1/lvs/abc.../gaps?include_low_confidence=true`

```json
{
  "lv_id": "abc12345-…",
  "total_positions": 12,
  "total_materials": 48,
  "gaps_count": 3,
  "missing_count": 0,
  "estimated_count": 0,
  "low_confidence_count": 3,
  "gaps": [
    {
      "position_id": "e7f2...",
      "position_oz": "02.01.01",
      "position_name": "Metallstaenderwand W112",
      "material_name": "UW 75",
      "material_dna": "Knauf|Profile|UW|75|",
      "required_amount": 0.85,
      "unit": "m",
      "severity": "low_confidence",
      "price_source": "supplier_price",
      "match_confidence": 0.42,
      "source_description": "Kemmler-Listenpreis 2,15 €/m (unsicher, bitte pruefen)",
      "needs_review": true
    }
  ]
}
```

---

## 5. Material-Namen-Ableitung aus DNA

**Regel:**

Das DNA-Pattern hat das Format
`Hersteller|Kategorie|Produktname|Abmessungen|Variante`.

Für `material_name` werden die Teile 3 (Produktname) und 4
(Abmessungen) genommen, durch ein Leerzeichen verbunden,
leere Segmente verworfen.

**Beispiele:**

| DNA | material_name |
|---|---|
| `Knauf\|Profile\|CW\|75\|` | `"CW 75"` |
| `\|Gipskarton\|Fireboard\|12.5\|` | `"Fireboard 12.5"` |
| `Knauf\|Profile\|\|\|Spezial` | `"Spezial"` (nur Variante) |
| `\|\|\|\|` | (fällt durch) |
| `keine pipe drin` | (fällt durch) |

**Fallback:** wenn `material_name` nach dem Parsing leer ist, wird das
komplette `material_dna`-Feld als material_name verwendet. Niemals
leerer String — die UI soll immer etwas anzeigen können.

Implementierungs-Hinweis: `material_dna` wird **immer** zusätzlich
ausgegeben, auch wenn material_name erfolgreich abgeleitet wurde.
Das hält Debug-Fälle lesbar.

---

## 6. Sortier-Reihenfolge der gaps-Liste

Primär nach `severity` in dieser Priorität:

1. `missing`
2. `low_confidence`
3. `estimated`

Sekundär nach `position_oz` (lexikographisch, damit die Ausgabe der
LV-Reihenfolge folgt).

Tertiär nach dem Auftreten im `materialien`-JSON-Array
(Rezept-Reihenfolge).

Diese Sortierung ist deterministisch — zwei aufeinanderfolgende
Aufrufe liefern dieselbe Reihenfolge (Test 10).

---

## 7. Service-Logik (Skelett)

```python
def compute_lv_gaps(
    lv: LV,
    include_low_confidence: bool = False,
) -> LVGapsReport:
    gaps: list[CatalogGapEntry] = []
    missing = estimated = low_conf = total_mat = 0

    severity_rank = {
        GapSeverity.missing: 0,
        GapSeverity.low_confidence: 1,
        GapSeverity.estimated: 2,
    }

    for pos in sorted(lv.positions, key=lambda p: p.reihenfolge):
        for m in (pos.materialien or []):
            total_mat += 1
            src = m.get("price_source")
            conf = m.get("match_confidence")

            sev = None
            if src == "not_found":
                sev = GapSeverity.missing; missing += 1
            elif src == "estimated":
                sev = GapSeverity.estimated; estimated += 1
            elif include_low_confidence and src == "supplier_price" \
                    and conf is not None and conf < 0.5:
                sev = GapSeverity.low_confidence; low_conf += 1

            if sev is None:
                continue

            gaps.append(CatalogGapEntry(
                position_id=str(pos.id),
                position_oz=pos.oz or "",
                position_name=pos.erkanntes_system
                    or (pos.kurztext or "")[:60],
                material_name=_material_name_from_dna(m.get("dna", "")),
                material_dna=m.get("dna", ""),
                required_amount=float(m.get("menge", 0.0)),
                unit=str(m.get("einheit", "")),
                severity=sev,
                price_source=str(src or ""),
                match_confidence=(
                    None if src == "not_found" else float(conf or 0.0)
                ),
                source_description=str(m.get("source_description", "")),
                needs_review=bool(m.get("needs_review", False)),
            ))

    gaps.sort(key=lambda g: (severity_rank[g.severity], g.position_oz))

    return LVGapsReport(
        lv_id=str(lv.id),
        total_positions=len(lv.positions),
        total_materials=total_mat,
        gaps_count=len(gaps),
        missing_count=missing,
        estimated_count=estimated,
        low_confidence_count=low_conf,
        gaps=gaps,
    )
```

---

## 8. Klarstellung zur Semantik von `include_low_confidence`

- **Default** (kein Query-Parameter): Response enthält nur
  `severity ∈ {missing, estimated}`. Das ist der „zeige mir die
  wirklichen Probleme"-Modus.
- **`?include_low_confidence=true`**: Response enthält zusätzlich
  `severity=low_confidence` für `supplier_price`-Matches mit
  `match_confidence < 0.5`. Das ist der „zeige mir alles was wackelig
  ist"-Modus.

Die Counter-Konsistenz gilt immer:
`gaps_count == missing_count + estimated_count + low_confidence_count`.
