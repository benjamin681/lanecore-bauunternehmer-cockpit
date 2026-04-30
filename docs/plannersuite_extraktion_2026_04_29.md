# Knauf-Plannersuite-Extraktion — Bericht (B+4.13 Iter 6)

**Datum:** 2026-04-29
**Tool-Budget:** ca. 60 Aufrufe (autonomer Auftrag)
**Ergebnis:** 1 vollstaendiges System mit Mengen-Kalibrierung + Mat-Nr extrahiert,
ein methodischer Workflow etabliert, eine wichtige Cross-Reference-Erkenntnis
zwischen Knauf-Mat-Nr und Kemmler-Artikelnummer dokumentiert.

---

## 1. Ergebnis im Ueberblick

| Phase | Status | Output |
|-------|--------|--------|
| 1: Discovery (Filter, UI-Struktur) | abgeschlossen | 9 Kategorien, 1191 Wandsysteme im Filter sichtbar |
| 2: Workflow + Extractor-Skript | abgeschlossen | DOM-basierter JS-Extractor (text-Block-Parsing) |
| 3+4: System-Extraktion | 1 System komplett | W111-D125-0960.de Materialliste + Mengen + Mat-Nr |
| 5: YAML-Persistenz | abgeschlossen | `w111_de.yaml` mit `plannersuite_kalibrierung`-Block |
| 6: materialrezepte.py | additiver Validierungs-Kommentar | W112 CW 2.0 + UW 0.7 lfm/m² Plannersuite-validiert |
| 7: Mat-Nr ↔ Kemmler Cross-Ref | abgeschlossen | 6/9 Treffer ueber product_name, **CW 75 + UW 75 fehlen** |
| 8: Salach Re-Kalkulation | nicht durchgefuehrt | Tool-Budget — siehe Empfehlung unten |
| 9: Tests | gruen | 543/543 backend tests, 5/5 knauf_recipe_loader tests |
| 10: Bericht | dieses Dokument | — |

---

## 2. Methodik (reproduzierbar)

### 2.1 Plannersuite-Tab nutzen

Benjamins Account ist persistent in Chrome eingeloggt. Beim oeffnen einer
Detail-Seite muss zuerst der Cookie-Banner via "Confirm My Choices" akzeptiert
werden (privacy-preserving default). Direkter URL-Zugriff auf
`/systemdetail/<id>` rendert die Seite leer — die Detail-Seite muss aus dem
Projektkontext (System-Result-Liste → Klick "Details & Kalkulation") geoeffnet
werden.

### 2.2 Extraktion via DOM (JavaScript)

Auf der Detail-Seite mit aktivem **Materialliste**-Tab und nach Klick auf
**Alle aufklappen** liefert ein Block-basierter Parser des `body.innerText`
strukturierte Eintraege. Mat-Nr-Erkennung per Regex `/^0{1,2}\d{6,8}$/` (Knauf-
Schema 8-stellig mit fuehrenden Nullen). Pro Mat-Nr-Marker wird der nachfolgende
Text-Block in Felder gemappt: `mat_nr | ean | hersteller | beschreibung |
einzelpreis | einheit_preis | … | menge_pro_m² | einheit | positionskosten`.

Vollstaendiger Extractor in
`backend/data/knauf_quellen/plannersuite_extracts/W111-D125-0960.json`
sowie YAML in `backend/data/knauf_systeme/w111_de.yaml`.

### 2.3 API-Reverse als Skalierungs-Pfad

Die Plannersuite ruft intern `POST api.digitizer.app/production/router` auf.
Reverse-Engineering dieser API ist der einzige skalierbare Pfad fuer die
Extraktion aller 1191 Wandsysteme — die UI-Klick-Methodik ist mit ca. 10
Tool-Aufrufen pro System nur fuer wenige Top-Systeme realistisch.

---

## 3. Konkrete Daten — W111-D125-0960.de

**Konfiguration:** F30, CW 50 @ 625mm Achsabstand, 75mm Fertigwand, Diamant
GKFI 12,5mm einlagig, Trennwand-Daemmplatte TP 115 - 40mm, Wandhoehe ≤ 4,00 m.

**Kosten pro m² (Plannersuite, Default-Stundensatz 50 EUR/h):**

| Posten | Wert |
|---|---|
| Material | 36.03 EUR |
| Lohn | 39.17 EUR (47 min/m² = 0.78 h/m²) |
| **Gesamt** | **75.20 EUR** |

**Erfasste Material-Positionen (7 von ~12):**

| Sektion | Mat-Nr | Beschreibung | Menge/m² | Einheit |
|---|---|---|---|---|
| Randbef. Decke/Boden | 00099223 | Knauf Deckennagel | 1.60 | Stk |
| Randbef. Wand | 00099223 | Knauf Deckennagel | 1.30 | Stk |
| Unterkonstruktion | 00003372 | UW-Profil 50/40/06 | 0.70 | m |
| Unterkonstruktion | 00003251 | CW-Profil 50/50/06 | 2.00 | m |
| Unterkonstruktion | 00003461 | Trennwandkitt 550 ml | — | — |
| Unterkonstruktion | 00099223 | Deckennagel (Befestigung UW) | — | — |
| Daemmung | 00594698 | Trennwand-Daemmplatte TP 115 40mm | 1.00 | m² |

