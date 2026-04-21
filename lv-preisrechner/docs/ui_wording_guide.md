# UI Wording Guide — LV Kalkulierer

**Stand:** 21.04.2026
**Gilt für:** alle User-facing Texte im Frontend (Labels, Buttons, Pills, Tooltips, Fehlermeldungen, PDF-Export)

## Prinzip

Jeder Begriff im UI beantwortet für den Handwerker eine von zwei Fragen:

1. **"Kann ich das abgeben?"** → direkt, ohne Zögern
2. **"Muss ich was tun?"** → klar, was zu tun ist

Keine Insider-Begriffe. Keine Prozent-Zahlen ohne erklärende Bedeutung. Kein Fachchinesisch. Zielgruppe: Meister und Bauleiter im Handwerk, nicht Software-Entwickler.

## Status-Pills (Kern-Lexikon)

| Verwenden | Vermeiden | Bedeutung |
|---|---|---|
| Preis gefunden | Sicher · Direkt · Exact Match · Stage 1 | Direkter Treffer im Lieferantenkatalog |
| Ähnlicher Artikel | Fuzzy · Fuzzy Match · Stage 2 | Nicht identisch, aber wahrscheinlich passend |
| Richtwert | Geschätzt · Estimated · Stage 4 · Fallback | Kein Katalog-Treffer, Preis aus Erfahrungswerten |
| Fehlt im Katalog | Nicht gefunden · Not found · No match | Kein Preis, muss manuell ergänzt werden |

## Confidence-Stufen (für Detail-Ansichten)

Interne Confidence-Scores werden nicht als Prozentzahl angezeigt. Übersetzung:

| Score-Range | Anzeige |
|---|---|
| ≥ 0,85 | fast sicher |
| 0,65 – 0,84 | wahrscheinlich passend |
| 0,40 – 0,64 | eher unsicher |
| < 0,40 | unsicher, bitte prüfen |

## Metriken und Dashboards

| Verwenden | Vermeiden |
|---|---|
| Preise stehen · 9 von 11 | Material gesichert · 82 % · 9/11 |
| Noch zu prüfen · 2 | Offen zur Prüfung · 2 · needs_review |
| Angebotssumme | Sum · Total · Gesamt-Netto (wenn nicht differenziert) |
| Aktualisiert vor 2 Min | Last updated · Modified timestamp |

## Buttons und Aktionen

| Verwenden | Vermeiden |
|---|---|
| Preis selbst eintragen | Manuellen Preis setzen · Override · Manual price |
| Beim Lieferanten anfragen | Katalog-Lücke melden · Gap report |
| Angebot als PDF | Export PDF · PDF-Download |
| Kalkulation neu starten | Re-calculate · Recompute |

## Detail-Texte (Expand-Panels)

| Verwenden | Vermeiden |
|---|---|
| Treffer in der Kemmler-Preisliste · fast sicher | Direkter Treffer · Kemmler · Confidence 98 % |
| Ähnlicher Artikel bei Kemmler · wahrscheinlich passend | Fuzzy-Match · Kemmler · Confidence 78 % |
| Richtwert aus Branchen-Erfahrung · bitte prüfen vor Abgabe | Estimated price · Branch average · Stage 4 fallback |
| Nicht in deinen Preislisten · 3 ähnliche Artikel gefunden | No match in active supplier lists · 3 near-miss candidates |
| 167,40 €/Karton auf 3,05 €/m² umgerechnet | Bundle resolution · 167,40 €/Ktn ÷ 55 m² |
| lfm und m sind dasselbe | Einheit lfm auf m normalisiert · unit_normalizer |
| 78,16 % Rabatt bereits eingerechnet | Rabatt −78,16 % angewandt · discount applied |
| Karton mit 100 Stück · auf Stückpreis umgerechnet | Gebinde-Auflösung · 21,56 €/Ktn (100 St) → 0,22 €/St |

## Near-Miss-Kandidaten (Drawer)

| Verwenden | Vermeiden |
|---|---|
| Ähnliche Artikel, die passen könnten | Near-Miss candidates · Top-3 candidates |
| anderer Profil-Typ · eher unsicher | Profile type mismatch · Low confidence |
| anderes Maß · eher unsicher | Size deviation · Low match score |

## Fehler- und Hinweistexte

| Verwenden | Vermeiden |
|---|---|
| Kalkulation läuft … | Parsing in progress · PARSING |
| Kalkulation fehlgeschlagen — bitte erneut versuchen | Error: parse_error · Status ERROR |
| Verbindung zum Server unterbrochen | Connection lost · 503 Service Unavailable |
| Dein Dokument wird geprüft | Document validation in progress |

## Sprach-Register

- **Duzen oder Siezen?** → Siezen. Professioneller Kontext, Meister/Bauleiter im Gespräch mit Kunden. Ausnahmen: Bestätigungen wie "Dein Angebot ist fertig" — da kann die persönlichere Form stehen. Konsistenz innerhalb eines Screens wichtiger als starre Regel.
- **Aktiv statt Passiv** → "Preis wurde gefunden" ❌ / "Preis gefunden" ✅
- **Zahlen ausgeschrieben** bei kleinen Zahlen (eins bis zwölf) außer in Tabellen-Kontexten mit tabular-nums
- **Währung** → immer mit Komma als Dezimaltrenner und Tausender-Punkt: "1.234,56 €"
- **Einheiten** → immer mit non-breaking-space und Komma: "45,50 m²" (nicht "45.5m²")

## Was NICHT übersetzen

Folgende Begriffe bleiben Fachterminologie, weil sie branchenintern so verwendet werden:

- LV, Position, Zulage, Vorhaltung, Pauschale
- Leistungsverzeichnis, Auftraggeber, Auftragnehmer
- Gebinde, Karton, Sack, Rolle, Palette, Eimer
- Materialnamen wie Gipskartonplatte, CW-Profil, UW-Profil, Trennwandplatte
- Abkürzungen wie lfm, qm, m², St, Stk, Pkg, Ktn

## Pflege dieses Dokuments

Dieses Dokument ist die Single-Source-of-Truth für User-facing Strings. Änderungswunsch? Pull Request mit klarer Begründung, warum die alte Formulierung nicht funktioniert hat.

Bei neuen UI-Elementen: erst hier eintragen, dann bauen. Nicht andersrum.
