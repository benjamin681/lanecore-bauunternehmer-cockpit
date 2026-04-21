# Parser-Baseline vor generic-Prompt-Upgrade (2026-04-21)

Gesnapshottet vor B+4.3-Parser-Upgrade, als 4 Pricelists fuer den E2E-Tenant
`19f3cd31-3de6-4baa-9de6-317412d32783` aktiv waren. Alle Zahlen stammen aus
`data/lv_preisrechner.db` zum Zeitpunkt des Upgrade-Commit.

## Kemmler — Ausbau 2026-04

- pricelist_id: `56eaf132-471e-4b35-b16f-252cacf6f31b`
- status: `APPROVED`
- entries: **327**
- avg_confidence: **0.73**
- needs_review: **119** (36%)

### Attribute-Schluessel

| Attribute | Count |
|---|---:|
| `dimensions` | 122 |
| `thickness` | 86 |
| `weight` | 68 |
| `color` | 67 |
| `packaging` | 50 |
| `length` | 44 |
| `bundle_length` | 43 |
| `pieces_per_package` | 40 |
| `width` | 39 |
| `material` | 35 |
| `grain` | 25 |
| `pieces_per_carton` | 19 |

### Unit/Effective-Unit-Verteilung (Top 8)

| unit / effective_unit | Count |
|---|---:|
| `€/Sack / kg` | 66 |
| `€/m / lfm` | 54 |
| `€/m² / m²` | 54 |
| `€/Paket / €/Paket` | 50 |
| `€/Stk. / €/Stk.` | 30 |
| `€/Rolle / m²` | 19 |
| `€/Ktn. / €/Karton` | 19 |
| `€/kg / kg` | 11 |

### 3 Beispiel-Entries

**hi-conf** — article=`3005150028`

- product_name: `Kemmler KKZ30 Kalk-Zement-Putz KKZ30 30 kg/Sack`
- price_net: `8.1 EUR/€/Sack` → eff `0.27/kg`
- confidence: `0.95` | needs_review: `False`
- attributes: `{"weight": "30 kg"}`
- source_row_raw: `Kemmler KKZ30 Kalk-Zement-Putz KKZ30 30 kg/Sack 3005150028 8,10 €/Sack`

**mid-conf** — article=`3505150116`

- product_name: `OWA construkt cliq 24CT Verbindungsprof. B=24 mm H=25 mm, BL=625 mm - 60 St./Bd.`
- price_net: `1.4 EUR/€/m` → eff `1.4/lfm`
- confidence: `0.55` | needs_review: `True`
- attributes: `{"width": "24 mm", "height": "25 mm", "length": "625 mm", "pieces_per_bundle": 60}`
- source_row_raw: `OWA construkt cliq 24CT Verbindungsprof. B=24 mm H=25 mm, BL=625 mm - 60 St./Bd. 3505150116 1,40 €/m`

**lo-conf** — article=`3505150107`

- product_name: `OWA Spannabhänger Nr. 12/44 100 St./Pak.`
- price_net: `34.22 EUR/€/Paket` → eff `34.22/€/Paket`
- confidence: `0.3` | needs_review: `True`
- attributes: `{"pieces_per_pack": 100}`
- source_row_raw: `OWA Spannabhänger Nr. 12/44 100 St./Pak. 3505150107 34,22 €/Paket`


## Wölpert — Angebot 2026-03

- pricelist_id: `348b561d-3dcc-41f1-95aa-93930de06fd7`
- status: `PARSED`
- entries: **37**
- avg_confidence: **0.373**
- needs_review: **33** (89%)

### Attribute-Schluessel

| Attribute | Count |
|---|---:|
| `length` | 21 |
| `thickness` | 19 |
| `conversion` | 16 |
| `surface` | 14 |
| `color` | 12 |
| `bundle` | 12 |
| `dimensions` | 11 |
| `packaging` | 11 |
| `unit_conversion` | 6 |
| `brand` | 5 |
| `weight` | 4 |
| `volume` | 4 |

### Unit/Effective-Unit-Verteilung (Top 8)

| unit / effective_unit | Count |
|---|---:|
| `€/H / €/H` | 13 |
| `H / H` | 7 |
| `E / E` | 5 |
| `€/T / €/T` | 3 |
| `€/L / €/L` | 3 |
| `€/St / Stk` | 2 |
| `€/M / lfm` | 2 |
| `€/Sa / €/Sa` | 1 |

### 3 Beispiel-Entries

**hi-conf** — article=`31108578`

- product_name: `Baumit Silikoncolor weiß 14 l`
- price_net: `5.95 EUR/€/St` → eff `5.95/Stk`
- confidence: `1.0` | needs_review: `False`
- attributes: `{"volume": "14 l", "color": "wei\u00df"}`
- source_row_raw: `14,0 31108578 Baumit Silikoncolor weiß 14 l 14,00 L 1 St (=1 St) 5,95 E 83,30`