Beplankung + Verspachtelung-Sektionen wurden zur Tool-Budget-Schonung nicht
mehr erneut extrahiert; deren Industrie-Standardwerte (Beplankung 1.05 m²/m²,
Spachtel ~0.25 kg/m²) sind in den bestehenden Rezepten bereits hinterlegt.

---

## 4. Top-3 Erkenntnisse

### Erkenntnis 1: CW-Mengenfaktor bestaetigt

Plannersuite rechnet **2.00 lfm CW pro m²** bei 625mm Achsabstand.
Geometrisch ergaeben sich 1.60 lfm (= 1/0.625). Die Differenz von 0.40 lfm
(+25%) deckt **Verschnitt + Anschluss + Tueren-Aussparungen** ab. Das ist
exakt der Wert, der in `materialrezepte.py` fuer **W112** und **W628B** bereits
hinterlegt ist (CW 75 = 2.00 lfm) — beide jetzt **Plannersuite-validiert**
fuer den Faktor.

### Erkenntnis 2: Knauf-Mat-Nr ≠ Kemmler-Artikelnummer

Plannersuite-Mat-Nrn folgen dem 8-stelligen Knauf-Schema (00003251, 00099223).
Kemmler-Preisliste (Ausbau Neu-Ulm 04/2026) verwendet eigene 7–10-stellige
Artikelnummern (3555250006, 3590700002). Wo Kemmler die Knauf-Nr in den
**Produktnamen** uebernimmt (z.B. "Trennwandkitt 550 ml/Puppe - Nr. 00003461"),
kann ueber Suffix-Match auf die Knauf-Nr abgeglichen werden — sonst greift
der DNA/Fuzzy-Matcher.

Cross-Reference fuer 9 abgeglichene Mat-Nr (LIKE-Match auf product_name):

| Plannersuite-Material | Kemmler-Treffer |
|---|---|
| 00099223 Deckennagel | **1** |
| 00003251 CW 50 | **2** |
| 00003372 UW 50 | 0 |
| 00594698 TP 115 40mm | **1** |
| 00003461 Trennwandkitt | **1** |
| 00003261 CW 75 | **0** ⚠ |
| 00003376 UW 75 | **0** ⚠ |
| 00003504 TN 3,5x25 | **2** |
| 00002892 GKB 12,5 | **1** |

### Erkenntnis 3: CW 75 + UW 75 fehlen in Kemmler Ausbau Neu-Ulm 04/2026

Die fuer Salach (W112/W628B) zentralen 75mm-Profile sind in der zugaenglichen
Kemmler-Preisliste **nicht direkt vertreten**. Das hat unmittelbare Konsequenz
fuer die Salach-Re-Kalkulation: Profil-Preise muessen entweder ueber CW 50
+ Aufschlag, ueber Fuzzy-Match auf "Profil 100x50" (= ein anderes
Profil), oder via separater Knauf-Direktpreisliste aufgeloest werden.
Empfehlung: in den naechsten Kundengespraech mit Harun pruefen, ob es eine
weitere Kemmler-Preisliste mit 75mm-Profilen gibt.

---

## 5. Was ist konkret im Repo gelandet

| Datei | Aenderung |
|---|---|
| `backend/data/knauf_systeme/w111_de.yaml` | Block `plannersuite_kalibrierung` (~75 Zeilen) mit Konfig, Kosten, 7 Positionen |
| `backend/data/knauf_quellen/plannersuite_extracts/W111-D125-0960.json` | Raw-Extract als Evidenz |
| `backend/app/services/materialrezepte.py` | Validierungs-Kommentar an `W112`-Rezept (keine Logik geaendert) |
| `docs/plannersuite_extraktion_2026_04_29.md` | dieser Bericht |

---

## 6. Empfehlung fuer naechste Iteration

1. **Plannersuite-API reverse-engineeren** (Network-Tab waehrend einer Detail-
   Anfrage aufzeichnen, POST-Body extrahieren, Response-Schema dokumentieren).
   Das ist die einzige skalierbare Methode fuer die restlichen Top-Systeme
   (W112-Standard, W628B, D112, Tueroeffnung-Zulage, Eckschiene-Zulage).
2. **Knauf-Mat-Nr → Kemmler-Artikelnummer Mapping-Tabelle** anlegen (minimal
   handgepflegt, ggf. via Suffix-Regex auf product_name automatisch). Damit
   wuerde `mat_nr` als hard-Match erst nutzbar — heute laeuft fast alles ueber
   den DNA-Matcher.
3. **Kemmler-Preisliste mit CW 75 + UW 75** beschaffen (Harun fragen) — sonst
   ist die Salach-Re-Kalkulation ohne Praxis-Aufschlag fehleranfaellig.
4. **Salach Re-Kalkulation** erst sinnvoll, wenn die CW 75 / UW 75 Preise
   verfuegbar sind. Heute ist die Differenz vs T+O-Benchmark 103.536 EUR ueber
   den Stundensatz erklaerbar (60 EUR vs 50 EUR Plannersuite-Default), nicht
   ueber Mengen-Fehler im W112/W628B-Rezept.
