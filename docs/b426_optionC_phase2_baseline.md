# B+4.2.6 Option C — Phase 2: Baseline & Design

**Stand:** 22.04.2026 | **Scope:** Matcher-Umbau auf strukturierte
Produkt-Codes. Parser/Extraktor aus Phase 1 bleibt unverändert.

## Aktueller Matcher-Stand (price_lookup.py)

Stage 2c in `_try_supplier_price` (Zeile 324–346):

1. Vorselektion: `active_lists` → alle Entries des Tenants mit
   `is_active=True`.
2. **a) Article-Number** exakt (wenn Query trägt article_number).
3. **b) Produktname + Hersteller exakt.**
4. **c) Fuzzy-Match:** `_best_fuzzy(candidates, material_name, key_fn)`
   via `material_normalizer.score_query_against_candidate`. Der Scorer
   hat seit B+4.2.6 (`879b9f6`) die eingebaute Profil-Code-Whitelist
   für Query-Typen `{cw, uw, ua, cd, ud}` mit 60/25/15-Gewichtung.

## Whitelist-Entscheidung

**Für heute:** `{CW, UW, UA, CD, UD}` — minimal-invasiver Fix des
B+4.2.6-Bugs.

**Bewusst nicht aufgenommen:**

- **KKZ, SLP, MP** — Putz-Codes. Kein bekannter Matching-Bug aktuell.
  Erweiterung wäre ein neuer Scope mit eigenen Golden-Tests. Trade-off:
  Risikominimierung > Abdeckungsvollständigkeit.
- **UT, TC, DA, NAO, ASA, …** — Suffix-/Artikelcodes. Diese **dürfen**
  keinen strukturierten Match bekommen (UT40 ist der Kern der
  PE-Folien-Regression).

Entscheidung später überprüfen, wenn ein konkreter Match-Bug mit
Putz-Codes auftaucht.

## Dry-Run: Code-Extraktion auf den 327 Kemmler-Entries

Ohne DB-Änderung habe ich `extract_product_code` heute Morgen auf alle
327 Einträge der Kemmler-Pricelist angewendet (read-only):

| Kategorie | Anzahl | Bewertung |
|---|---|---|
| Entries mit Whitelist-Code (CW/UW/UA/CD/UD) | **2** | `CD60` in zwei Kemmler-Befestigungs-Clips |
| Entries mit Nicht-Whitelist-Code | **124** | Mehrheit: CE (28), NAO (7), TP (6), EST, WLG, MP, SP, **UT (3)**, TC, VE, MW, SM, SEP, SN, FN, XTN, DA, NEW usw. |
| Entries ohne extrahierbaren Code | **201** | Freie Produktnamen ohne `[A-Z]{2,3}\d+`-Muster — u. a. das CW-Profil und alle TR-Kantenprofile |

**Überraschung:** kein einziger CW/UW/UA-Eintrag aus dem Kemmler-Katalog
wird erkannt. Grund: Kemmler schreibt „CW-Profil 100x50x0,6 mm" (Wort
`Profil` zwischen Typ und Dimension) — die strenge Regex überspringt
das bewusst (siehe Phase-1-Baseline-Korrektur).

## **Strategie-Entscheidung erforderlich**

Der ursprüngliche Phase-2-Plan sah einen **positiven Whitelist-Match**
vor: wenn Query-Code in Whitelist und Kandidat hat denselben
`product_code_raw` → exact match. Das Problem:

- **Null Kemmler-Entries** haben einen CW/UW/UA-Whitelist-Code.
- Bei Query `|Profile|CW|75|` greift der strukturierte Pfad daher
  nicht → Fallback auf Fuzzy.
- Die **PE-Folie-UT40-Regression** entsteht im Fuzzy-Pfad: Dämmungs-
  Rezept `|Daemmung||40mm|` → Query `"40mm"` → kein Alpha-Token → kein
  Profil-Code-Pfad im Scorer aktiv → klassischer Token-Coverage-Score
  → UT40-Candidate hat Tokens `{pe, folie, …, ut, 40}` → `"40"`
  matcht → Regression bleibt bestehen.

**→ Der reine Positiv-Match-Pfad löst die Regression nicht.**

