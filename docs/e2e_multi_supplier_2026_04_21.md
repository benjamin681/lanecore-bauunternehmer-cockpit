# E2E-Lauf — Stuttgart-LV mit 4 aktiven Preislisten (21.04.2026)

**Kontext:** Erster E2E-Lauf *nach* Parser-Upgrade (generic_prompt) und
Aktivierung aller 4 Preislisten (Kemmler, Wölpert, Hornbach Baumit,
Hornbach Putzbänder). Baseline war der Morgen-Lauf mit nur Kemmler aktiv.

**Tenant:** `e2e-test-2026-04-21` (`19f3cd31-...`)  |
**LV:** Stuttgart-Omega-Sorg (102 Positionen)  |
**Flag:** `use_new_pricing=True`

## Diff gegen Morgen-Baseline

| Metrik | Morgen (1 Liste, alter Parser) | Jetzt (4 Listen, generic_prompt) | Δ |
|---|---|---|---|
| Angebotssumme netto | 575.457,41 € | **959.557,53 €** | +384.100 € (+66,7 %) |
| Positionen gesamt | 102 | 102 | 0 |
| Positionen mit EP > 0 | 37 | **77** | +40 |
| Positionen mit EP = 0 | 65 | **25** | −40 |
| Material netto (bindend) | 88.585,90 € | 122.665,72 € | +34.080 € (+38,5 %) |
| Lohn netto (Σ über alle Pos.) | 702.118,70 € | 702.118,70 € | 0 ¹ |
| needs_price_review | 78 | 78 | 0 |
| Kalkulationsdauer | ~0,5 s | **1,31 s** | — |

¹ Bestehender Artefakt der Snapshot-Summierung: `lohn_ep` wird pro
Position auch dann berechnet, wenn `manuell_pruefen=True` (ep=0) —
dadurch ist die Summe über *alle* Positionen flagge-unabhängig.
Angebotssumme (GP) zählt jedoch korrekt nur die kalkulierten
Positionen, daher der +384k-Sprung.

## Stage-Verteilung (Material-Zeilen)

| Stage | Baseline | Neu | Δ |
|---|---|---|---|
| supplier_price | 95 (38,9 %) | **95 (38,9 %)** | 0 |
| estimated (Stufe 4) | 0 | **70 (28,7 %)** | +70 |
| not_found | 149 (61,1 %) | **79 (32,4 %)** | −70 |
| **Summe Material-Zeilen** | 244 | 244 | 0 |

**Kern-Befund:** Der Sprung von 37 → 77 kalkulierten Positionen kommt
**ausschließlich aus der `estimated`-Stage**. Die Anzahl *echter*
supplier_price-Matches ist **unverändert** (95). Der neue Parser hat
also keine neuen direkten Treffer gebracht — aber durch mehr
extrahierte Entries (z. B. Wölpert/Hornbach) greift die 12-Monate-
Kategorie-Mittelwerte-Schätzung (Stufe 4) häufiger.

## Multi-Lieferanten-Verhalten

| Lieferant | supplier_price-Matches | Aktiv? |
|---|---|---|
| Kemmler | **95** | ✓ |
| Wölpert | **0** | ✓ |
| Hornbach Baumit | **0** | ✓ |
| Hornbach Putzbänder | **0** | ✓ |

**Diagnose:** Alle 3 neu aktivierten Listen bringen **null** Matches
gegen das Stuttgart-LV. Strukturell erwartbar:

- **Wölpert** liefert Stuckateur-Zubehör (Drahtrichtwinkel, VWS
  Eckwinkel, Starcontact-Kleber) — thematisch nicht im Trockenbau-LV.
- **Hornbach Baumit** sind Putze, Gewebe, Leichtputze — Stuckateur-
  Kontext.
- **Hornbach Putzbänder** sind Putzbänder, Dichtmanschetten,
  Kleberschaum — ebenfalls Außen-/Innenputz.

Das Stuttgart-LV ist reines Trockenbau (W112/W116/W133/D112/W628A/W630),
dessen Materialien (GKB, CW/UW, ROCKWOOL, GKF) weiterhin nur Kemmler
führt. **Kein Matcher-Bug — die Listen passen zum Gewerk nicht.**

## Plausibilitäts-Stichproben

### Position 1.9.2.2.60 — W628A Schachtwand (123 m²)

