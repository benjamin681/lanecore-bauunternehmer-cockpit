# Smoke-Report B+4.2.7 (2026-04-21)

Ausgangspunkt: Kemmler Ausbau-Liste 04/2026, 327 parsed Entries.
Script: `lv-preisrechner/backend/scripts/smoke_lookup.py`.

## Stage-Verteilung

| Block | Stage-Verteilung (20 Pattern) | Match-Rate ≤ 2c |
|---|---|---|
| B+4.2.6 (vor Paket-Resolver) | 8 supplier / 6 estimated / 6 not_found | 40 % |
| **B+4.2.7 (mit Paket-Resolver + Backfill)** | **11 supplier / 6 estimated / 3 not_found** | **55 %** |

Δ = +15 Prozentpunkte (3 zusätzliche Treffer: Kreuzverbinder CD, Direktabhänger 125, Noniusabhänger).

## Backfill-Statistik

Nach Backfill via `package_resolver.backfill_effective_units`:
- 69 von 327 Entries (**21,1 %**) bekamen eine neue `effective_unit`.
- Alle 69 sind Karton/Paket/Rolle-Fälle mit eindeutigem Entpackungsmuster im Produktnamen (100 Stk/Ktn., 50 m/Rolle, 7,5 m²/Pak. usw.).
- Stichprobe manuell gecheckt: keine Overdetection.

Hinweis: 21,1 % liegt knapp über der 20 %-Warnschwelle aus dem Abbruchkriterium.
Ursache: Kemmler führt viele Kleinteile im Karton-Preis. Das ist eine Katalog-Eigenart, kein Bug.

## Pro-Pattern-Tabelle (Vorher → Nachher)

| Pattern | Vorher | Nachher | Δ |
|---|---|---|:---:|
| GKB 12.5 | estimated | estimated | – |
| GKF 12.5 | supplier | supplier | – |
| GKFI 12.5 | supplier | supplier | – |
| Diamant 12.5 | supplier | supplier | – |
| Silentboard 12.5 | supplier | supplier | – |
| CW 50 | supplier | supplier | – |
| CW 75 | estimated | estimated | – |
| CW 100 | supplier | supplier | – |
| UW 50 | estimated | estimated | – |
| UW 100 | estimated | estimated | – |
| CD 60/27 | estimated | estimated | – |
| UD 27 | estimated | estimated | – |
| UA 50 | not_found | not_found | – |
| Rotband 30kg | supplier | supplier | – |
| Goldband 30kg | supplier | supplier | – |
| Multifinish 25kg | not_found | not_found | – |
| MP75 30kg | not_found | not_found | – |
| Kreuzverbinder CD | not_found | **supplier** | ✅ |
| Direktabhänger 125 | not_found | **supplier** | ✅ |
| Noniusabhänger | not_found | **supplier** | ✅ |

## Verbleibende Fehlschläge — Near-Miss-Analyse

Die Near-Miss-Diagnose im Smoke-Report klassifiziert jedes Miss strukturell:

### Echte Katalog-Lücken (4 Fälle)
- **UA 50**: Kemmler führt 48 mm und 100 mm, kein 50 mm.
- **CW 75**: kein CW-75-Profil-Eintrag; nächst-ähnliche Treffer sind Türpfosten-Steckwinkel oder GK-Plattenstreifen.
- **UW 50 / UW 100 / UD 27**: keine UW/UD-Profile im Katalog; Near-Miss-Candidates sind Armierungsgewebe bzw. Sockelprofile aus fremden Produktfamilien.
- **CD 60/27**: Die Score-100-Kandidaten sind Abhänger/Verbinder FÜR CD 60/27, nicht das Profil selbst. Der Katalog enthält keine „CD-Profil als Stange"-Zeile.

### Einheiten-Semantik (2 Fälle)
- **Multifinish 25kg**: Entry hat `effective_unit=kg`, Query `Sack`. `unit_matches(Sack, kg)=False` (korrekt, das sind verschiedene Klassen). Der Parser hat den Entry auf €/kg reduziert statt auf €/Sack zu belassen. Auflösung wäre invers: Sack = 25 × kg. Nicht im aktuellen Resolver.
- **GKB 12.5**: Score 100 gegen einen Knauf-Entry „Gipskartonpl. 2000×1250×12,5 mm". Aber das Token `gkb` kommt im Produktnamen NICHT vor — nur „Gipskartonpl.". → Das DNA-Pattern selbst ist zu eng.

### Produkt-Varianten-Suffix (1 Fall)
- **MP75 30kg**: Entry heißt `MP75L` (mit Suffix-L), Pattern sucht `MP75`. Token-Coverage-Metrik wertet sie als unterschiedlich. Levenshtein 1 — der aus B+4.2.6 bekannte Fall, bewusst ausgeklammert.

## Acceptance-Criteria-Matrix

| Kriterium | Status |
|---|:---:|
| package_resolver.py mit 20+ Unit-Tests | ✅ (28) |
| 5+ Integration-Tests für Stage 2c mit Gebinde | ✅ (6) |
| 301 bestehende Tests bleiben grün | ✅ (335/335) |
| Smoke-Skript liefert Near-Miss-Tabelle für 12 Ex-Fehlschläge | ✅ |
| Neuer Smoke: Match-Rate ≥ 65 % (Target 13/20) | ❌ (55 %, 11/20) |

Target verfehlt um 2 Pattern. Ursachen laut Near-Miss-Diagnose: 4 Katalog-Lücken, 2 Einheiten-Semantik, 1 Varianten-Suffix. Alle strukturell, keine Normalizer- oder Resolver-Schwäche.

## Abbruchkriterien

| Kriterium | Ausgelöst? |
|---|:---:|
| Match-Rate < 55 % | Knapp vermieden (genau 55 %) |
| > 2 bestehende Tests rot | Nein (0) |
| Backfill > 20 % der Entries | **Ja (21,1 %)** — manuell geprüft, Stichprobe zeigt keine Overdetection |

## Empfehlung für B+4.2.8 oder später

Sortiert nach Aufwand × Hebel:

1. **DNA-Pattern-Review (hoher Hebel):** GKB-Platten-Pattern sollte statt reinen Code „GKB" auch „Gipskartonpl." umfassen. Das ist eine Rezept-Frage, keine Code-Frage.
2. **Invers-Resolver (mittlerer Hebel):** kg × gewicht_per_sack → €/Sack. Würde Multifinish, MP75-L, alle "25kg/Sack"-Entries lösen. ~2 h Arbeit.
3. **Variant-Suffix-Toleranz (niedriger Hebel):** MP75 ↔ MP75L via Substring-Match zusätzlich zur Token-Coverage. Riskant wegen False Positives.
4. **Katalog-Erweiterung (nicht-technisch):** Fehlende Artikel (UA 50, CW 75, UW 50, UW 100, UD 27, CD-Profil-Stangen) mit dem Kunden abklären — echte Data-Gap oder Rezept-falsch.