### Zwei Strategien zur Wahl

#### Strategie A — Positiv-Pfad nur (ursprünglicher Plan)

- Matcher sucht Kandidaten mit `attributes.product_code_raw == query.raw`
  wenn Query einen Whitelist-Code hat.
- Trefferquote: sehr niedrig (nur CD60-Clips).
- **UT40-Regression bleibt** — unverändert zum Stand heute Morgen.
- **Kein Mehrwert** gegenüber Phase 1 plus dem bestehenden Matcher-Fix.

#### Strategie B — Positiv-Pfad **plus Negativ-Filter**

Zusätzlich zur Positiv-Logik: **Kandidaten ausschließen**, deren
extrahierter Code **außerhalb der Whitelist** steht **und** deren Typ
nicht zur Query-Absicht passt.

Konkret: wenn die Query keinen strukturierten Code hat (typisch bei
Dämmung, Spachtel, etc.), werden **alle** Kandidaten mit Nicht-
Whitelist-Code aus dem Pool gefiltert. UT40, TC, DA, NAO usw.
erreichen den Fuzzy-Scorer nicht mehr.

Effekt:

- PE-Folie UT40 fällt raus der Dämmungs-Kandidatenliste → Fuzzy
  greift jetzt auf **nicht-kodierte** Kandidaten (z. B. Rockwool
  Sonorock) → Regression **verschwindet**.
- CW-Profil-Entry hat keinen Code → wird nicht gefiltert → Fuzzy
  greift weiter wie gestern → CW-100-Match bleibt erhalten.
- CD60-Clips haben Whitelist-Code → kein Konflikt.

**Risiko:** ein Dämmungs-Query, der **wirklich** gegen einen Nicht-
Whitelist-Code-Eintrag matchen müsste (z. B. Wärmeleitgruppe WLG040),
wird jetzt abgelehnt. Das Rockwool-Sonorock-Entry trägt aber
`WLG040` — wird es damit auch rausgefiltert?

**Check:** Sonorock-Entry: „Trennwandpl. Sonorock WLG040, 1000x625x40
mm". Der Code ist `WLG040`, Typ `WLG`, **nicht in Whitelist** → würde
unter Strategie B aus dem Kandidatenpool fliegen. Die Dämmungs-Query
würde dann gar keinen Match mehr bekommen. **Das ist kein akzeptabler
Zustand.**

#### Strategie B' — Verfeinerung: Filter nur bei **Dimensions-Kollision**

Kandidat wird nur ausgeschlossen, wenn **sowohl** der extrahierte Code
außerhalb der Whitelist liegt **als auch** seine Dimension mit der
Query-Dimension übereinstimmt — d. h. genau der Fall, in dem die
Dimension den Fuzzy-Score „trügerisch" hoch treibt.

Beispiel:

- Query `40mm` (Dämmung) → `q_dim = 40`.
- UT40 → `c_type="UT" ∉ Whitelist`, `c_dim=40 == q_dim` →
  **ausschließen** (Kollisions-Filter).
- WLG040 (Sonorock) → `c_type="WLG" ∉ Whitelist`, `c_dim=040`. Wenn
  `040` == `40` (numerisch, nicht string) → auch hier **ausschließen**?

Das bricht den WLG-Fall ebenfalls. Der Dimensions-Vergleich kann nicht
unterscheiden, ob UT oder WLG gefährlich ist.

→ Strategie B/B' funktioniert **nicht ohne zusätzliche Logik**. Um WLG
durchzulassen, aber UT auszuschließen, bräuchten wir eine **zweite
Liste**: eine *Blacklist* expliziter „gefährlicher Codes" — im
Gegensatz zur *Whitelist* „erlaubter Codes".

#### Strategie C — Blacklist statt Whitelist im Matcher

**Konkret:**

- Kein struktureller Positiv-Match-Pfad.
- Stattdessen: Kandidaten-Pre-Filter im Fuzzy-Schritt. Wenn
  `candidate.attributes.product_code_type ∈ Blacklist {UT, TC, DA, …}`
  **und** die Query enthält dieselbe numerische Dimension → schließ
  den Kandidaten aus.
- Whitelist `{CW, UW, UA, CD, UD}` bleibt im Scorer, wie heute.

