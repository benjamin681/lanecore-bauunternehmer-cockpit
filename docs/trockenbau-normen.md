# Trockenbau-Normen & Standards -- Normative Wissensbasis

> Stand: 16. April 2026
> Quellen: DIN-Normen, VOB/C, Herstellerangaben (Knauf, Rigips, Siniat)
> Zweck: Normative Basis fuer die automatische Massenermittlung im Bauunternehmer-Cockpit

---

## 1. DIN 18181 -- Gipsplatten im Hochbau: Verarbeitung (Ausgabe 2019-04)

Zentrale Verarbeitungsnorm fuer alle Gipsplattenarbeiten.

### 1.1 Achsabstaende (Staenderabstand)

| Plattenbreite | Montagerichtung | Achsabstand |
|---------------|-----------------|-------------|
| 1250 mm       | laengs          | **625 mm**  |
| 900 mm        | laengs          | **450 mm**  |
| 600 mm        | laengs          | **300 mm**  |
| 2600 mm       | quer            | **520 mm**  |
| 2000 mm       | quer            | **500 mm**  |
| 1250 mm       | quer            | **625 mm**  |

**Praxisregel 625 mm vs. 417 mm:**

- **625 mm Achsabstand (Standard):** Bei Laengsbeplankung mit 1250 mm breiten Platten. Jede Plattenkante sitzt auf einem Profil. Geeignet fuer einfache Beplankung ohne besondere Lastanforderungen.
- **417 mm Achsabstand (verstaerkt):** Erforderlich bei erhoehter Belastbarkeit -- erhaelt man Konsollasten bis 0,7 kN/m (Haengeschraenke) und Sanitaerinstallationen bis 1,5 kN/m OHNE zusaetzliches UA-Profil. Auch bei Querbeplankung 1250 mm Platten.

**Fuer Kalkulation:** Standard = 625 mm. Flag setzen wenn Nutzer Kueche/Bad angibt -> 417 mm vorschlagen.

### 1.2 Schraubenabstaende

| Bauteil | Max. Schraubenabstand |
|---------|-----------------------|
| **Wand** | **max. 250 mm** |
| **Decke** | **max. 170 mm** |

Doppelbeplankung -- Erste Lage:
- Wandbeplankung 1. Lage: max. **750 mm** (Heftbefestigung)
- Deckenbeplankung 1. Lage: max. **750 mm** (Heftbefestigung)

Doppelbeplankung -- Zweite Lage:
- Wand 2. Lage: max. **250 mm**
- Decke 2. Lage: max. **170 mm**

**Schraubenlaenge:**
- Einfache Beplankung (1x 12,5 mm): Schraube **25 mm** (TN 3,5x25)
- Doppelte Beplankung 2. Lage (2x 12,5 mm): Schraube **35 mm** (TN 3,5x35)
- Doppelte Beplankung 2. Lage (2x 18 mm): Schraube **45 mm** (TN 3,5x45)

**Eindringtiefe:** Mind. 10 mm ins Profil (nach DIN 18181)

### 1.3 Fugenversatz

- **Mindest-Fugenversatz: 400 mm** (Versatz der Quernaehte benachbarter Platten)
- Kreuzfugen sind NICHT zulaessig (Ausnahme: bestimmte Plattentypen laut Hersteller)
- Platten immer im Verband verlegen
- Bei Doppelbeplankung: Fugen der 2. Lage um mind. 400 mm zur 1. Lage versetzen

### 1.4 Stossfugenbreite

- Ideal: 1-3 mm
- Maximal: 5 mm (mit geeigneter Spachtelmasse)

---

## 2. DIN 4103-1 -- Nichttragende innere Trennwaende (Ausgabe 2015-06)

### 2.1 Einbaubereiche

| Einbaubereich | Beschreibung | Beispiele |
|---------------|-------------|-----------|
| **Bereich 1** | Geringe Personenbelegung | Wohnungen, Hotels, Bueros, Krankenzimmer |
| **Bereich 2** | Hohe Personenbelegung | Versammlungsraeume, Schulen, Hoersaele, Einzelhandel |

### 2.2 Grenzabmessungen

| Parameter | Anforderung |
|-----------|-------------|
| **Mindestdicke** | 50 mm |
| **Maximale Dicke (nichttragende Wand)** | < 115 mm |
| **Maximale Wandhoehe (ohne Untergliederung)** | bis 4,50 m (abhaengig von Wanddicke und Profil) |
| **Wandhoehe > 4,50 m** | Horizontale Untergliederung erforderlich (z.B. Riegel aus Beton-U-Schalen) |

