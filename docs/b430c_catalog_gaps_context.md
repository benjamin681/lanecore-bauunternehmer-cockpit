# B+4.3.0c — Katalog-Lücken-Report: Kontext & Design

**Stand:** 22.04.2026
**Zweck:** Planung vor Implementierung. Kein Code, kein Commit.
**Abhängigkeiten:** B+4.2 (price_source_summary, needs_price_review),
B+4.3.0b (Candidates-Endpoint als Nachbar-Route).

---

## 1. Bestehende Bausteine (wiederverwendbar)

### 1.1 Position-Ebene — was schon da ist

Auf `Position` (Model + `PositionOut`-Schema) existieren seit B+4.2 zwei
aggregierte Spalten (persistent, via Migration `d48e2b57c1fa`):

| Feld | Typ | Beschreibung |
|---|---|---|
| `needs_price_review` | `bool` | True, wenn **mindestens ein** Material der Position `needs_review=True` liefert |
| `price_source_summary` | `str` | Verdichtete Textform, z. B. `"4× supplier_price, 1× estimated, 1× not_found"` |

Das ist die bereits aggregierte Sicht. Für den Katalog-Lücken-Report
reicht sie aber nicht aus — wir brauchen das **Detail pro Material**,
nicht nur die Summary.

### 1.2 Material-Ebene — was im JSON steckt

Jede Position hat `materialien: list[dict]` (JSON-Spalte). Pro Item
liegen die B+4.2-Felder:

```json
{
  "dna": "Knauf|Profile|CW|75|",
  "menge": 1.15,
  "einheit": "m",
  "preis_einheit": 8.05,
  "gp": 9.26,
  "price_source": "supplier_price",  // override | supplier_price | legacy_price | estimated | not_found | legacy
  "source_description": "Kemmler-Listenpreis 8,05 €/m",
  "applied_discount_percent": null,
  "needs_review": false,
  "match_confidence": 0.93
}
```

**Das ist die Datenquelle für den Lücken-Report.** Wir brauchen keine
neue Tabelle, keine neue Migration, keine neue Datenlogik — wir
iterieren über bestehende Positionen + deren Materialien-JSON.

### 1.3 Endpoint-Nachbarschaft

| Endpoint | Zweck | Relation zu B+4.3.0c |
|---|---|---|
| `GET /pricing/pricelists/{id}/review-needed` | Listet `SupplierPriceEntry`-Reihen mit `needs_review=True` | Andere Ebene: **Preisliste-Einträge**, nicht **Kalkulations-Ergebnisse**. Kein Konflikt, kein Reuse. |
| `GET /lvs/{id}` | LV-Details inkl. aller Positionen + materialien-JSON | **Hier liegen die Daten**. Der neue Report filtert sie. |
| `GET /lvs/{id}/positions/{pos_id}/candidates` | Top-N Kandidaten pro Material | Ergänzender Endpoint: Report sagt „hier fehlt was", Candidates-Endpoint sagt „hier sind mögliche Alternativen". Frontend ruft beide sequentiell auf. |

**Kein bestehender Endpoint deckt „alle Lücken im LV" ab.** `review-needed`
arbeitet auf Preislisten-Einträgen, nicht auf Kalkulations-Ergebnissen.

### 1.4 Aggregation auf LV-Ebene

`LV.positionen_unsicher` (int) existiert — aber das ist ein Count über
`konfidenz < 0.85`, nicht über `price_source == not_found`. Nicht
direkt wiederverwendbar.

---

## 2. Design-Fragen mit Empfehlungen

### 2a) Was zählt als "Katalog-Lücke"?

**Optionen:**

| Option | Umfang | Vor- / Nachteil |
|---|---|---|
| A | Nur `not_found` | Strengste Definition. Handwerker sieht nur das, wo der Katalog zu 100 % versagt. Unterschätzt die Lücken (estimated ist oft ein Bluff). |
| B | `not_found` + `estimated` | Entspricht dem Benutzer-Erleben: „wo habe ich keinen echten Listenpreis?". Aktueller Stuttgart-LV: 62 estimated + 64 not_found = **126 lückenhafte Materialien**. |
| C | B + `low-confidence-fuzzy` (`supplier_price` mit `match_confidence < 0.5`) | Zeigt auch „wackelige" Matches. Groß — könnte überfordern. |

