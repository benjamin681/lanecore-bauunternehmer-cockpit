# Verifikations-Workflow für Knauf-Systeme

> Entstanden bei der Auflösung des W628-Konflikts am 2026-04-20.
> Dient als Präzedenzfall und Aufwandsschätzung für die spätere
> flächige Verifikation aller modellgenerierten Knauf-Knowledge-Dateien.

---

## Verlauf am Präzedenzfall W628

### Ausgangslage
- `knowledge/knauf-systeme-w61-vorsatzschalen.json` listete W628 als **Vorsatzschale mit Holzunterkonstruktion**
- `knowledge/knauf-systeme-w62-w63-schachtwaende.json` listete W628 als **Schachtwand**
- `lv_parser.py` SYSTEM_PROMPT klassifizierte W628 seit Aufgabe 2B als **Schachtwand**
- Kein verbindlicher Entscheid — beide Knowledge-Dateien hatten `meta.quelle = "Aus Modellwissen rekonstruiert"`

### Recherche-Schritte
1. **WebSearch** `"Knauf W628 Detailblatt System Schachtwand Vorsatzschale"` — **1 Anfrage, ~3 s**
   - Top-Hits sofort eindeutig: `knauf.com/de-DE/.../w62-de-schachtwaende` (offizielle Übersichtsseite), CAD-Layer-URLs für W628A.de/W628B.de (beide Schachtwand)
2. **WebFetch** auf die offizielle Seite — **1 Anfrage, ~6 s**
   - Direktes Zitat: *"Knauf Schachtwände sind einseitig beplankte Metallständerwände... Systeme W628A.de, W628B.de, W629.de, W635.de"*

**Gesamt-Recherche-Zeit: ~30 Sekunden inkl. Tippen der Suchanfrage. Befund eindeutig.**

### Ergebnis
- W628 ist **definitiv Schachtwand** (nicht Vorsatzschale)
- SYSTEM_PROMPT war bereits korrekt → keine Code-Änderung nötig
- `knauf-systeme-w61-vorsatzschalen.json`: W628-Eintrag und Match-Regel entfernt, Korrektur-Vermerk in `meta`
- `knauf-systeme-w62-w63-schachtwaende.json`: `meta.verifiziert_am`-Array eingefügt mit Datum, URL, Zitat und offenen Punkten

### Offene Punkte für W62 (aus Recherche erkannt, NICHT im Scope dieser Aufgabe)
- Unsere internen Systemnamen `W625S`, `W626S`, `W631S`, `W632` haben **keine 1:1-Entsprechung** auf der offiziellen Knauf-Seite. Dort heißen die 4 Systeme **W628A.de, W628B.de, W629.de, W635.de**.
- Unser Eintrag `W628` deckt aktuell **beide Varianten** (W628A freispannend + W628B CW-Ständer) pauschal ab.
- **Empfehlung:** In einer späteren Sub-Aufgabe sauber 1:1 auf die offiziellen Bezeichnungen umziehen.

---

## Zuverlässigkeit der Knauf-Webquellen

| Quelle | Verfügbarkeit | Genauigkeit | Stabilität der URLs |
|---|---|---|---|
| `knauf.com/de-DE/...wand-systeme-im-ueberblick/` | ✅ Produktiv, schnell | ✅ Offizielle Herstellerseite | 🟡 Pfad könnte sich bei Relaunch ändern — URL ohne klare ID |
| `knauf.de/media/modules/cad/cadlayer.php?ss_sg_nr=...` | ✅ CAD-Details pro System | ✅ Technisch präzise | ✅ Parametrisiert über `ss_sg_nr`-Parameter — stabil |
| PDF-Detailblätter `knauf.de/detailblaetter/...` | 🟡 erreichbar, aber URL unklar ohne Suche | ✅ Goldstandard (direkt die AbP-relevanten Planungsdaten) | 🟡 Versionierung in Dateinamen |
| `knauf-firewin.com` (Brandschutzsparte) | ✅ | ✅ | 🟡 Marke wurde teils umbenannt |
| Zweit-Quellen (yumpu, docplayer, studocu) | 🟡 | 🟡 oft veraltet | 🟡 |

**Erkenntnis:** Die offiziellen `knauf.com/de-DE/...`-URLs sind primärzitat-tauglich. Zweit-Quellen (yumpu, docplayer) höchstens zur Plausibilitäts-Gegenprobe.

---

## Klicks/Schritte bis zur Info

Typischer Pfad für die **Klärung einer einzelnen System-Zuordnung** (Schachtwand vs. Vorsatzschale vs. Brandwand):

1. Google/WebSearch mit `"Knauf <Systemname> <vermutete-Kategorie>"` → 1 Anfrage
2. Offizielle Knauf-URL aus Top-3-Hits identifizieren → manuell ~5 s
3. WebFetch auf die URL, Frage stellen → 1 Anfrage
4. Zitat + URL in `meta.verifiziert_am` eintragen → ~1 Min Schreibarbeit

**→ 2-3 Minuten pro Konflikt-Auflösung** wenn Recherche eindeutig ist.

Für die **Detail-Verifikation** (Wanddicke, Rw-Werte, max. Wandhöhe pro Systemvariante) reicht die Übersichtsseite nicht. Dafür braucht es:

1. Knauf-Detailblatt als PDF finden (downloads.knauf.de / Detailblatt-Suche)
2. PDF lesen und mit Modellwissen-Rekonstruktion abgleichen
3. Abweichungen pro Feld dokumentieren

**→ 15-30 Minuten pro System** für belastbare Detail-Verifikation (mehr wenn das PDF viele Varianten zeigt).

---

## Aufwandsschätzung für vollständige Knauf-Verifikation

Aktueller Bestand (aus INVENTORY.md):
- `knauf-systeme-w11-d11.json` — **10 Systeme** (6 Wand + 4 Decken), einzige Datei mit offizieller Quellen-Referenz (noch nicht hash-verifiziert)
- `knauf-systeme-brandschutz-fireboard.json` — **~13 Systeme/Varianten** (W131, W133, W112-Fireboard, K211-K213, D131)
- `knauf-systeme-w61-vorsatzschalen.json` — **4 Systeme** nach W628-Korrektur (W623, W625, W626, W631)
- `knauf-systeme-w62-w63-schachtwaende.json` — **5 Systeme** (intern benannt — echte Knauf-Namen W628A/B, W629, W635 stehen noch aus)

**Summe: ~32 zu verifizierende Systeme.**

| Verifikationsniveau | Aufwand pro System | Gesamt |
|---|---|---|
| **Nur Kategorien-Zuordnung** (Schachtwand/Vorsatz/Brand?) | 2-3 Min | ~90 Min |
| **Nur Systemname korrekt zu offiziellem W62X.de mappen** | 5-10 Min | ~5 h |
| **Detail-Verifikation aller Eigenschaften** (Wandhöhe, Rw, Feuerwiderstand, Plattenvarianten) | 15-30 Min | **~12-16 h** |

---

## Empfehlung: Bulk-Verifikation vs. System-für-System

### System-für-System (reaktiv)
**Wann sinnvoll:** Wenn bei der Nutzung des LV-Preisrechners konkrete Zweifel auftreten (wie beim W628-Konflikt).
**Vorteil:** Niedriger Aufwand, direkter Nutzen.
**Nachteil:** Bei Live-Deployment können blinde Flecken auftauchen die wir nicht kennen.

### Bulk-Verifikation (proaktiv)
**Wann sinnvoll:** Vor der öffentlichen/kommerziellen Freigabe an weitere Tenants (nicht mehr nur Harun's Vater).
**Vorteil:** Eine verifizierte Wissensbasis, die danach bei jedem neuen LV greift.
**Nachteil:** Eintäglicher Sprint (~1 Arbeitstag) für Kategorien-Zuordnung, oder 2-3 Tage für Detail-Verifikation.

### Praktische Empfehlung
1. **Jetzt (kurzfristig):** System-für-System bei Konflikten verifizieren wie hier gemacht. Markiere `meta.verifiziert_am` in jeder Datei pro Teilaspekt. Das reicht für den Pilot-Kunden und deckt Blindflecken reaktiv auf.
2. **Vor Phase 2 (Multi-Tenant-SaaS):** 1-Tages-Sprint für Kategorien-Zuordnung aller 32 Systeme. Das kann mit einem Agent und klarem Recherche-Skript in ~90 Minuten automatisiert werden.
3. **Vor verbindlichen Angebotssummen mit Kunden-Haftung:** Detail-Verifikation aller Eigenschaften. Rechnen: 2-3 Arbeitstage. Eventuell mit einem Trockenbau-Experten (nicht nur KI) verifizieren.

### Kosten-Abschätzung Bulk-Verifikation
- **Kategorien-Zuordnung aller ~32 Systeme:**
  - Manuell: 90 Min Recherche × 60 €/h = **~90 €**
  - Agent-gestützt (WebSearch+WebFetch pro System, ~2 Claude-Calls à ~$0.01): ~$0.64 API-Kosten + 15 Min Nachkontrolle = **~30 €**
- **Detail-Verifikation aller Eigenschaften:**
  - Manuell: 12-16 h × 60 €/h = **~800 €**
  - Agent-gestützt (PDF-Download + Vergleich pro System, deutlich teurer wegen PDF-Parsing): ~$5-10 API-Kosten + 3-4 h Review = **~250 €**

**Faustregel:** Agent-gestützte Bulk-Verifikation ist ~3× günstiger als manuell, verlangt aber qualifizierten Review durch Trockenbau-Experten.

---

## Technik: So dokumentiere ich Verifikationen (Standard für alle Knauf-Dateien)

Im `meta`-Block jeder Knowledge-JSON wird ein Array `verifiziert_am` angelegt:

```json
"verifiziert_am": [
  {
    "datum": "YYYY-MM-DD",
    "scope": "<was genau verifiziert wurde>",
    "quelle": "<URL>",
    "zitat": "<Direktzitat für Prüfbarkeit>",
    "offene_punkte": ["<noch nicht verifizierte Aspekte>"]
  }
]
```

Mehrere Einträge möglich — pro Recherche-Runde ein Eintrag. So bleibt nachvollziehbar:
- Was ist verifiziert?
- Was ist noch rekonstruiert?
- Wann wurde zuletzt geprüft?

Bei Änderungen an Systemen wird der vorhandene Eintrag nicht gelöscht, sondern ein neuer ergänzt — die Historie bleibt lesbar.