```
Profil: 1x CW/UW 50 oder Winkelprofil 50
material_ep = 45,54 €/m² → ep = 110,41 €/m² → gp = 13.580,43 €
source_summary: 3× supplier_price, 2× estimated, 1× not_found

  ★ supplier_price: Kemmler Fuzzy (1.00) auf Produktname, ~m²      [GK-Platte]
    estimated     : Ø 20 Einträge Kategorie 'Profile', 12 Monate   [CW-Profil]
    estimated     : Ø 20 Einträge Kategorie 'Profile', 12 Monate   [UW-Profil]
  ★ supplier_price: Kemmler Fuzzy (1.00) auf Produktname, ~m²      [Dämmung]
    not_found    : manuell eingeben                                [Dichtungsband]
  ★ supplier_price: Kemmler Fuzzy (1.00) auf Produktname, ~kg      [Spachtel]
```

Plausibel: Gipskarton + Dämmung + Spachtel sitzen auf Kemmler; CW/UW-
Profile greifen nicht (Rezept-Dimensions-Pattern trifft die
Kemmler-Profil-Strings nicht — bekanntes Follow-up aus B+4.2.6).

### Position 1.9.2.2.70 — W630 Schachtwand F90 (206 m²)

Identische Struktur: 3 supplier_price, 2 estimated, 1 not_found.
material_ep 45,54 €/m², gp = 22.744,46 € — **plausibel** gegen manuellen
Referenzwert (üblich 40–60 €/m² Material für F90-Schachtwand).

### Position 1.9.2.2.50 — W133 Brandwand (135 m²)

material_ep = 112,81 €/m², ep = **0,00 €** weil `not_found` auf einem
Pflicht-Material (→ manuell_pruefen=True setzt EP/GP auf 0). Korrektes
Verhalten: zweilagige Wand W133 hat kein dediziertes Kemmler-Match für
eine der 6 Material-Zeilen, deshalb zurückhaltendes EP=0.

## Qualitative Beurteilung

| Kriterium | Befund |
|---|---|
| Keine Regression (Morgen→Jetzt) | ✓ identische supplier_price-Zahl |
| Mehr kalkulierbare Positionen | ✓ 37 → 77 (+40) |
| Plausible EP-Werte in Stichproben | ✓ 45–113 €/m², Markt-konform |
| Multi-Lieferanten greift | ✗ 0 Matches aus Wölpert/Hornbach ² |
| Gebinde-Auflösung bei Pack/Ktn. | ✗ CW/UW weiterhin estimated |

² Nicht blockend — strukturelle Folge, dass die 3 Listen nicht das
gleiche Gewerk bedienen.

## Gesamt-Bewertung: Pilot-ready für Yildiz?

**Bedingt ja.** Für einen Pilot-Kunden im Trockenbau-Gewerk mit einer
Kemmler-Preisliste ist der Stand jetzt deutlich nutzbarer als heute
Morgen:

- **Mehr als doppelt so viele Positionen** (77 vs. 37) liefern
  Kalkulationen.
- **Keine Faktor-Fehler** (Parser-Upgrade bewiesen).
- **Plausible €/m²-Werte** in der Stichprobe.

Aber der Pilot muss **wissen**, dass:

- 70 Material-Zeilen auf **Stufe-4-Schätzungen** (Kategorie-Mittelwert
  der letzten 12 Monate) beruhen — nicht auf echten Kemmler-Preisen.
- 79 Material-Zeilen (32 %) weiterhin `not_found` sind.
- `needs_price_review` bei 78/102 Positionen (76 %) True ist → der
  Review-Schritt im UI ist Pflicht, kein optionales Feature.

### Bekannte Blocker für *produktive* Auslieferung

1. **CW/UW-Profile-Matching** (Kemmler-Katalog hat die Profile, das
   Rezept-DNA-Pattern trifft sie nicht). Follow-up aus B+4.2.6, noch
   offen. Lösung: Dimensions-normalisierung im DNA-Matcher.
2. **Gebinde-Preise (100 Stk/Ktn.)** werden nicht auf Einzelpreis
   umgerechnet, wenn die Konversion nur im Produktnamen steht.
3. **Schätzwert-Markierung in der Kalkulation-PDF** — die 70
   estimated-Einträge müssen für den Kunden als "Schätzwert, nicht
   verbindlich" erkennbar sein.

## Snapshot

`tests/live/e2e_multi_supplier_after_parser_upgrade.json` (gitignored,
nur lokal auf Benjamins Entwicklungsmaschine).
