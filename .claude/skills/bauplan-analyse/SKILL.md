# Skill: Bauplan-Analyse

## Zweck
Systematische Interpretation von Bauplänen (PDFs) zur Massenermittlung für den Trockenbau.

---

## Grundlagen: Was ist ein Bauplan?

### Plantypen
| Typ | Beschreibung | Relevant für Trockenbau |
|-----|-------------|------------------------|
| **Grundriss** | 2D-Draufsicht, Schnitt auf ~1m Höhe | *** Hauptdokument |
| **Schnitt** | Vertikaler Querschnitt | ** für Deckenhöhen |
| **Ansicht** | Außenansicht | * selten relevant |
| **Detailplan** | Konstruktionsdetails | ** für Wandaufbau |
| **Schichtenpläne** | Schallschutz, Brand | ** für Wandtyp |

### Maßstäbe (Standard)
- **1:100** — Standard-Grundriss, 1cm im Plan = 1m in der Realität
- **1:50** — Detaillierter, z.B. Sanitär, Küche
- **1:20** — Konstruktionsdetails
- **1:500** — Lageplan (nicht relevant für Massen)

---

## Schritt-für-Schritt Analyse

### 1. Schriftfeld lesen (rechts unten)
Enthält: Maßstab, Planbezeichnung, Geschoss, Revision, Datum

### 2. Legende interpretieren
- Linienarten: Welche Linie = welcher Wandtyp?
- Schraffuren: Beton, Mauerwerk, Trockenbau
- Abkürzungen: W112, W115, SW, TW, BW...

### 3. Maßketten ablesen
```
Maßkette lesen: |--1.25--|--2.40--|--1.85--|
                |--------5.50---------|
Kreuzcheck: 1.25 + 2.40 + 1.85 = 5.50 ✓
```
Fehlt der Kreuzcheck → Warnung ausgeben.

### 4. Räume identifizieren
- Raumbezeichnungen aus Raumstempel (z.B. "B 1.01 Büro")
- Raumfläche oft direkt eingetragen (z.B. "24.50 m²")
- Sonst: Länge × Breite aus Maßketten

### 5. Wandlängen berechnen
- Jede Trennwand separat erfassen
- Öffnungen (Türen, Fenster) subtrahieren → Nettolänge
- Wandtyp aus Legende

### 6. Deckenhöhen
- Aus Schnitten oder Raumstempeln (OKF = Oberkante Fertigfußboden, OKD = Oberkante Decke)
- Typische Werte: Büro 2.75–3.00m, Wohnbau 2.50m

---

## Häufige Trockenbau-Planzeichen

| Zeichen | Bedeutung |
|---------|-----------|
| Doppellinie + Schraffur | Gipskarton-Ständerwand |
| Strich-Punkt-Linie | Systemmaß (Achsmaß) |
| △ mit Nummer | Schnittmarkierung |
| Pfeil + "OKF +0.00" | Höhenangabe |
| "lw" oder "LW" | Lichte Weite (Öffnungsmaß) |
| "AX" | Achsmaß |

---

## Typische Fehlerquellen und Umgang

### Unleserliche Maßzahlen
→ Ableiten aus Kontext: Normtür = 0.875m, 1.0m, 1.25m lichte Weite

### Widersprüchliche Maße
→ Teilmaße vs. Gesamtmaß: Teilmaße bevorzugen (genauer eingemessen)

### Fehlender Maßstab
→ Ableiten: Türbreite in Pixel messen, auf 0.875m / 1.0m normieren → Skalierungsfaktor

### Handschriftliche Korrekturen
→ Immer mit Warnung vermerken, da ggf. neuere Revision

### Mehrere Revisionen
→ Neueste Revision verwenden, ältere mit "überholt" markieren

---

## Qualitätsprüfung (Plausibilität)

```
Flächen-Check:
- Summe aller Räume ≈ Bruttogeschossfläche × 0.85 (15% Wandanteil)
- Büro: 8–20 m² pro Arbeitsplatz
- Flur: 15–25% der Nutzfläche

Wandlängen-Check:
- Perimeter (Außenwände) > Innenwände bei Standardgebäude
- Wandlänge pro m² Grundfläche: typisch 0.3–0.6 m/m²

Höhen-Check:
- Wohnbau: 2.40–2.60m
- Büro: 2.70–3.20m
- Gewerbe: 3.00–5.00m
```
