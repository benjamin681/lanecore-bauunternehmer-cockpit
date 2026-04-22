# Follow-ups nach B+4.3.0b

**Stand:** 22.04.2026 nach Push der Candidates-Endpoint-Implementierung.
**Remote:** `7398da4`. Keiner der Punkte unten ist ein Pilot-Blocker —
alle können in einer späteren Session adressiert werden.

## FU-1 — Estimated-Platzhalter 0 € trotz vorhandener Entries

**Kontext:** Im Phase-4-Smoke-Test zeigt die W628A-Position bei der
Dämmungs-Material-Zeile (`40mm` Query, Kategorie `Daemmung`) einen
estimated-Eintrag mit `price_net=0.00` und dem Fallback-Reason „Kein
Katalog-Durchschnitt verfuegbar" — obwohl Sonorock WLG040 (3,05 €/m²)
und Thermolan TP115 (1,79 €/m²) als echte supplier_price-Kandidaten
sauber gefunden werden.

**Vermutung:** `_build_estimated_candidate` iteriert über Entries der
Kategorie, prüft `unit_matches(query_unit, r.effective_unit)` und
`unit_matches(query_unit, r.unit)`. Edge-Case in einem der beiden
Aufrufe — vermutlich liefert `r.effective_unit` bei manchen Entries
etwas Nicht-passendes zurück (leer oder anders normiert), so dass
die `prices`-Liste leer bleibt und der None-Rückgabezweig greift.

**Scope:** Bugfix im estimated-Pfad. Frontend ist nicht betroffen,
weil die echten supplier_price-Kandidaten korrekt geliefert werden.
Der Platzhalter stört nur den Richtwert-Case.

**Priorität:** niedrig. Kein Pilot-Blocker, weil echte Matches
vorliegen.

**Tracking:** eigenes Ticket bei Bedarf; sonst in der nächsten
Pflege-Session abarbeiten.

## FU-2 — Fuzzy-Kandidaten mit niedrigem Score als Noise

**Kontext:** Bei der W628A-Position liefert die UW-75-Material-Zeile
als Winner einen „GK-Plattenstreifen" mit Score 0,33 — rein
alphabetisches Match über Kategorie und Einheit, semantisch sinnlos.
Auch die CW-75-Liste enthält Kandidaten wie „TB Bewegungsprofil …"
mit 0,33.

**Impact:** Top-3 füllt sich mit Rauschen. Der Handwerker sieht
drei „Ähnliche Artikel, die passen könnten" — aber mindestens zwei
davon passen nicht.

**Lösung:** UI-seitig dämpfen gemäss `lv-preisrechner/docs/
ui_wording_guide.md`:

- Kandidaten mit `match_confidence < 0.40` bekommen das Label
  „unsicher, bitte prüfen" und optional eine gedimmte Schrift.
- Kandidaten mit < 0.20 eventuell ganz ausblenden (UI-Filter,
  kein Backend-Eingriff).

**Alternative Backend-Variante** (größerer Eingriff): untere Score-
Grenze im `list_candidates_for_position`-Sortier-Step (z. B.
`if score < 0.30: continue`). Nicht empfohlen, weil dadurch die
Anzahl sichtbarer Kandidaten unvorhersehbar wird.

**Scope:** Frontend-Ticket in B+4.3.1.

**Priorität:** mittel — beeinflusst die UX, aber nicht die Korrektheit.

## FU-3 — Near-Miss-Drawer muss viele Material-Sektionen vertragen

**Kontext:** Die W628A-Position liefert 6 Material-Sektionen (Fireboard,
CW 75, UW 75, Dämmung 40 mm, Schrauben, Spachtel). Andere Rezepte
könnten ähnlich viele oder mehr haben (W635 mit mehrfach-Profilen,
D112 mit mehreren UK-Ebenen).

**Impact:** Drawer darf nicht einfach linear alle 6 Sektionen
untereinander rendern — der Handwerker würde scrollen müssen.

**Lösungsoptionen für B+4.3.1:**

- **Accordion:** nur ein Material auf einmal geöffnet, andere
  eingeklappt. Empfohlen — kompakt und übersichtlich.
- **Tabs:** pro Material ein Tab. Benötigt horizontalen Platz,
  schwierig auf Mobile.
- **Long-Scroll:** einfach alles untereinander. Akzeptabel für
  Desktop, problematisch für Mobile.

**Empfehlung:** Accordion. Das erste Material (meist das Hauptpreis-
treibende, z. B. Gipskarton) wird standardmäßig expandiert, alle
anderen eingeklappt.

**Scope:** UI-/UX-Entscheidung in B+4.3.1.

**Priorität:** mittel — beeinflusst den Drawer direkt.

## FU-4 — Optional: Blacklist-Erweiterung nachrüsten

**Kontext:** Aktuelle Blacklist ist `{UT}` (nur PE-Folien-Suffix).
Beim Smoke-Test fielen keine weiteren False-Positives auf, aber das
ist keine Garantie für andere LVs oder andere Lieferanten.

**Regel (aus B+4.2.6-Baseline):** Blacklist-Erweiterung braucht
zwingend:
(a) konkret reproduzierten Regressions-Fall
(b) Golden-Test, der den Filter erzwingt.

**Tracking:** offen, keine Aktion heute.

## Offene Punkte außerhalb B+4.3.0b

Für den Planungs-Block zur nächsten Session:

- **B+4.3.1:** Near-Miss-Drawer + Manual-Override-UI + Wording-
  Migration. Der Endpoint steht, das Frontend kann gegen ihn
  arbeiten.
- **B+4.3.2:** Katalog-Lücken-Report (Tab `/gaps`) — Datenquelle
  ist `Position.needs_price_review`-Filter, keine neuen Backend-
  Endpoints nötig.
- **Hetzner-Deployment-Setup** und **Pilot-Onboarding-Materialien**
  bleiben offen.
