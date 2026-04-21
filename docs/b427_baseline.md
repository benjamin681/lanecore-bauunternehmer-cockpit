# B+4.2.7 Teil 1 — Baseline vor der Resolver-Erweiterung

**Stand:** 21.04.2026 | **Branch:** `claude/beautiful-mendel` | **Scope:** nur
`app/services/package_resolver.py` erweitern, kein Worker-/E2E-Touch heute.

## Aktuelle Muster in `resolve_package`

Die Funktion greift **nur wenn** `_is_gebinde(unit) == True` (siehe
`package_resolver.py:146`), d. h. die Einheit ist aus der Menge
`{Ktn., Karton, Pak., Paket, Packung, Bd., Bund, Rolle, Rol., Rollen}`.
Danach wird der Produktname gegen 4 Regex-Muster geprüft (Reihenfolge
relevant, spezifischer zuerst):

| Regel | Regex-Name (Zeile) | Beispiel-Trigger | Ergebnis |
|---|---|---|---|
| R1 | `_PAT_PIECES_PER_GEBINDE` (84–87) | `"100 Stk/Ktn."`, `"50 St./Pak."`, `"60 St./Bd."` | `("Stk.", price/N)` |
| R2 | `_PAT_M_PER_GEBINDE` (88–91) | `"50 m/Rolle"`, `"30 m/Rol."` | `("m", price/N)` |
| R3 | `_PAT_M2_PER_GEBINDE` (92–95) | `"7,5 m²/Pak."` | `("m²", price/N)` |
| R4 | `_PAT_GEBINDE_EQ_PIECES` (98–101) | `"Paket = 100 Stk."`, `"à 50 Stk."` | `("Stk.", price/N)` |

## Welche Fälle greifen heute, welche nicht

### Greift heute ✓

- **Karton-Stückzahl (R1):** „ASA01 Schnellabhänger 100 Stk/Ktn." →
  korrekter €/Stk.
- **Paket-Stückzahl (R1):** „Knauf Deckennagel 100 St./Pak." → korrekter
  €/Stk.
- **Rolle-Meter (R2):** Putzbänder, Folien mit `m/Rolle`
- **Paket-Quadratmeter (R3):** „Trennwandpl. 7,5 m²/Pak."

### Greift heute ✗ (Lücke, die B+4.2.7 schließen soll)

Entries mit **`unit="€/m"`** (kein Gebinde), aber **`pieces_per_package` +
`package_size` bereits vom Parser gefüllt**. `_is_gebinde("€/m")` ist False
→ `resolve_package` exitet sofort zurück mit `(unit, price)` unverändert.

## Kemmler-Katalog-Stichprobe: Betroffene Entries

Abfrage: `unit IN ('€/m','€/lfm','€/lfdm') AND pieces_per_package IS NOT
NULL`. Ergebnis: **11 Einträge** im Kemmler-Katalog (04/2026):

| Produkt | price_net | pieces | package_size | Korrekter €/m |
|---|---|---|---|---|
| **CW-Profil 100×50×0,6 mm 8 St./Bd.** | 167,40 | 8 | 2,6 m | 167,40 / (8×2,6) = **8,05** |
| Kemmler TR Kantenprofil 3502 ALU, BL=2500 mm | 59,66 | 50 | 2,5 m | 59,66 / 125 = **0,477** |
| Kemmler TR Kantenprofil 3502 ALU, BL=3000 mm | 59,66 | 50 | 3,0 m | 59,66 / 150 = **0,398** |
| Prima ALU Kantenprofil 9539 | 66,80 | 50 | 2,5 m | 66,80 / 125 = **0,534** |
| TB Einfaßprofil 3735 PVC BL=2500 mm | 116,32 | 50 | 2,5 m | 116,32 / 125 = **0,931** |
| TB Einfaßprofil 3741 PVC BL=2500 mm | 52,40 | 50 | 2,5 m | 52,40 / 125 = **0,419** |
| TB Abschlussprofil 3768 PVC BL=3000 mm | 190,62 | 20 | 3,0 m | 190,62 / 60 = **3,18** |
| TB Kantenschutzprofil 9179 ALU BL=2500 mm | 289,86 | 25 | 2,5 m | 289,86 / 62,5 = **4,64** |
| construkt cliq 24CT (BL=625 mm) | 1,40 | 60 | 0,625 m | 1,40 / 37,5 = **0,0373** |
| construkt cliq 24CT (BL=1250 mm) | 1,40 | 60 | 1,25 m | 1,40 / 75 = **0,0187** |
| construkt cliq 24MR Tragprofil BL=3750 mm | 1,40 | 20 | 3,75 m | 1,40 / 75 = **0,0187** |

