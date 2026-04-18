# ADR-007: Kunden-eigene Preisliste als Kern-Feature (Multi-Tenant Pricing)

**Datum:** 18.04.2026
**Status:** Entschieden
**Entscheider:** Ben

---

## Kontext

Beim Aufbau der Wissensdatenbank wurden umfangreich Händler-Preislisten (Kemmler A-Liste, A+ Liste 04/2026) extrahiert. Frage: Soll die Knowledge Base mit echten Händlerdaten (Kemmler, später Wölpert, Raab Karcher) ausgeliefert werden?

Antwort des Kunden (Ben, 18.04.2026):

> "die kemmlerlisten sind nur für unsere testzwecke unsere kunden müssen ihre individuellen listen selbst hochladen können"
>
> "kein handwerker hat den gleichen preis wie ein anderer"

Das ist die richtige Produkt-Beobachtung. Jeder Trockenbauer verhandelt eigene Konditionen mit seinem Händler. Eine Kemmler-Liste "04/2026 Liste A" ist die öffentliche Listenpreis-Variante — die echten Einkaufspreise eines Betriebs liegen typischerweise 10–40 % darunter (je nach Abnahmemenge, Verhandlungsposition, Rahmenverträgen).

Ein LV-Preisrechner, der mit einer generischen Liste kalkuliert, liefert **falsche EP** und ist damit wertlos.

---

## Entscheidung

### 1. Kemmler-Daten sind Test-Fixtures — nicht Produkt-Inhalt
- `knowledge/kemmler-preise-042026.json` bleibt minimal, nur für automatisierte Tests und Entwickler-Demos.
- **Nicht** exhaustiv weiter-extrahieren. Kein Produktkatalog-Ausbau für Kemmler.
- Dokument-Header muss klar markieren: "TESTDATEN — nicht produktiv einsetzbar."

### 2. Preisliste-Upload ist das Kern-Feature (Säule 2)
Jeder Kunde muss seine eigene Preisliste hochladen können. Das System parst sie in unser Produkt-DNA-Format und verwendet **nur die Kundendaten** für Kalkulationen.

### 3. Multi-Tenant-Trennung ab Tag 1
Auch im MVP (SQLite, ein Nutzer) muss die Datenbank-Struktur Preislisten pro `tenant_id` / `user_id` trennen. Keine globale Preisliste, auf die mehrere Kunden zugreifen.

---

## Feature-Spezifikation: Preisliste-Upload

### Eingabe-Formate (Priorität)
1. **PDF** (häufigster Fall — Händler-PDF-Preislisten, z.B. Kemmler 04/2026, Wölpert Katalog, Raab Karcher)
2. **Excel/CSV** (wenn Kunde bereits eine strukturierte Datei hat)
3. **Scan/Foto** (Fallback: fotografierte Papierlisten → Claude Vision)

### Parsing-Pipeline
```
Upload (PDF/XLSX/Bild)
  ↓
Vorverarbeitung (pdfplumber für Text / Claude Vision bei Scans)
  ↓
Struktur-Erkennung (Claude Sonnet)
  - Welche Kategorien? (Gipskarton, Dämmung, Profile, Schrauben, ...)
  - Welche Spalten? (Art-Nr, Bezeichnung, Menge, Einheit, Preis, Einheit-Preis)
  - Welche Preis-Klassen? (Liste A, Liste B, Sonderkondition)
  ↓
Produkt-DNA-Extraktion (Claude Sonnet mit Kalibrierungs-Prompt)
  - Hersteller | Kategorie | Produktname | Abmessungen | Variante → DNA-String
  - Fallback Opus bei niedriger Konfidenz
  ↓
Normalisierung
  - Einheiten-Konvertierung (€/Paket → €/m², €/Stk → €/m², ...)
  - Duplikat-Erkennung (gleiche DNA, verschiedene Art-Nr)
  ↓
Review-UI
  - Kunde sieht geparste Einträge
  - Markiert unsichere Zeilen (niedrige Konfidenz)
  - Kann manuell korrigieren / ergänzen
  ↓
Persistenz
  - Pro Kunde gespeichert (tenant-isoliert)
  - Versioniert (Stand 04/2026, 10/2026, ...)
  - Aktive Liste je Kunde markiert
```

### Matching mit LV-Positionen
- LV-Position wird in Produkt-DNA übersetzt (Trockenbau-Skill)
- Gegen Kunden-eigene Preisliste gematcht
- Bei mehreren Treffern (z.B. Kunde hat Liste A + Liste B): günstigsten Preis wählen oder Kunde entscheidet
- Bei keinem Treffer: Fallback-Warnung, manuelle Preis-Eingabe

---

## Datenmodell (vereinfacht, SQLite MVP)

