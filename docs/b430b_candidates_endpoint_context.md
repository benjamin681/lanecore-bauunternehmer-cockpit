# B+4.3.0b — Candidates-Endpoint Kontext & Design-Vorbereitung

**Stand:** 22.04.2026 vormittags | **Zweck:** Planung des neuen
Endpoints `GET /api/v1/lvs/{lv_id}/positions/{pos_id}/candidates`
für den Near-Miss-Drawer in B+4.3.1. Kein Code geschrieben.

## Bestehende Bausteine (wiederverwendbar)

### Router + Auth
- `app/api/lvs.py` trägt bereits 10 Routes unter `/lvs/…`; der neue
  Endpoint fügt sich natürlich dort ein (nicht in eine eigene Datei).
- Auth-Pattern ist konsistent: `CurrentUser`-Dependency
  (`app/core/deps.py:16-35`) + `Position.lv_id == lv_id`-Filter +
  `LV.tenant_id == user.tenant_id`. 404 bei Miss.
- Position-ID-Handling gibt's bereits im PATCH-Endpoint
  (`/lvs/{lv_id}/positions/{position_id}`, Zeile 173) — das Muster
  kann 1:1 für den GET übernommen werden.

### Lookup-Logik
- `price_lookup._try_supplier_price` (Zeile 328–474) ist die
  „Hauptquelle" der Kandidaten. Stage 2c liefert aktuell nur den
  *einen* besten Kandidaten. Für Top-N brauchen wir eine leichte
  Erweiterung oder eine neue Helper-Funktion, die statt
  `_best_fuzzy` die ganze sortierte Kandidaten-Liste zurückgibt.
- `PriceLookupResult.lookup_details` (list[dict]) enthält schon den
  Audit-Trail pro Stage — ideal für den UI-Drawer, der „Stufe 1
  (Override) nicht geprüft, Stufe 2c mit Fuzzy 87 % getroffen"
  sichtbar macht.
- `_best_fuzzy` (`price_lookup.py`) hat bereits den Score pro
  Kandidat — wir müssen nur statt „nur den besten" alle Kandidaten
  samt Score zurückgeben.
- Blacklist-Pre-Filter und Unit-Toleranz sind bereits dort, wo wir
  sie brauchen; keine Duplikation nötig.

### Persistierte Daten auf Position
- `Position.materialien` (JSON-Array) enthält pro Material schon:
  - `dna` (Legacy), `menge`, `einheit`
  - `preis_einheit`, `gp`, `match_konfidenz`
  - `price_source`, `source_description`, `applied_discount_percent`,
    `needs_review`, `match_confidence` (neue B+4.2-Felder)
- Damit ist **der Winner** schon auf der Position persistiert — den
  müssen wir nicht neu berechnen, nur die Near-Miss-Kandidaten
  dazu liefern.

### Test-Patterns
- `tests/conftest.py` liefert das `client`-Fixture mit In-Memory-DB.
- `_register_and_login(client, email)` + `_auth(token)` sind die
  Standardbausteine aus `test_pricing_foundation.py`.
- Tenant-Isolations-Tests (z. B. `test_tenant_isolation_flag_off`)
  sind das Muster für die 403/404-Abdeckung.

## Offene Design-Fragen an Benjamin

### a) Kandidaten-Anzahl

- Mockup sieht Top-3 vor. Reicht **fix 3** oder lieber ein Query-
  Parameter `?limit=N` mit Default 3 und Max 10?
- **Empfehlung:** Default 3, mit `?limit`-Query-Parameter (Max 10),
  damit die UI später flexibler wird ohne API-Break.

### b) Felder pro Kandidat

Vorschlag:

```json
{
  "entry_id": "uuid-…",
  "pricelist_id": "uuid-…",
  "supplier_name": "Kemmler",
  "list_name": "Ausbau 2026-04",
  "product_name": "CW-Profil 100x50x0,6 mm …",
  "manufacturer": "Knauf",
  "article_number": "3580150467",
  "unit": "€/m",
  "effective_unit": "m",
  "price_net": 167.40,
  "price_per_effective_unit": 8.05,
  "match_confidence": 0.82,
  "match_stage": "supplier_price_fuzzy",
  "match_reason": "Fuzzy 0.82 auf Produktname + Einheit ~m",
  "is_winner": false,
  "excluded_reason": null
}
```

**Offene Detail-Fragen:**

1. Soll `match_confidence` als Zahl (0.0–1.0) oder übersetztes Label
   („fast sicher", „wahrscheinlich passend") raus? Der Wording-Guide
   empfiehlt Labels für die UI — aber die UI kann die Übersetzung
   selbst machen, API soll die Zahl liefern.
   **Empfehlung:** Zahl (0.0–1.0). UI-Mapping kommt in `stage-badge`.