**Gemeinsamer Nenner:** Produktbeschreibung enthält `BL=XXX mm` (Bundellänge
pro Stange), Parser liest `pieces_per_package` (Stangen pro Bund) und
`package_size` (Länge in m) korrekt heraus — aber `price_per_effective_unit`
bleibt beim Bundle-Gesamtpreis stehen, weil die Resolver-Regel fehlt.

## Weitere „St./Bd."-Entries, die eigener Pfad sind

Drei Entries mit `unit="€/Bund"` (echtes Gebinde) + „100 Stk/Bd." im Namen:

| Produkt | price_net | Heutiger Stand | Gehört zu |
|---|---|---|---|
| Kemmler ADÖ375 Abhängedraht mit Öse 100 Stk/Bd. | 12,49 €/Bund | ppe=12,49 (nicht entpackt) | **R1** (müsste greifen — Backfill ruft aber nicht; Worker-Integration = Teil 2) |
| Kemmler ADÖ500 Abhängedraht mit Öse 100 Stk/Bd. | 16,67 €/Bund | ppe=16,67 | R1 |
| Kemmler ADÖ750 Abhängedraht mit Öse 100 Stk/Bd. | 25,76 €/Bund | ppe=25,76 | R1 |

→ Diese 3 sind **nicht** Ziel von Teil 1, weil die bestehende R1 sie schon
abdeckt; sie werden nur nicht angewandt, weil `backfill_effective_units`
nicht in der Produktionskette hängt (Teil-2-Thema).

## Planung für Teil-1-Fix

Neue **Regel R6** in `resolve_package`:

- **Bedingung:** Eingang ist nicht direkt ein Gebinde
  (`_is_gebinde(unit) == False`), aber `unit` ist ein Längen-Typ
  (`m`/`lfm`/`lfdm`). Zusätzliche Parameter nötig:
  `pieces_per_package` + `package_size` + `package_unit` müssen gesetzt sein.
- **Berechnung:** `price_per_effective_unit = price_net / (pieces × size_in_m)`
- **Einheit-Normierung:** `package_unit="mm"` → ÷1000.

### Design-Frage für Phase 3

`resolve_package(unit, product_name, price)` hat heute keine Zugriff auf
strukturelle Felder. Optionen:

- **A — Signatur erweitern:** optional `pieces_per_package`, `package_size`,
  `package_unit` ergänzen. Direktste Lösung, aber Signatur-Break für
  bestehende Aufrufer (`smoke_lookup.py`, `test_package_lookup.py`).
- **B — Neue Funktion `resolve_bundle_per_meter(entry)`** nebenan, nur
  für diesen Fall. `backfill_effective_units` ruft sie zusätzlich.
- **C — Muster aus Produktnamen lesen:** „8 St./Bd." + „BL=2600 mm" als
  weiterer Regex, analog zu R1–R4. Bleibt innerhalb der bestehenden API,
  aber duplikat zu dem, was der Parser schon ausgelesen hat.

Phase-3-Entscheidung kommt nach Freigabe. Option B wirkt am saubersten
(Separation of Concerns, keine Breaking Change).

## Scope-Begrenzung (unverändert)

- **Nicht in Teil 1:** `backfill_effective_units` im Worker verdrahten.
- **Nicht in Teil 1:** E2E-Lauf auf Stuttgart-LV.
- **Nicht in Teil 1:** Push auf Remote.