**Vorteil:** chirurgischer Eingriff. Nur die bekannten Schad-Codes
(UT, TC, DA) werden blockiert. WLG, CE, NAO etc. bleiben unberührt;
Sonorock-Match auf Dämmung wird nicht beschädigt.

**Nachteil:** Wartung der Blacklist. Jeder neue Problem-Code muss
händisch aufgenommen werden. Aber: der Blacklist-Ansatz ist in der
Praxis meistens robust genug, solange die Liste klein bleibt.

### Empfehlung

**Strategie C.** Die ursprünglich geplante Whitelist-Logik (Strategie A)
löst das eigentliche Problem nicht (zu wenige Whitelist-Hits im
Kemmler-Katalog). Strategie B verursacht Kollateralschaden bei
WLG040-Dämmung. Strategie C ist minimal-invasiv:

- `price_lookup` bekommt einen kleinen Pre-Filter im Stage-2c-Schritt:
  bei Kandidaten-Code in Blacklist + Dimensions-Kollision → raus.
- Fuzzy-Scorer bleibt unverändert (Whitelist für Profil-Codes weiter
  aktiv, keine neue Logik).
- Null Änderung am Parser, am Extraktor, am Rezept.

Blacklist-Kandidaten für heute: `{UT, TC, DA}` — die drei Code-Typen
mit `d=40`-Varianten im Kemmler-Katalog, die die Regression auslösen
können. Liste wird im Code direkt hartkodiert, mit Kommentar zum
Design-Trade-off.

### Frage an Benjamin

**Welche Strategie wird umgesetzt?** Die bestehende Phase-2-Spec geht
von Strategie A aus; mein Dry-Run zeigt, dass A die Regression nicht
löst. Strategie C ist die minimalste Änderung, die das Kernproblem
adressiert. Strategie B/B' schlage ich **nicht** vor (Kollateralschaden).

Falls Strategie A trotzdem gewollt ist (weil „Feature ist Feature",
Regression-Fix passiert woanders), würde Phase 2 den CD60-Matcher für
zwei Entries liefern und die UT40-Regression müsste über eine
separate Runde gelöst werden.

## Backfill-Erwartung (angepasst)

- **Strategie A oder C:** Backfill ~126 Entries bekommen neue
  `attributes.product_code_*`-Felder (alle mit Code, in oder außerhalb
  Whitelist). **Außerhalb** der ursprünglich veranschlagten 10–30.
- **Interpretation:** der Extraktor ist präziser als gedacht (erkennt
  auch Nicht-Profile-Codes); die Whitelist/Blacklist macht die
  Unterscheidung. Die 126 sind kein Fehler, sondern vollständige
  Strukturierung des Katalogs.

## Blacklist-Verifikation (nachgetragen)

Bevor die Blacklist `{UT, TC, DA}` festgeschrieben wird, Einzel-Review
aller Kemmler-Entries pro Code-Typ. Ziel: echte **Suffixe** (wie UT als
Varianten-Kennzeichner) von **echten Typ-Produkten** (wie Direktabhänger
DA) unterscheiden, damit wir nichts versehentlich herausfiltern, was
legitimer Match-Kandidat ist.

### UT — 3 Treffer, alle PE-Folien-Suffixe ✓

| raw | dim | unit | product_name |
|---|---|---|---|
| UT40 | 40 | €/m² | PE-Folie S=0,20 mm - 4000 mm x 50 m/Ro. farbstichig - UT40 |
| UT40 | 40 | €/m² | PE-Folie S=0,30 mm - 4000 mm x 25 m/Ro. farbstichig - UT40 |
| UT20 | 20 | €/m² | PE-Folie S=0,20 mm - 4000 mm x 50 m/Ro. farbstichig - UT20 |