2. Soll `match_stage` den feingranularen Stage-Code liefern
   (`supplier_price_2a` vs. `supplier_price_2b` vs. `supplier_price_2c`)
   oder nur den groben (`supplier_price` / `legacy_price` / usw.)?
   **Empfehlung:** grober Stage-Name + separates `match_reason` als
   Freitext („Artikelnummer exakt" / „Name+Hersteller exakt" /
   „Fuzzy 0.82").

### c) Umgang mit geblacklisteten Kandidaten

Zwei Optionen:

- **(i) Einblendung mit Flag:** `excluded_reason = "blacklist:UT"` +
  `is_winner=false`, Kandidat erscheint in der Liste, UI rendert ihn
  durchgestrichen oder grau. Transparent, aber mehr Rauschen.
- **(ii) Komplett ausblenden:** nur tatsächlich in Betracht gezogene
  Kandidaten. Klarer.

**Empfehlung: (ii) ausblenden.** Option (i) überlädt die UI mit
technischen Details, die der Handwerker nicht braucht. Die Blacklist
ist Produkt-interne Qualitätsmaßnahme, keine Information, die der
Bieter im Angebot sehen will.

### d) Stage-4-Schätzung als virtueller Kandidat

Wenn `price_source="estimated"` (keine echten Kandidaten):

- **(i) Einen einzelnen „virtuellen" Kandidaten** „Ø über Kategorie
  Profile der letzten 12 Monate" liefern, mit `is_winner=true` und
  niedriger Confidence.
- **(ii) Leere Kandidaten-Liste** + Status-Feld `"no_candidates"`.

**Empfehlung: (i) virtueller Kandidat.** Das Mockup zeigt im
„Richtwert"-Case keine Auswahl-Liste, aber der Drawer könnte
trotzdem den Schätzwert als einzelnen „Eintrag" zeigen mit Hinweis
„kein Katalog-Treffer, Durchschnittswert aus Kategorie". So sieht
der Handwerker den Rechenweg transparent.

### e) Performance

- Aktuell: `_try_supplier_price` iteriert in Python über alle
  Kandidaten (Unit-Filter + Blacklist + Fuzzy-Score). Kemmler-Pool ~
  327 Entries × ~4 Profile-Rezepte Materialien pro Position × ~100
  Positionen pro LV = ~130 000 Score-Berechnungen für einen vollen
  Kalkulations-Lauf. Das ist akzeptabel.
- Pro **einzelnem** Candidates-Call (UI-Drawer für eine Position):
  ~4 Materialien × ~327 = ~1300 Score-Berechnungen. Trivial.
- **Keine Pre-Filterung auf API-Ebene nötig.** Die Top-N-Auswahl
  passiert nach dem Scoring in Python.

## Implementierungs-Plan (für B+4.3.0c → B+4.3.1)

### Betroffene Dateien

| Datei | Art | Was |
|---|---|---|
| `app/services/price_lookup.py` | Erweiterung | Neue Funktion `list_candidates(…)` neben `lookup_price`, die statt nur des Gewinners eine sortierte Kandidaten-Liste liefert |
| `app/schemas/pricing.py` oder neue `app/schemas/candidates.py` | Neu | Pydantic-Schemas `CandidateOut`, `PositionCandidatesOut` |
| `app/api/lvs.py` | Erweiterung | Neuer Handler `list_position_candidates(lv_id, position_id, limit=3)` |
| `tests/test_lvs_candidates.py` *(neu)* | Tests | Happy-Path, 404 (fremder LV/Position), 401 (ohne Token), Tenant-Isolation, Limit-Query-Parameter, virtueller Kandidat bei Stage-4 |
| `docs/b430b_candidates_endpoint_spec.md` *(neu, optional)* | Doc | Endpoint-Doc + Response-Beispiel für Frontend-Entwicklung |

### Aufwandsschätzung

| Teil | Zeit |
|---|---|
| `list_candidates` in `price_lookup.py` + Unit-Tests | 1 h |
| Pydantic-Schemas | 0,5 h |
| Route in `lvs.py` + Handler | 0,5 h |
| Test-Suite (Happy + 3 Error-Fälle + Isolation) | 1 h |
| End-to-End-Smoke gegen Kemmler-DB | 0,5 h |
| **Gesamt** | **~3,5 h** |

### Abhängigkeiten

- Keine neuen Pakete.
- Keine DB-Migration.
- Kein Frontend-Code in diesem Block — der Drawer wird in B+4.3.1
  (Client-Component) gebaut, nutzt dann diese Route.

## Offene Punkte für Planungs-Session

1. Design-Fragen (a)–(d) entscheiden.
2. Wording-Mapping (Confidence-Zahl → UI-Label) im Frontend-Modul
   oder in einer kleinen Helper-Funktion in `src/lib/format.ts`
   vorbereiten.
3. Optional: Katalog-Lücken-Report (Tab `/gaps` aus B+4.3.0-
   Discovery) in gleichem Block mitnehmen — Datenquelle ist eine
   einfache Filterung über `needs_price_review=True`.

## Scope-Bilanz dieser Session

- Keine Änderung im Repo außer dieser Doc.
- Keine Endpoints angefasst.
- Keine Tests hinzugefügt.
- Kein Push.
