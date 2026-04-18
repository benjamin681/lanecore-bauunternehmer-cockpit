# LV-Preisrechner — Produktspezifikation

**Version:** 1.0
**Stand:** 04/2026
**Status:** In Entwicklung (separates Projekt, nicht im Cockpit)

---

## Kontext & Motivation

Nach Kundengespräch vom 17.04.2026 mit Harun's Vater (Trockenbauer, Ulm):

Der Kunde bekommt regelmäßig **LVs (Leistungsverzeichnisse) als PDF** vom Auftraggeber. Diese enthalten alle Bauleistungen mit Mengen, aber ohne Preise. Der Trockenbauer muss jetzt:
1. Jede Position manuell kalkulieren (Materialrezept ermitteln)
2. Aktuelle Einkaufspreise von Kemmler nachschlagen
3. Lohn und Zuschläge addieren
4. Das Ergebnis mühsam in das PDF eintippen oder ausdrucken & handschriftlich ausfüllen

Das dauert heute **2–4h pro LV**. Der LV-Preisrechner automatisiert das auf **<5 Minuten**.

---

## Kernprodukt

**Input → Verarbeitung → Output**

```
LV als PDF (oder GAEB X83 / Excel)
        ↓
Positionen erkennen (Claude Vision + OCR)
        ↓
Materialrezept zuordnen (pro Systemtyp)
        ↓
Preise aus Händler-Preislisten matchen
        ↓
EP kalkulieren (Material + Lohn + Zuschläge)
        ↓
Ausgefülltes Original-PDF (EP + GP eingetragen)
```

---

## Input-Formate

| Format | Priorität | Beschreibung |
|--------|-----------|--------------|
| PDF | **Hauptfall** | Ausgabe aus ORCA, Nevaris, AVA-Software |
| GAEB X83 | Nice-to-have | Maschinenlesbares LV-Format |
| Excel | Nice-to-have | Manuelle LVs vom Auftraggeber |

---

## Positions-Erkennung

Claude Vision extrahiert pro Position:
- **OZ** (Ordnungszahl, z.B. "610.0010")
- **Menge** (z.B. "1.895,00")
- **Einheit** (m², lfm, Stk, psch)
- **Kurztext** (z.B. "Trennwand W112, GKB, F30, h≤4,00m")
- **Langtext** (vollständige Leistungsbeschreibung)

---

## Materialrezepte

Jeder Systemtyp hat ein Standardrezept (pro m²):

### W112 — Einfache Trennwand (Beispiel)
| Material | Menge | Einheit |
|----------|-------|---------|
| CW-Profil (75mm) | 1,80 | lfm |
| UW-Profil (75mm) | 0,80 | lfm |
| GKB 12,5mm | 2,10 | m² (je Seite, 2 Seiten → ×2) |
| Mineralwolle 60mm | 1,05 | m² |
| Gipsplattenschrauben | ~0,30€ | pauschal |
| Kleinmaterial (Fugenband, Dübel) | ~1,50€ | pauschal |

### Weitere Systeme (müssen noch hinterlegt werden)
- W115 (2-lagige Beplankung, erhöhter Schallschutz)
- W118 (Brandschutzwand, GKF)
- W135 (mit Stahlprofil-Verstärkung)
- Vorsatzschalen (freistehend / wandgebunden)
- Unterdecken / abgehängte Decken
- WC-Trennwände
- Schachtwände

---

## Matching-Logik: Produkt-DNA

**Wichtig:** Matching erfolgt NICHT über Artikelnummern, sondern über die "Produkt-DNA":

```
Produkt-DNA = Hersteller + Kategorie + Produktname + Abmessungen + Variante
```

Beispiel:
- Kemmler Art.-Nr. `3530100012` = "Knauf Gipskartonplatte GKB 12,5mm 2000×1250mm"
- Wölpert hat dieselbe Platte unter anderer Artikelnummer, gleichem Preis ±x%
- Die Produkt-DNA "Knauf / GKB / 12,5mm / 2000×1250" ist überall gleich

**Vorteile:**
- Neue Händler können per Preislisten-Import ergänzt werden
- Preisvergleich zwischen Händlern wird automatisch möglich
- Kein manuelles Mapping der Artikelnummern nötig

---

## EP-Kalkulation

### Formel
```
EP = Material + Lohn + Gemeinkosten
```

### Aufschlüsselung (Beispiel W112, 62,00 €/m²)
| Kostenart | Berechnung | Betrag |
|-----------|-----------|--------|
| CW75 Profil | 1,80 lfm × 2,10 €/lfm | 3,78 € |
| UW75 Profil | 0,80 lfm × 1,80 €/lfm | 1,44 € |
| GKB 12,5mm | 4 × 1,05 m² × 3,00 €/m² | 12,60 € |
| Mineralwolle 60mm | 1,05 m² × 2,50 €/m² | 2,63 € |
| Schrauben | pauschal | 0,30 € |
| Kleinmaterial | pauschal | 1,50 € |
| **Summe Material** | | **22,25 €** |
| Lohn | 0,55 h × 46,00 €/h | 25,30 € |
| BGK 10% | auf Material+Lohn | 4,76 € |
| AGK 12% | auf Material+Lohn | 5,71 € |
| W+G 5% | auf alles | 2,90 € |
| **EP netto** | | **~62,00 €/m²** |

### Konfigurierbare Parameter (vom Trockenbauer einzugeben)
- Kalkulationslohn (€/h, inkl. Lohnnebenkosten)
- BGK-Zuschlag (%)
- AGK-Zuschlag (%)
- Wagnis & Gewinn (%)
- Zeitansätze pro Systemtyp (h/m²)

---

## Output: Ausgefülltes PDF

### Technische Umsetzung (PyMuPDF)
1. EP/GP-Felder werden über Textsuche "EP.........." lokalisiert
2. Punkte werden weiß überdeckt (Whitebox)
3. Preise werden in gleicher Schriftart/Größe eingefügt
4. GP = Menge × EP wird berechnet und eingefügt
5. Summen werden aktualisiert

### Proof of Concept
- Habau GmbH, Verwaltungsgebäude Koblenz, 58 Seiten
- 16/16 Innenwand-Positionen erfolgreich gefüllt
- Details: `docs/proof-of-concept-ergebnisse.md`

---

## Tech-Stack (separates Projekt)

| Komponente | Technologie | Begründung |
|------------|-------------|------------|
| Backend | FastAPI (Python) | Bewährt im Projekt, PDF-Libs |
| PDF-Verarbeitung | PyMuPDF + pdfplumber | Positionserkennung + Einfüllung |
| LLM | Claude Sonnet 4.6 → Opus 4.6 Fallback | Cost-optimiert |
| Frontend v1 | Streamlit | Schnellster Weg zum Test |
| Frontend v2 | Next.js (aus Cockpit) | Spätere Integration |
| Datenbank | SQLite | Kein Overhead für MVP |
| Auth | Kein Auth für MVP | Nur Harun's Vater |

---

## Offene Punkte

- Zeitansätze und Zuschläge müssen vom Kunden kommen (`docs/offene-fragen-harun.md`)
- Decken, Vorsatzschalen, WC-Trennwände: Rezepte noch nicht hinterlegt
- GAEB X83 Parser: Noch nicht implementiert
- Multi-Händler Preisvergleich: Schritt 2 nach Pilot