**lo-conf** — article=`30109160`

- product_name: `Baumit Starcontact KBM-FIX Leicht weiß 25 kg`
- price_net: `669.0 EUR/€/T` → eff `669.0/€/T`
- confidence: `0.3` | needs_review: `True`
- attributes: `{"weight": "25 kg", "color": "wei\u00df", "pallet": "1 PAL = 42 Sa", "conversion": "1 Sa = 0,025 T"}`
- source_row_raw: `2,0 30109160 Baumit Starcontact KBM-FIX Leicht weiß 25 kg 1,050 T 42 Sa (=1 PAL) 669,00 E 702,45`


## Hornbach Union — Jahresangebot Putzbänder 2026

- pricelist_id: `f1aa9085-2d5d-45f7-b079-d8705bdc57ad`
- status: `PARSED`
- entries: **15**
- avg_confidence: **0.34**
- needs_review: **14** (93%)

### Attribute-Schluessel

| Attribute | Count |
|---|---:|
| `dimensions` | 13 |
| `color` | 12 |
| `type` | 12 |
| `material` | 4 |
| `variant` | 4 |
| `volume` | 2 |
| `product_code` | 1 |

### Unit/Effective-Unit-Verteilung (Top 8)

| unit / effective_unit | Count |
|---|---:|
| `€/Rolle / €/Rolle` | 12 |
| `€/KTU / €/KTU` | 2 |
| `€/Rolle / m²` | 1 |

### 3 Beispiel-Entries

**hi-conf** — article=`8720141036`

- product_name: `Verputzerband weiß 48mmx33m mit 30% Recyclinganteil im PE Träger`
- price_net: `3.54 EUR/€/Rolle` → eff `2.2348/m²`
- confidence: `0.9` | needs_review: `False`
- attributes: `{"dimensions": "48mm x 33m", "color": "wei\u00df", "material": "PE Tr\u00e4ger"}`
- source_row_raw: `2 Artikelnummer: 8720141036 Verputzerband weiß 48mmx33m mit 30% Recyclinganteil im PE Träger 36,000 Rolle 3,54 127,44`

**lo-conf** — article=`8720140287`

- product_name: `Masker mit Gewebeband blau 550mm 20m Typ 3833`
- price_net: `2.47 EUR/€/Rolle` → eff `2.47/€/Rolle`
- confidence: `0.3` | needs_review: `True`
- attributes: `{"dimensions": "550mm x 20m", "color": "blau", "type": "Typ 3833"}`
- source_row_raw: `5 Artikelnummer: 8720140287 Masker mit Gewebeband blau 550mm 20m Typ 3833 60,000 Rolle 2,47 148,20`


## Hornbach Union — Baumit Jahresangebot 2026

- pricelist_id: `c9e16248-f8e8-4bd6-b365-504e1817a4a9`
- status: `PARSED`
- entries: **27**
- avg_confidence: **0.322**
- needs_review: **26** (96%)

### Attribute-Schluessel

| Attribute | Count |
|---|---:|
| `weight` | 21 |
| `color` | 7 |
| `type` | 6 |
| `surcharge_type` | 3 |
| `rate` | 3 |
| `length` | 2 |
| `grain_size` | 2 |
| `mesh_size` | 1 |
| `roll_size` | 1 |
| `dimensions` | 1 |
| `binder` | 1 |
| `note` | 1 |

### Unit/Effective-Unit-Verteilung (Top 8)

| unit / effective_unit | Count |
|---|---:|
| `€/Sack / €/Sack` | 21 |
| `€/X / €/X` | 3 |
| `€/qm / m²` | 1 |
| `€/LFDM / €/LFDM` | 1 |
| `€/Stück / €/Stück` | 1 |

### 3 Beispiel-Entries

**hi-conf** — article=`2848010069`

- product_name: `Baumit VWS-Gewebe StarTex MW 4x4,5mm Armierungsgewebe fein, Rolle a 50x1,10m`
- price_net: `0.95 EUR/€/qm` → eff `0.95/m²`
- confidence: `0.9` | needs_review: `False`
- attributes: `{"mesh_size": "4x4,5mm", "roll_size": "50x1,10m"}`
- source_row_raw: `2 Artikelnummer: 2848010069 Baumit VWS-Gewebe StarTex MW 4x4,5mm Armierungsgewebe fein, Rolle a 50x1,10m 55,000 qm 4,35 -78,16% 0,95 52,25`

**lo-conf** — article=`2848010185`

- product_name: `Baumit Anputzleiste 3D pro 2400mm, Standard`
- price_net: `3.3 EUR/€/LFDM` → eff `3.3/€/LFDM`
- confidence: `0.3` | needs_review: `True`
- attributes: `{"length": "2400mm"}`
- source_row_raw: `4 Artikelnummer: 2848010185 Baumit Anputzleiste 3D pro 2400mm, Standard 2,400 LFDM 7,32 -54,92% 3,30 7,92`