**Semantik:** „UT" steht bei PE-Folien am Namensende als Varianten-
Kennzeichner (vermutlich „Untertyp"). Keines der drei Produkte ist ein
„UT-Produkt" im Sinne eines eigenen Typs — die PE-Folie ist der Haupt-
Typ. Dimensionen 40 und 20 sind **hoch kollisionsgefährdet** mit
Dämmungs-Rezept-Queries (40mm, 20mm sind gängige Dämmstärken).
**Blacklist: Ja.**

### TC — 3 Treffer, alle Kemmler-Artikelnummern-Präfix ⚠

| raw | dim | unit | product_name |
|---|---|---|---|
| TC7700 | 7700 | €/Rolle | TC7700 Zellvlies 130 g/m² 750 mm breit x 25 m/Rol |
| TC4303 | 4303 | €/Eimer | TC4303 Mineral-Streichputz Korn 0,8 mm – 20 kg/Eimer |
| TC4303 | 4303 | €/Eimer | TC4303 Mineral-Streichputz Korn 0,8 mm – 7 kg/Eimer |

**Semantik:** „TC" ist Kemmler-interne Artikelnummern-Serie (technische
Kennung, kein Produkt-Typ). Die Dimensionen 7700 und 4303 sind
**unrealistisch** als Rezept-Dimensionen (7,7 m bzw. 4,3 m — keine
typische mm-Angabe). Eine Kollision mit einer Rezept-Query ist extrem
unwahrscheinlich. **Blacklist: Ja** — harmlos, weil keine Kollision
erwartet, aber schützt gegen künftige Rezepte mit ungewöhnlichen
Dimensionen.

### DA — 2 Treffer, **echtes Typ-Produkt** (Direktabhänger) ✗

| raw | dim | unit | product_name |
|---|---|---|---|
| DA125 | 125 | €/Ktn. | DA125 Direktabhänger 125 mm gestreckt – für CD 60/27 – 100 Stk/Ktn. |
| DA200 | 200 | €/Ktn. | DA200 Direktabhänger 200 mm gestreckt, für CD 60/27 – 100 Stk/Ktn. |

**Semantik:** „DA" = Direktabhänger, ein echtes Trockenbau-Produkt (kein
Suffix). DA125 und DA200 sind zwei Varianten eines eigenständigen
Bauteils. Dimensionen 125 und 200 mm sind zwar **realistisch** als
Abhänge-Längen, aber nicht als gängige Rezept-Dimensionen (Rezepte
fragen nach Profil-Maßen 50/75/100 oder Dämmungs-Dicken 30/40/60).

**Blacklist: NEIN.** Ein Blacklist-Eintrag würde bei einer hypothetischen
zukünftigen Rezept-Query mit `dim=125` oder `dim=200` den einzigen
legitimen Direktabhänger-Kandidaten aus dem Pool werfen. Das ist
kein akzeptables Design.

### Finale Blacklist: `{UT}`

Für Phase 2 wird die Blacklist auf **`{UT}` allein** festgelegt.

**Warum nicht auch TC?** Diskussion im Team-Review: TC hat aktuell
**keinen konkreten Bug** und **keinen Test-Case**, der Filterung
verlangt. Eine präventive Aufnahme widerspricht der „do the minimum"-
Disziplin. Wenn ein TC-Matching-Fall echte Probleme macht, wird er mit
konkretem Test-Case in einem späteren Block behandelt.

**Warum nicht DA?** DA ist ein **echtes Typ-Produkt** (Direktabhänger
DA125/DA200). Blacklist würde legitime Match-Kandidaten blockieren.

**Erweiterungsregel:** Jede zukünftige Blacklist-Erweiterung braucht
(a) einen konkret reproduzierten Regressions-Fall **und** (b) einen
Golden-Test, der den Filter erzwingt. Keine präventiven Einträge.

**Scope-Konsequenz für Phase 2-Tests:**

- Test 1 (UT-Filter + TC-Guard) prüft beides: UT wird gefiltert,
  TC bleibt im Pool.
- Test 3 (Nicht-Blacklist) nutzt WLG040 (unverändert).
- Alle anderen Tests unabhängig von der finalen Blacklist-Grösse.

## Scope-Bilanz Phase 2

- ✗ Kein Parser-Touch.
- ✗ Kein `_explode_alnum`-Touch.
- ✓ Genau ein Code-Pfad-Update im `price_lookup` (abhängig von
  Strategie-Entscheidung).
- ✓ Backfill-Skript in 2c (deterministisch, ohne API).
- ✓ E2E auf Stuttgart-LV in 2d.

**Kein Push vor grünem E2E.**