**Empfehlung: B** mit einem zusätzlichen `severity`-Feld
(`missing` / `estimated` / `low_confidence`). So kann die UI filtern
oder sortieren, aber Default ist B. Variante C lässt sich als
Query-Parameter `?include_low_confidence=true` nachrüsten, ohne das
Schema zu ändern.

### 2b) Aggregations-Ebene

**Optionen:**

| Option | Scope | Einsatz |
|---|---|---|
| A | Pro LV | Ein Report pro LV. Der Handwerker öffnet ein Angebot und sieht seine Lücken dort. |
| B | Tenant-weit | Liste aller Lücken über alle LVs. Zeigt Muster (z. B. „CW 75 fehlt in 4 von 7 LVs"). |
| C | Beide mit je einem Endpoint | Flexibel, aber doppelter Aufwand. |

**Empfehlung: A** für heute. Der Pilot-Use-Case ist „ich arbeite an
Angebot X und will sehen wo noch Preise fehlen". Tenant-weite Sicht
kann später nachgezogen werden (Stichwort: `/gaps` als Dashboard-
Widget). Für den Katalog-Lücken-Tab im Near-Miss-UI (B+4.3.1) reicht
LV-Scope.

**Route-Vorschlag:** `GET /api/v1/lvs/{lv_id}/gaps`

### 2c) Response-Struktur

**Material-Ebene** ist richtig — genau wie beim Candidates-Endpoint in
B+4.3.0b. Position-Ebene wäre zu grob (eine Position mit 6 Materialien
hätte einen einzigen „gap"-Eintrag, obwohl 4 Materialien matchen und
2 nicht).

**Vorgeschlagenes Schema:**

```python
class CatalogGapEntry(BaseModel):
    position_id: str
    position_oz: str              # z.B. "1.2.3"
    position_name: str            # erkanntes_system oder kurztext
    material_name: str            # aus DNA-Pattern ableitbar
    material_dna: str             # vollständiges Pattern
    required_amount: float
    unit: str
    severity: str                 # "missing" | "estimated" | "low_confidence"
    price_source: str             # "not_found" | "estimated" | "supplier_price"
    match_confidence: float
    source_description: str       # nutzbar im UI als Tooltip
    needs_review: bool

class LVGapsReport(BaseModel):
    lv_id: str
    total_positions: int
    total_materials: int
    gaps_count: int
    missing_count: int            # price_source=not_found
    estimated_count: int          # price_source=estimated
    low_confidence_count: int     # supplier_price + confidence<0.5 (nur wenn include_low_confidence=true)
    gaps: list[CatalogGapEntry]
```

### 2d) "Ursache"-Klassifikation?

**Vorschlag: ja**, aber minimal als `severity`-String (siehe 2c).
Drei Werte, keine Freitext-Erklärung (das bleibt dem Candidates-
Endpoint + UI überlassen):

- `missing` — `price_source == "not_found"`
- `estimated` — `price_source == "estimated"`
- `low_confidence` — `price_source == "supplier_price"` und
  `match_confidence < 0.5` (nur mit `?include_low_confidence=true`)

Die **differenzierten Handlungsempfehlungen** stehen im Candidates-
Endpoint (`match_reason`) und müssen hier nicht dupliziert werden.

---

## 3. Implementierungs-Plan

### 3.1 Datei-Pfade

| Datei | Änderung |
|---|---|
| `app/schemas/gaps.py` *(neu)* | `CatalogGapEntry` + `LVGapsReport` |
| `app/services/catalog_gaps.py` *(neu)* | `compute_lv_gaps(lv, include_low_confidence=False) -> LVGapsReport` — iteriert über `lv.positions` und deren `materialien`-JSON |
| `app/api/lvs.py` *(Erweiterung)* | Route-Handler `list_lv_gaps(lv_id, include_low_confidence=False)` direkt neben dem Candidates-Handler |
| `tests/test_lvs_gaps.py` *(neu)* | 8–10 Golden-Tests |

Kein Touch an Models, keine Migration, keine Schema-Änderung auf
bestehenden Endpoints. Rein additiv.

### 3.2 Service-Funktion (Kern-Logik)

```
def compute_lv_gaps(lv, include_low_confidence=False) -> LVGapsReport:
    gaps = []
    missing = estimated = low_conf = total_mat = 0
    for pos in lv.positions:
        for m in (pos.materialien or []):
            total_mat += 1
            src = m.get("price_source")
            conf = m.get("match_confidence", 1.0)
            if src == "not_found":
                severity = "missing"; missing += 1
            elif src == "estimated":
                severity = "estimated"; estimated += 1
            elif include_low_confidence and src == "supplier_price" and conf < 0.5:
                severity = "low_confidence"; low_conf += 1
            else:
                continue
            gaps.append(CatalogGapEntry(
                position_id=pos.id, position_oz=pos.oz,
                position_name=pos.erkanntes_system or pos.kurztext[:60],
                material_name=_extract_material_name(m.get("dna", "")),
                material_dna=m.get("dna", ""),
                required_amount=m.get("menge", 0.0),
                unit=m.get("einheit", ""),
                severity=severity,
                price_source=src,
                match_confidence=conf,
                source_description=m.get("source_description", ""),
                needs_review=bool(m.get("needs_review", False)),
            ))
    return LVGapsReport(
        lv_id=lv.id, total_positions=len(lv.positions),
        total_materials=total_mat,
        gaps_count=len(gaps),
        missing_count=missing, estimated_count=estimated,
        low_confidence_count=low_conf,
        gaps=gaps,
    )
```

### 3.3 Handler (Skelett)

```
@router.get("/{lv_id}/gaps", response_model=LVGapsReport)
def list_lv_gaps(
    lv_id: str,
    include_low_confidence: bool = Query(False),
    user: CurrentUser,
    db: DbSession,
):
    lv = db.get(LV, lv_id)
    if lv is None or lv.tenant_id != user.tenant_id:
        raise HTTPException(404)
    return compute_lv_gaps(lv, include_low_confidence)
```

### 3.4 Test-Liste (Vorschlag, 8–10 Tests)

1. **Happy Path** — LV mit 3 Positionen, 6 Materialien, 2 not_found → report.gaps_count == 2
2. **Estimated zählt** — Position mit estimated-Material → erscheint mit severity="estimated"
3. **Low-Confidence Default aus** — supplier_price mit confidence 0.4 → standardmäßig KEIN gap
4. **Low-Confidence opt-in** — `?include_low_confidence=true` → 0.4-Match erscheint mit severity="low_confidence"
5. **Legacy-Materialien ignoriert** — materialien mit `price_source="legacy"` oder ohne Feld → KEIN gap
6. **Counter-Konsistenz** — missing_count + estimated_count + low_confidence_count == gaps_count
7. **LV ohne Materialien** — Position ohne Rezept (Regiestunde) → gaps_count == 0
8. **404 bei fremdem Tenant** — User A ruft LV von Tenant B → 404
9. **401 ohne Auth** → 401
10. **Reihenfolge deterministisch** — gaps-Array in Positions-Reihenfolge

### 3.5 Vorgehen (Build-Block)

1. Baseline-Doc (diese Datei als Basis, ggf. minimaler Commit)
2. 10 Golden-Tests — alle rot (Endpoint existiert nicht)
3. Schema + Service + Handler — alle grün
4. Smoke gegen Stuttgart-LV: erwartete Zahlen 64 missing + 62 estimated = **126 gaps**
5. Commit + Push

---

## 4. Aufwandsschätzung

| Phase | Zeit |
|---|---|
| Baseline + Schema | 10 min |
| Golden-Tests (rot) | 30 min |
| Service + Handler | 30 min |
| Debug + Grün | 15 min |
| Smoke + Dokumentation | 20 min |
| **Gesamt** | **~1h45** |

Kosten: 0 $ (keine LLM-Calls). Risiko-Einschätzung: **niedrig** — keine
neuen Datenquellen, keine Matcher-Änderung, rein additives
Read-Modell.

---

## 5. Offene Mini-Fragen vor Phase 1

- **Material-Namen-Ableitung aus DNA:** das DNA-Pattern ist
  `Hersteller|Kategorie|Produktname|Abmessungen|Variante`. Für die UI-
  Anzeige reicht vermutlich Produktname + Abmessungen (z. B.
  „Gipskarton 12.5 mm"). Klare Regel dazu in Phase 1 finalisieren,
  damit nicht ein halber UI-Tab leer aussieht.

- **Sortierung im gaps-Array:** heute primär Position-Reihenfolge,
  sekundär Material-Reihenfolge im Rezept. Alphabetisch oder nach
  Häufigkeit wäre erst interessant, wenn tenant-weit aggregiert wird
  (spätere Phase).

- **Performance:** ein LV mit 102 Positionen × ∅ 5 Materialien =
  ~500 JSON-Items. Python-Iteration in < 50 ms erwartet. Kein
  Pre-Filter nötig.