### 2.3 Belastungsanforderungen

Trennwaende muessen statische (vorwiegend dauerhafte) und stossartige Beanspruchungen aufnehmen, wie sie unter Gebrauchslasten auftreten koennen.

**Fuer Kalkulation:** Wandhoehe pruefen. Ab > 4,00 m Sonderprofile (UA) oder Verstaerkungen einplanen.

---

## 3. DIN 18340 -- VOB/C Trockenbauarbeiten (Ausgabe 2023-09)

Zentrale Norm fuer Abrechnung, Aufmass und Vergabe von Trockenbauarbeiten.

### 3.1 Aufmassregeln -- Oeffnungsabzuege

| Abrechnungsart | Oeffnungsgroesse | Regelung |
|----------------|------------------|----------|
| Flaechenmass (m2) | **<= 2,50 m2** Einzelgroesse | Wird **uebermessen** (KEIN Abzug) |
| Flaechenmass (m2) | **> 2,50 m2** Einzelgroesse | Wird **abgezogen** |
| Bodenbekleidung (m2) | **<= 0,50 m2** Einzelgroesse | Wird **uebermessen** |
| Bodenbekleidung (m2) | **> 0,50 m2** Einzelgroesse | Wird **abgezogen** |

**Wichtig fuer Kalkulation:**
- Standardtueren (0,885 x 2,135 m = ~1,89 m2) -> KEIN Abzug (unter 2,50 m2)
- Doppelfluegelige Tueren oder grosse Fenster (> 2,50 m2) -> Abzug
- Fuer Oeffnungsgroesse gelten die **kleinsten Masse** der Oeffnung
- Raumhoher Querschnitt zaehlt ebenfalls als Oeffnung

### 3.2 Geltungsbereich

DIN 18340 gilt fuer:
- Decken- und Wandbekleidungen
- Innere Ausbauten in Trockenbauweise
- Leichte Trennwaende und Systemwaende
- Brandschutzbekleidungen
- Installationsfuehrungen (Vorsatzschalen)
- Einbau von Zargen, Tueren und sonstigen Einbauteilen

---

## 4. DIN 4109 -- Schallschutz im Hochbau (Ausgabe 2018)

### 4.1 Mindest-Schalldaemmwerte R'w

| Bauteil / Nutzung | R'w Mindestanforderung | Erhoehter Schallschutz (DIN 4109-5) |
|--------------------|------------------------|--------------------------------------|
| **Wohnungstrennwand** | **>= 53 dB** | >= 56 dB |
| **Reihenhaus-Trennwand** | **>= 62 dB** | >= 67 dB |
| **Wohnungstrenndecke (Luft)** | **>= 54 dB** | >= 57 dB |
| **Treppenhaus-Wand (Wohnung)** | **>= 52 dB** | >= 55 dB |
| **Buero-Trennwand (normal)** | >= 37 dB | >= 42 dB |
| **Buero-Besprechungsraum** | >= 45 dB | >= 52 dB |
| **Flurwand (Hotel)** | >= 47 dB | >= 52 dB |
| **Krankenhaus (Patientenzimmer)** | >= 47 dB | >= 52 dB |

### 4.2 Zuordnung zu Trockenbau-Systemen (Richtwerte)

| Knauf-System | Aufbau | ca. Rw (Labor) | Typische Anwendung |
|-------------|--------|----------------|-------------------|
| W111 | 1x CW, 1-fach beplankt | ~42 dB | Raumteiler, Buero intern |
| W112 | 1x CW, 2-fach beplankt | ~50-54 dB | Buero, Flure |
| W115 | 1x CW, 2-fach beplankt + Daemmung | ~56-60 dB | Wohnungstrennwand |
| W116 | 2x CW, versetzt, beplankt | ~62-67 dB | Reihenhaus, Hotel |

**Fuer Kalkulation:** System-Typ bestimmt Plattenlagen, Daemmung, Profilebedarf.

---

## 5. DIN EN 520 -- Gipsplatten: Klassifizierung und Typen

### 5.1 Plattentypen