```sql
-- Kunde / Mandant
CREATE TABLE tenants (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Preisliste eines Kunden (z.B. "Kemmler Neu-Ulm 04/2026", "Wölpert 03/2026")
CREATE TABLE price_lists (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  haendler TEXT NOT NULL,              -- "Kemmler", "Wölpert", "Eigene Kalkulation"
  niederlassung TEXT,                  -- "Neu-Ulm", "Stuttgart"
  stand_monat TEXT NOT NULL,           -- "04/2026"
  original_dateiname TEXT,
  original_pdf_sha256 TEXT,            -- Audit: welche Datei wurde geparst
  status TEXT NOT NULL,                -- "parsing", "review", "aktiv", "archiviert"
  aktiv BOOLEAN DEFAULT FALSE,         -- max. 1 pro haendler aktiv
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Einzelner Preis-Eintrag mit Produkt-DNA
CREATE TABLE price_entries (
  id TEXT PRIMARY KEY,
  price_list_id TEXT NOT NULL REFERENCES price_lists(id),
  art_nr TEXT,                         -- optional, vom Händler
  dna TEXT NOT NULL,                   -- "Knauf|GKB|Standard|12.5mm|2000x1250"
  hersteller TEXT NOT NULL,
  kategorie TEXT NOT NULL,
  produktname TEXT NOT NULL,
  abmessungen TEXT,
  variante TEXT,
  preis REAL NOT NULL,                 -- Netto-EK
  einheit TEXT NOT NULL,               -- "€/m²", "€/Stk", "€/Paket (500 Stk)"
  preis_pro_basis_einheit REAL,        -- normalisiert auf €/m², €/Stk, €/lfm
  basis_einheit TEXT,
  konfidenz REAL,                      -- 0.0-1.0, Claude-Extraktion
  manuell_korrigiert BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_price_entries_dna ON price_entries(dna);
CREATE INDEX idx_price_entries_list ON price_entries(price_list_id);
```

---

## Bestehende Kemmler-Daten — was damit passiert

- `knowledge/kemmler-preise-042026.json` wird als **Test-Fixture** behalten.
- Wird in Tests unter `tests/fixtures/` gespiegelt / verlinkt.
- Dient als Beispiel-Input für:
  - Integration-Tests des Parsers (PDF rein → erwartete DNA raus)
  - End-to-End-Tests des LV-Preisrechners (LV + Kemmler-Liste → erwartete EP)
  - Entwickler-Demo ohne Kunden-Daten
- Bleibt minimal — kein Deep-Dive mehr in A+ Liste alle Kategorien.

## Knauf/Siniat System-Wissen — bleibt universal

Im Gegensatz zu Preisen sind **Hersteller-Systeme (W111, W112, W115, W118, W625, D112, Fireboard, ...) universal** — jeder Trockenbauer nutzt die gleichen Knauf-Datenblätter. Diese Wissensdateien (`knowledge/knauf-systeme-*.json`) bleiben globaler Produkt-Inhalt:

- Systemaufbau (Platten, Profile, Dämmung pro System)
- Feuerwiderstand / Schalldämmwerte
- Materialrezepte pro m² Wand/Decke
- LV-Matching-Muster (Keyword → System)

Der Kunde muss diese Wissensbasis **nicht** hochladen.

---

## Konsequenzen

### Was wir bauen
1. **PDF-Parser-Service** (`app/services/price_list_parser.py`)
   - Input: PDF-Bytes + tenant_id + metadata
   - Output: `price_list_id` mit N `price_entries`
2. **Review-UI** (Streamlit MVP → Next.js v2)
   - Liste der geparsten Einträge
   - Konfidenz-Badges
   - Inline-Edit für Korrekturen
3. **DNA-Matcher** (`app/services/dna_matcher.py`)
   - LV-Position → DNA → Suche in aktiver Preisliste
4. **Upload-Endpoint** `/api/v1/price-lists/upload` (multipart)

### Was wir nicht bauen
- Zentrale Händler-Preislisten-Datenbank ("community curated")
- Preisliste-Sharing zwischen Kunden
- Crawler für Händler-Websites
- Keine automatischen Preis-Updates (Kunde muss selbst hochladen)

### Offene Fragen an Harun
Zusätzlich zur Liste in `docs/offene-fragen-harun.md`:
- In welchem Format kommen Preislisten typischerweise (PDF? Excel? Papier)?
- Wie viele verschiedene Händler nutzt sein Vater gleichzeitig?
- Wie oft wechseln die Preise (quartalsweise? monatlich? auf Anfrage)?
- Hat er Rahmenverträge/Sonderkonditionen, die nicht in der Standardliste stehen?

---

## Implementierungs-Reihenfolge

1. **Phase 1 (MVP für Pilot):**
   - Minimal-Upload: Kunde lädt PDF hoch, Claude Vision extrahiert Einträge, Review-UI, manuelle Korrektur
   - Nur 1 aktive Liste pro Kunde

2. **Phase 2:**
   - Mehrere parallele Listen (z.B. Kemmler + Wölpert gleichzeitig)
   - Günstigster-Händler-Vergleich pro Position

3. **Phase 3:**
   - Versionierung mit Diff-Ansicht ("was hat sich seit 01/2026 geändert?")
   - Preisverlauf / Trends
