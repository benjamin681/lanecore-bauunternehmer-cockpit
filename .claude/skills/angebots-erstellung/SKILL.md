# Skill: Angebotserstellung (Säule 3 — v2)

> **Status:** Geplant für v2. Dieses Skill-Dokument dient als Architektur-Referenz.
> Säule 3 baut auf Säule 1 (Bauplan-Analyse) und Säule 2 (Preisvergleich) auf.

---

## VOB/B Grundlagen für Trockenbauer

### Was ist die VOB?
- **Vergabe- und Vertragsordnung für Bauleistungen** — deutsches Regelwerk
- **VOB/A**: Vergabe (öffentliche Ausschreibungen)
- **VOB/B**: Vertragsbedingungen (wie wird abgerechnet)
- **VOB/C**: Technische Ausführungsbestimmungen (ATV — Allgemeine Technische Vertragsbedingungen)

### Relevante ATV für Trockenbau
- **DIN 18340** — Trockenbauarbeiten
- **DIN 18183** — Metallprofile für Trennwand- und Deckensysteme
- **DIN 4109** — Schallschutz im Hochbau (Anforderungen)

---

## Leistungsverzeichnis (LV) Struktur

```
Gewerk: Trockenbauarbeiten
└── Los: Innenausbau EG
    ├── Position 01: Trennwand W112
    │   ├── Positionsnummer: 035.102
    │   ├── Leistungsbeschreibung: [Text]
    │   ├── Mengenansatz: 245.00
    │   ├── Einheit: m²
    │   ├── Einheitspreis: [€/m²]
    │   └── Gesamtpreis: [€]
    ├── Position 02: Trennwand W115 ...
    └── Position 03: Abgehängte Decke ...
```

---

## Standard-Positionstexte (Trockenbau)

### Position W112 (1× GK, einfache Ständerwand)
```
035.102 — Trennwand in Ständerbauart

Nichttragende Trennwand in Ständerbauart mit
Metallunterkonstruktion, Ständerprofil CW 75,
beidseitig 1-lagig beplankt mit GK-Platte 12,5mm.
Mineralwolledämmung 40mm in der Hohlkonstruktion.
Fugen und Stöße gespachtelt und schleiffertig.

Wandhöhe bis 3,00m
Einheit: m² (Nettowandfläche ohne Öffnungen)

EP: _____,__ €/m²
```

### Position W115 (2× GK, erhöhter Schallschutz)
```
035.104 — Trennwand mit erhöhtem Schallschutz

Nichttragende Trennwand in Ständerbauart mit
Metallunterkonstruktion, Ständerprofil CW 75,
beidseitig 2-lagig beplankt mit GK-Platte 12,5mm.
Mineralwolledämmung 60mm. Rw ≥ 53 dB.
Fugen und Stöße gespachtelt und schleiffertig.

Wandhöhe bis 3,00m
Einheit: m²

EP: _____,__ €/m²
```

---

## Einheitspreise (Orientierung — Stand 2025)

> Achtung: Diese Preise sind Orientierungswerte. Immer mit aktuellen Lieferantenpreisen berechnen!

| Position | EP-Netto (ca.) | Materialanteil | Lohnanteil |
|---------|---------------|---------------|-----------|
| W112 | 45–65 €/m² | 60% | 40% |
| W115 | 65–85 €/m² | 65% | 35% |
| W118 (F90) | 85–120 €/m² | 60% | 40% |
| Unterdecke D112 | 55–75 €/m² | 55% | 45% |
| Anschlussarbeiten | 15–25 €/lm | 50% | 50% |

---

## Kalkulations-Schema

```
Nettomaterialkosten (aus Preisvergleich)
+ Verschnitt (10–20%)
+ Materialgemeinkosten (5%)
= Materialkosten gesamt

Lohnstunden × Stundensatz (inkl. Lohnnebenkosten)
= Lohnkosten

Materialkosten + Lohnkosten
= Herstellkosten

+ Gerätekosten (5–8% der Herstellkosten)
+ Nachunternehmerleistungen
= Selbstkosten

+ Allgemeine Geschäftskosten / AGK (8–12%)
+ Wagnis und Gewinn (3–8%)
= Angebotspreis netto

+ USt 19%
= Angebotspreis brutto
```

---

## Lohnstunden-Richtwerte Trockenbau

| Leistung | Std/m² | Anmerkung |
|---------|--------|-----------|
| W112 aufbauen | 0.35 | Erfahrener Trockenbauer |
| W115 aufbauen | 0.50 | Doppelbeplankung |
| W118 aufbauen | 0.65 | GKF + Brandschutzdetails |
| Unterdecke | 0.45 | Inkl. Unterkonstruktion |
| Verspachtelung | 0.20 | Pro m² beidseitig |

---

## Claude-Prompt für LV-Erstellung (Konzept)

```python
# Aus Analyse-Ergebnis automatisch LV-Positionen generieren
system = """Du bist ein Kalkulator für Trockenbauarbeiten.
Erstelle aus den Massen-Angaben ein VOB-konformes Leistungsverzeichnis.
Format: JSON mit Positionen nach DIN 276."""

user = f"""
Erstelle LV-Positionen für folgende Massen:
{json.dumps(analyse_ergebnis)}

Verwende Standard-ATV DIN 18340.
Einheitspreise aus Preisliste: {json.dumps(preise)}
"""
```