| Typ-Kuerzel | Bezeichnung | Eigenschaft |
|-------------|-------------|-------------|
| **A** | Standard-Gipsplatte | Keine besonderen Anforderungen |
| **D** | Dichte-Gipsplatte | Rohdichte >= 800 kg/m3 |
| **E** | Platte mit reduzierter Wasseraufnahme | Fuer Feuchtraeume (Oberflaechenbehandlung) |
| **F** | Feuerschutz-Gipsplatte | Verbesserter Gefuegezusammenhalt bei Brandeinwirkung |
| **H1** | Reduzierte Wasseraufnahme Stufe 1 | Wasseraufnahme <= 5% |
| **H2** | Reduzierte Wasseraufnahme Stufe 2 | Wasseraufnahme <= 10% |
| **H3** | Reduzierte Wasseraufnahme Stufe 3 | Wasseraufnahme <= 25% |
| **I** | Oberflaechenhaerte | Erhoehte Oberflaechenhaerte |
| **P** | Putztraeger | Fuer Nassputz geeignet |
| **R** | Erhoehte Biegezugfestigkeit | Fuer erhoehte mechanische Belastung |

### 5.2 Kombinations-Bezeichnungen (Praxis)

| Handelsname | DIN EN 520 Typ | Alte DIN 18180 | Verwendung |
|-------------|---------------|----------------|-----------|
| GKB (Standardplatte) | Typ A | GKB | Standardwand, Decke |
| GKBI (impr.) | Typ H2 | GKBI | Feuchtraum (Bad, Kueche) |
| GKF (Feuerschutz) | Typ DF oder F | GKF | Brandschutzwand F30/F60 |
| GKFI (Feuerschutz impr.) | Typ DFH2 | GKFI | Brandschutz + Feuchtraum |

### 5.3 Standardmasse

| Plattendicke | Plattenbreite | Plattenlaenge (typisch) |
|-------------|---------------|------------------------|
| 9,5 mm | 1250 mm | 2000 mm |
| 12,5 mm | 1250 mm | 2000 / 2500 / 2600 / 2750 / 3000 mm |
| 15,0 mm | 1250 mm | 2500 / 2600 mm |
| 18,0 mm | 1250 mm | 2500 / 2600 mm |
| 20,0 mm | 600 mm | 2000 / 2500 mm (Trockenestrich) |
| 25,0 mm | 600 mm | 2000 mm (Trockenestrich) |

---

## 6. DIN EN 14195 -- Metallprofile fuer Trockenbau

### 6.1 Profiltypen und Masse

**Wandprofile:**

| Profil | Beschreibung | Steg (mm) | Flansch (mm) | Blechdicke (mm) |
|--------|-------------|-----------|-------------|-----------------|
| **UW 50** | U-Wandprofil (Anschlussprofil) | 50 | 40 | 0,6 |
| **UW 75** | U-Wandprofil | 75 | 40 | 0,6 |
| **UW 100** | U-Wandprofil | 100 | 40 | 0,6 |
| **CW 50** | C-Wandprofil (Staender) | 48,8 | 50 | 0,6 |
| **CW 75** | C-Wandprofil | 73,8 | 50 | 0,6 |
| **CW 100** | C-Wandprofil | 98,8 | 50 | 0,6 |
| **CW 150** | C-Wandprofil | 148,8 | 50 | 0,6 |
| **UA 50** | Aussteifungsprofil | 50 | 40 | 2,0 |
| **UA 75** | Aussteifungsprofil | 75 | 40 | 2,0 |
| **UA 100** | Aussteifungsprofil | 100 | 40 | 2,0 |

**Deckenprofile:**

| Profil | Beschreibung | Steg (mm) | Flansch (mm) | Blechdicke (mm) |
|--------|-------------|-----------|-------------|-----------------|
| **UD 28** | U-Deckenprofil (Randprofil) | 28 | 27 | 0,6 |
| **CD 60** | C-Deckenprofil (Tragprofil) | 60 | 27 | 0,6 |

**Standardlaenge:** 2600 mm, 3000 mm, 4000 mm (profilabhaengig)

### 6.2 Profil-Zuordnung zu Wandsystemen

| Wandsystem | UW-Profil | CW-Profil | Anwendung |
|-----------|-----------|-----------|-----------|
| Standard (75 mm) | UW 75 | CW 75 | Raumtrennwand ohne besondere Anforderung |
| Schallschutz (100 mm) | UW 100 | CW 100 | Erhoehter Schallschutz, Daemmung 80-100 mm |
| Installationswand (150 mm) | UW 150 | CW 150 | Sanitaerinstallation, Vorwandinstallation |

---

## 7. Materialverbrauch -- Richtwerte fuer Kalkulation

### 7.1 Schraubenverbrauch pro m2

