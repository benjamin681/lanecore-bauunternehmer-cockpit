# Skill: Preislisten-Import (Säule 2 — v2)

> **Status:** Geplant für v2. Dieses Skill-Dokument dient als Architektur-Referenz.

---

## Typische Preislisten-Formate

| Lieferant | Format | Herausforderung |
|-----------|--------|----------------|
| Knauf | PDF, Excel | Viele Varianten, Preisgruppen |
| Rigips (Saint-Gobain) | PDF | Sonderschriften, Tabellen-Layout |
| Siniat | Excel | Sauberste Datenstruktur |
| Baustoffhändler (lokal) | PDF, CSV, manuell | Sehr variabel |

---

## Extraktion-Pipeline

```
PDF/Excel eingehend
    ↓
[pdfplumber] Tabellen extrahieren
    ↓
[Claude Sonnet] Tabellen normalisieren:
    → Artikel-Nr, Bezeichnung, Einheit, Preis
    ↓
[Validierung] Preise plausibel? (€/m², €/Stk, €/lm)
    ↓
[DB] Preisdatenbank mit Lieferant + Datum
```

---

## Normalisiertes Preis-Schema

```json
{
  "lieferant": "Knauf",
  "preisliste_datum": "2026-01-01",
  "artikel": [
    {
      "artikel_nr": "GKB.12.5.1200.2000",
      "bezeichnung": "Knauf GKB Gipskartonplatte 12,5mm 1200×2000mm",
      "kategorie": "GK-Platten",
      "einheit": "m²",
      "preis_netto": 4.85,
      "waehrung": "EUR",
      "tags": ["GKB", "12.5mm", "standard"]
    }
  ]
}
```

---

## Matching: Analyse-Ergebnis → Preise

```python
# Aus Analyse-Ergebnis: "W112, 245m²"
# Benötigt: CW-Profile, UW-Profile, GKB, Mineralwolle, Schrauben

MATERIAL_MAPPING = {
    "W112": {
        "GKB_12.5": {"menge_pro_m2": 2.20, "einheit": "m²"},
        "CW_75": {"menge_pro_lm_wand": 1.60, "einheit": "lm"},
        "UW_75": {"menge_pro_lm_wand": 2.00, "einheit": "lm"},
        "MW_40": {"menge_pro_m2": 1.10, "einheit": "m²"},
    },
    "W115": {
        "GKB_12.5": {"menge_pro_m2": 4.40, "einheit": "m²"},
        # ...
    },
}
```

---

## Claude-Prompt für Preislisten-Normalisierung

```python
system = """Du normalisierst Baumaterial-Preislisten für ein Trockenbau-Unternehmen.
Extrahiere alle Artikel mit Artikel-Nr, vollständiger Bezeichnung, Einheit und Nettopreis.
Klassifiziere jeden Artikel: GK-Platten | Profile | Dämmung | Befestigung | Sonstiges.
Antworte im JSON-Format."""
```
