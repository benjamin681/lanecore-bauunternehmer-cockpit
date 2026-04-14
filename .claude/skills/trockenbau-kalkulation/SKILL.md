# Skill: Trockenbau-Kalkulation

## Wandsysteme und ihre Konstruktion

### W112 — Standard-Trennwand (Knauf/Rigips Typ A)
- **Aufbau:** 1× GK (12.5mm) | CW-Profil 75mm | 1× GK (12.5mm)
- **Gesamtdicke:** 100mm
- **Schallschutz:** Rw = 43 dB
- **Anwendung:** Standard-Bürotrennwände, Flure

**Materialbedarf pro m² Wandfläche:**
- GKB 12.5mm: 2.0 m² (beide Seiten) × Verschnitt 1.10 = **2.20 m²**
- CW-Profil 75/06 (Ständer): 1 Stk / 62.5cm = **1.60 Stk/m** Wandlänge × Wandhöhe
- UW-Profil 75/40 (Boden + Decke): 2 × Wandlänge = **2.0 lm/m** Wandlänge
- Mineralwolle 40mm: 1.10 m²
- Spachtelspitze/Bewehrungsband: nach Aufwand
- Schrauben TN 3.5×35: ~25 Stk/m²

### W115 — Schallschutzwand (Rw ≥ 53 dB)
- **Aufbau:** 2× GK (12.5mm) | CW-Profil 75mm | 2× GK (12.5mm)
- **Gesamtdicke:** 125mm
- **Anwendung:** Besprechungsräume, Konferenz, WC-Trennwände

**Materialbedarf pro m² (Änderungen zu W112):**
- GKB 12.5mm: 4.0 m² × Verschnitt 1.10 = **4.40 m²**
- Mineralwolle 60mm (statt 40mm)
- Sonst wie W112

### W118 — Brandschutzwand F90
- **Aufbau:** 2× GKF 15mm | CW-Profil 100mm | 2× GKF 15mm
- **Gesamtdicke:** 160mm
- **Brandschutz:** F90 (90 Minuten)
- **Anwendung:** Treppenhäuser, Flucht- und Rettungswege, Technikräume

**Abweichungen zu W115:**
- GKF statt GKB (Feuerschutz-Gipskarton, erkennbar an Rosa-/Roter Farbe)
- 15mm statt 12.5mm Plattendicke
- CW 100mm Profil (breiterer Ständer)

### W116 — Installationswand (doppelter Ständer)
- **Aufbau:** 1× GK | CW 50mm | 50mm Luft | CW 50mm | 1× GK
- **Gesamtdicke:** 215mm
- **Anwendung:** Sanitärwände, Installationsschächte

---

## Decken-Systeme

### D11x — Abgehängte Deckensysteme

**D112 — Standard Unterdecke**
- Tragprofil CD 60 im Raster 50×50cm oder 62.5×62.5cm
- Abhängung mit Nonius-Abhänger (alle 100cm)
- GKB 12.5mm einseitig

**Materialbedarf D112 pro m²:**
- GKB 12.5mm: 1.10 m² (inkl. Verschnitt)
- CD 60 Profil: 2.40 lm (Raster 62.5cm = 1.6 Stk × 1.5m/Stk)
- UD 28 Wandanschlussprofil: Umfang / Fläche ≈ 0.30 lm/m²
- Nonius-Abhänger: 4 Stk/m²

---

## Profiltypen und Abmessungen (DIN 18183)

| Profil | Verwendung | Standard-Länge | Breiten |
|--------|-----------|----------------|---------|
| CW | Ständer (vertikal) | 4000mm | 50, 75, 100mm |
| UW | Boden-/Deckenanschluss | 3000mm | 50, 75, 100mm |
| CD | Deckenträger | 3000mm | 60mm |
| UD | Decken-Wandanschluss | 3000mm | 28mm |
| UA | Verstärkungsständer | 4000mm | 50–200mm |

---

## Verschnitt-Faktoren

| Position | Faktor |
|----------|--------|
| GK-Platten Wand (einfach) | 1.10 (10% Verschnitt) |
| GK-Platten Decke | 1.15 (15% Verschnitt) |
| GK-Platten viele Ecken/Aussparungen | 1.20 |
| Profile (CW/UW) | 1.05 |
| Dämmung | 1.10 |

---

## Kalkulations-Beispiel

**Aufgabe:** W112, 8.40m lang, 2.80m hoch, 1 Tür 0.875m × 2.10m

```
Wandfläche brutto:  8.40 × 2.80 = 23.52 m²
Türöffnung:         0.875 × 2.10 = 1.84 m²
Wandfläche netto:   23.52 - 1.84 = 21.68 m²

GKB-Platten: 21.68 m² × 2 (beids.) × 1.10 = 47.70 m² → 48 Pl. (1.25×2.00m = 2.5m²)
CW-Profile:  (8.40m / 0.625) × 2.80m + Randständer = 14 Stk × 2.80m → 6 Stangen à 4m = 15 Stk
UW-Profile:  8.40 × 2 = 16.80 lm → 6 Stangen à 3m
MW-Dämmung: 21.68 × 1.10 = 23.85 m²
```

---

## LV-Positionen (VOB-Nummern)

```
035.102 – Trennwand in Ständerbauart (W112, GK einseitig)
035.104 – Trennwand in Ständerbauart (W115, GK beidseitig 2-lagig)
035.106 – Trennwand in Ständerbauart (W118, GKF beidseitig, F90)
036.112 – Unterdecke, abgehängt (D112)
```