| Beplankung | Schrauben pro m2 (Wand) | Schrauben pro m2 (Decke) | Schraubenlaenge |
|-----------|------------------------|-------------------------|-----------------|
| **Einfach (1x 12,5 mm)** | **~15 Stk** | **~24 Stk** | TN 3,5 x 25 |
| **Doppelt -- 1. Lage** | **~7 Stk** (Heftung) | **~7 Stk** (Heftung) | TN 3,5 x 25 |
| **Doppelt -- 2. Lage** | **~15 Stk** | **~24 Stk** | TN 3,5 x 35 |
| **Doppelt Gesamt** | **~22 Stk** | **~31 Stk** | gemischt |

Herleitung: Wand bei e=625mm, Schraubenabstand 250mm: ca. 12-15 Stk/m2. Decke bei e=500mm, Schraubenabstand 170mm: ca. 20-24 Stk/m2.

### 7.2 Profilebedarf pro m2 Wandflaeche

| Position | Richtwert pro m2 | Bemerkung |
|---------|-------------------|-----------|
| **CW-Profil** | **~1,8 lfm/m2** | Bei 625 mm Achsabstand (= 1,6 Staender/m Wandlaenge x Raumhoehe) |
| **CW-Profil (417 mm)** | **~2,6 lfm/m2** | Bei 417 mm Achsabstand |
| **UW-Profil** | **~0,8 lfm/m2** | Boden + Decke (= 2x Wandlaenge / Wandflaeche) |
| **Dichtungsband (UW)** | **~0,8 lfm/m2** | Unter UW-Profilen auf Boden und Decke |

### 7.3 Plattenbedarf pro m2

| Beplankung | Platten pro m2 (brutto) | Verschnitt-Zuschlag |
|-----------|------------------------|-------------------|
| **Einseitig einfach** | 1,0 m2/m2 | + 10-15% |
| **Beidseitig einfach** | 2,0 m2/m2 | + 10-15% |
| **Beidseitig doppelt** | 4,0 m2/m2 | + 10-15% |

### 7.4 Verschnitt-Zuschlaege

| Raumgeometrie | Verschnitt |
|--------------|-----------|
| **Einfache, rechteckige Raeume** | **5-10%** |
| **Raeume mit Nischen und Winkeln** | **10-15%** |
| **Dachschraegen** | **15-20%** |
| **Sehr kleine Flaechen** | **bis 25%** |

**Standard fuer Kalkulation: 10% (wenn keine weitere Information)**

### 7.5 Spachtelmasse / Fugenfueller

| Material | Verbrauch pro m2 Plattenflaeche | Bemerkung |
|---------|--------------------------------|-----------|
| **Fugenspachtel (z.B. Uniflott)** | **~0,3 kg/m2** pro Arbeitsgang | 2-3 Arbeitsgaenge ueblich |
| **Fugenspachtel Gesamt** | **~0,6-1,0 kg/m2** | Inkl. Schraubenkoepfe |
| **Fugenband (Bewehrungsstreifen)** | **~1,2-1,5 lfm/m2** | An allen Quernaehten |
| **Flaechen-Finish (Q3/Q4)** | **~0,5-0,8 kg/m2** zusaetzlich | Nur bei Q3/Q4-Qualitaet |

### 7.6 Daemmung pro m2

| Position | Richtwert |
|---------|-----------|
| **Mineralwolle** | **1,0 m2/m2** Wandflaeche | + 5% Verschnitt |
| **Dicke nach Profil** | CW 50 = 40 mm / CW 75 = 60 mm / CW 100 = 80-100 mm |

### 7.7 Deckenabhaenger pro m2

| Abhaengertyp | Richtwert pro m2 | Raster |
|-------------|-------------------|--------|
| **Direktabhaenger** | **~1,5-2,0 Stk/m2** | CD 60-Achsabstand 500 mm, Abhaengerabstand 800-1000 mm |
| **Nonius-Abhaenger** | **~1,5-2,0 Stk/m2** | Flexibler in der Hoehe (40-200 mm) |

Regel: Max. 600 mm Abstand zur Wand fuer den ersten Abhaenger.

---

## 8. VOB-konforme Abrechnung -- Zusammenfassung

### 8.1 Abrechnungs-Algorithmus fuer Kalkulation

```
FUER jede Wand:
  brutto_flaeche = laenge * hoehe

  FUER jede Oeffnung in Wand:
    oeffnungs_flaeche = breite * hoehe  (kleinste Masse)

    WENN oeffnungs_flaeche > 2.50:  # m2
      abzug += oeffnungs_flaeche
    SONST:
      abzug += 0  # Oeffnung wird uebermessen

  netto_flaeche_VOB = brutto_flaeche - abzug

  # Material berechnen (hier wird NICHT nach VOB abgezogen,
  # sondern nach tatsaechlichem Bedarf!)
  material_flaeche = brutto_flaeche - tatsaechliche_oeffnungen + verschnitt
```

