# Walkthrough: Review-UI + Bundgroesse-Widget (P4 Phase 2)

**Ziel:** Den UI-Pfad einmal manuell klicken und verifizieren, dass der
neue Bundgroesse-Widget im Review-Dialog die UA-Profile korrigiert und
die Korrektur persistent bleibt.

**Stand**: Backend + Frontend sind live. Auf Prod ist bereits EINE
UA-Position (UA48 BL=3000) via Backend-Script korrigiert — die siehst
du im UI schon als "reviewed". Du bearbeitest die restlichen 22.

---

## Vor dem Walkthrough

Die test2-Preisliste hat 27 needs_review-Eintraege nach dem Re-Parse,
davon nach dem Backend-Smoke-Test noch 26. Aufgeteilt grob:

- ~15 UA-Profile mit `review_reason=bundgroesse_fehlt` (1 davon reviewed)
- ~10 Einheiten-Probleme (`einheit_nicht_erkannt`)
- Rest: vereinzelt `preis_ausserhalb_korridor` / ohne strukturierten Grund

---

## Schritt 1 — Einloggen

1. Browser `https://kalkulane.lanecore-ai.de/login`
2. Einloggen als `test@web.de`.

## Schritt 2 — Zur Review-Seite

1. Navigiere zur Preisliste `test2`:
   `https://kalkulane.lanecore-ai.de/dashboard/pricing/c2cf526a-1b1c-4456-b2a5-f05e6c50ae77/review`
2. **Erwartung:** Die Seite laedt eine Filter-Leiste, Review-Grund-Chips
   ("Bundgröße fehlt", "Einheit nicht erkannt" etc.) und eine Tabelle
   mit den Eintraegen.
3. **Check:** Die Chip-Leiste sollte mindestens folgende Gruppen zeigen:
   - "Bundgröße fehlt (X)" mit X>=14
   - "Einheit nicht erkannt (Y)" mit Y>=8

## Schritt 3 — Filter auf Bundgroesse

1. Klicke den Chip **"Bundgröße fehlt"**.
2. **Erwartung:** Die Tabelle zeigt nur noch UA-Profile
   (UA48 / UA73 / UA98 in verschiedenen BL=2600..4000-Varianten).

## Schritt 4 — Einen UA-Eintrag oeffnen

1. Waehle UA48 BL=2600 (oder eine andere BL-Variante, die noch nicht
   reviewed ist).
2. Klicke die Zeile. Der **ReviewEntryDialog** oeffnet sich.
3. **Erwartung oben im Dialog:**
   - Graue Box "Originale Zeile aus dem PDF" mit dem monospaced
     Rohtext aus der Kemmler-PDF (z.B.
     `UA-Profil 48x40x2 mm BL=2600 mm - m. 1-reihiger Lochung 3575100046 318,80 €/m`).
   - Darunter eine **orange Box** mit der Ueberschrift
     **"Bundgröße nachtragen"**. Das ist das neue Widget.

## Schritt 5 — Bundgroesse eingeben + Preview checken

1. Im Input "Stück pro Bund" trage **6** ein.
2. **Erwartung:** Unter dem Input erscheint sofort die Live-Preview:
   `6 Stück × 2.6 lfm = 15.60 lfm pro Bund → 20.4359 €/lfm (aus 318.80 € Bundpreis)`
3. Die Checkbox **"Für künftige Uploads derselben Preisliste merken"**
   ist default an — lasse sie an.

## Schritt 6 — Speichern

1. Klicke **"Bundgröße anwenden"** (orange Button rechts unten in der
   Box).
2. **Erwartung:**
   - Dialog schliesst sich.
   - Toast-Notification "Gespeichert + für künftige Uploads gemerkt."
   - Die Tabellen-Zeile verschwindet aus der gefilterten Ansicht (weil
     needs_review=False) oder bleibt sichtbar, aber ohne den orangenen
     "offen"-Badge.

## Schritt 7 — DB-Verifikation (optional, fuer mich)

Benjamin: Diesen Schritt nicht selbst machen, den fahre ich per SSH
wenn du durch bist. Ich pruefe dann:

- `pieces_per_package=6` im Entry.
- `price_per_effective_unit` zwischen 13 und 22 (je nach BL-Variante).
- `needs_review=False`.
- `ProductCorrection`-Zeile mit `correction_type='pieces_per_package'`
  und gleicher Artikelnummer ist in der DB.

## Schritt 8 — Weitere UA-Profile

Wiederhole Schritte 4–6 fuer weitere UA-BL-Varianten, bis alle UAs
gruen sind:

- **UA48** bei 6 St/Bund: 2600, 2750, 3000, 3250, 3500, 4000 mm
- **UA73** bei 4 St/Bund: 2600, 2750, 3000, 3500, 4000 mm
- **UA98** bei 4 St/Bund: 2600, 2750, 3000, 3500 mm

Bei UA73 und UA98 statt "6" entsprechend "4" eingeben.

## Schritt 9 — Salach nochmal rechnen

Nach Korrektur aller UAs: LV `Salach "Ensemble-Höfe" 1.BA` neu
rechnen. Erwartete Summenwanderung:

| Zustand | Summe netto |
|---|---|
| Aktuell (0/15 UAs korrigiert) | 131.789 EUR |
| Nach allen 15 UA-Korrekturen | ~150–170 k (Schaetzung) |
| T&O-Benchmark (Referenz) | 103.536 EUR |

Die Summe wird STEIGEN (nicht fallen), weil die Matcher jetzt echte
UA-Preise findet und die Tuereroeffnungs-Positionen nicht mehr auf
EP=0 fallen.

## Bekannte Einschraenkungen

- **Pro Artikelnummer eine Korrektur:** Jede BL-Variante hat eine
  eigene Artikelnummer, also muss jede einzeln gemacht werden.
  Batch-Operation fuer einen ganzen Produkt-Typ (z.B. "alle UA48 auf
  6/Bund") ist P4.4-Scope.
- **Widgets fuer andere Review-Reasons fehlen:** `einheit_nicht_erkannt`,
  `preis_ausserhalb_korridor`, `bundpreis_vs_einzelpreis_unklar`
  bekommen ihre eigenen Widgets in P4.4.
- **Bisheriger Edit-Dialog-Pfad** (PATCH ueber `unit`/`price_net` etc.)
  bleibt unveraendert verfuegbar. Das Bundgroesse-Widget ist ein
  zusaetzlicher Pfad, kein Ersatz.

## Bei Problemen

- Toast "Speichern fehlgeschlagen": Backend-Logs pruefen
  (`docker compose logs backend --since 5m | grep -i correct`).
- Widget erscheint nicht: Eintrag hat moeglicherweise nicht
  `review_reason=bundgroesse_fehlt` im `attributes`-Feld. Das
  Widget ist bewusst eng an diesem Tag gebunden, damit es nicht bei
  falschen Kontexten auftaucht.
- Chip-Leiste fehlt ganz: Browser-DevTools → Network-Tab auf
  `/api/v1/pricing/entries/.../review` schauen. 404/401/500-Details.