**WICHTIG:** VOB-Aufmass (fuer Abrechnung) != Material-Aufmass (fuer Einkauf).
- VOB: Standardtueren (< 2,50 m2) werden uebermessen -> mehr Abrechnungsflaeche
- Material: Tuer ist Loch -> weniger Plattenverbrauch (aber Verschnitt an Tueroeffnung)
- Kalkulation muss BEIDES ausweisen: VOB-Flaeche UND Materialflaeche

---

## 9. Qualitaetsstufen Oberflaeche (Q1 - Q4)

| Stufe | Beschreibung | Spachtelbedarf | Typische Anwendung |
|-------|-------------|---------------|-------------------|
| **Q1** | Grundverspachtelung | nur Fugen + Schrauben | Unter Fliesen, nicht sichtbar |
| **Q2** | Standardverspachtelung | Q1 + breiteres Abziehen | Standard fuer Raufaser/Malervlies |
| **Q3** | Sonderverspachtelung | Q2 + Flaechenspachtelung | Fuer glatte Anstriche, feine Tapeten |
| **Q4** | Vollstaendige Flaechenspachtelung | Komplett verspachtelt | Streiflicht, hochglanz |

**Fuer Kalkulation:** Q-Stufe beeinflusst Spachtelmassenbedarf und Arbeitsaufwand erheblich.

---

## 10. Referenz-Normen Gesamtuebersicht

| Norm | Titel | Relevanz fuer Kalkulation |
|------|-------|--------------------------|
| **DIN 18181** | Gipsplatten -- Verarbeitung | *** Achsabstaende, Schraubenabstaende, Fugenversatz |
| **DIN 18340** | VOB/C Trockenbauarbeiten | *** Aufmass, Abrechnung, Oeffnungsabzuege |
| **DIN 4103-1** | Nichttragende Trennwaende | ** Grenzabmessungen, Einbaubereiche |
| **DIN 4109-1** | Schallschutz im Hochbau | ** System-Auswahl nach Rw-Anforderung |
| **DIN 4109-5** | Erhoehter Schallschutz | * Comfort-Level |
| **DIN EN 520** | Gipsplatten -- Typen | ** Plattentyp-Auswahl (A/F/H/DF) |
| **DIN EN 14195** | Metallprofile -- Masse | ** CW/UW/CD/UD-Dimensionen |
| **DIN 18182-1** | Zubehoer fuer Gipsplatten | * Befestigungsmittel |
| **DIN EN 13963** | Fugenfuellstoffe | * Spachtelarbeiten |
| **DIN 4102** | Brandverhalten Baustoffe | ** F30/F60/F90 Anforderungen |
| **DIN 18101** | Tueren im Wohnungsbau | * Standard-Tuermasse |

---

## 11. Kalkulationsparameter-Defaults (fuer MVP)

Diese Werte werden als Defaults im System hinterlegt und koennen vom Nutzer ueberschrieben werden:

```json
{
  "achsabstand_standard_mm": 625,
  "achsabstand_verstaerkt_mm": 417,
  "schraubenabstand_wand_mm": 250,
  "schraubenabstand_decke_mm": 170,
  "schraubenabstand_heftung_mm": 750,
  "fugenversatz_min_mm": 400,
  "verschnitt_standard_pct": 10,
  "verschnitt_komplex_pct": 15,
  "verschnitt_dachschraege_pct": 20,
  "oeffnungsabzug_grenze_m2": 2.50,
  "oeffnungsabzug_boden_grenze_m2": 0.50,
  "schrauben_pro_m2_wand_einfach": 15,
  "schrauben_pro_m2_wand_doppelt": 22,
  "schrauben_pro_m2_decke_einfach": 24,
  "schrauben_pro_m2_decke_doppelt": 31,
  "spachtelmasse_kg_pro_m2": 0.8,
  "fugenband_lfm_pro_m2": 1.3,
  "cw_lfm_pro_m2_625": 1.8,
  "cw_lfm_pro_m2_417": 2.6,
  "uw_lfm_pro_m2": 0.8,
  "abhaenger_pro_m2_decke": 1.8,
  "daemmung_m2_pro_m2": 1.05,
  "dichtungsband_lfm_pro_m2": 0.8
}
```
