# LaneCore AI — v2 Roadmap

## v2.1: Machine Learning / Feedback-Loop

### Problem
Wenn ein Nutzer KI-Werte korrigiert (z.B. Fläche von 13.27 auf 14.5 m²), geht dieses Wissen verloren.
Andere Kunden profitieren nicht von den Korrekturen.

### Lösung: Prompt-Tuning via Feedback-Loop

1. **Korrekturen erfassen** (bereits gebaut):
   - PATCH /{job_id}/result speichert korrigierte Werte
   - Editierte Felder werden mit `_edited: true` markiert

2. **Korrektur-Datenbank aufbauen**:
   - Neue Tabelle `analyse_korrekturen`:
     - job_id, feld (z.B. "raeume[3].flaeche_m2"), alter_wert, neuer_wert, user_id
   - Aggregiert über alle Kunden (anonymisiert)

3. **Prompt verbessern** (nicht klassisches ML):
   - Monatliche Analyse der häufigsten Korrekturen
   - Patterns erkennen: "Bei Deckenspiegel wird flaeche_m2 oft 5-10% zu niedrig"
   - Prompt-Anpassungen: "Beachte: Raumflächen in Deckenspiegel sind oft Netto-Flächen. Rechne die Fläche des Raumstempels dazu."
   - A/B-Testing: Neuer Prompt vs. alter Prompt auf historischen Plänen

4. **Konfidenz-Kalibrierung**:
   - Vergleiche KI-Konfidenz mit tatsächlicher Fehlerrate nach Korrekturen
   - Wenn KI sagt "90% sicher" aber 30% der Werte korrigiert werden → Konfidenz-Modell anpassen

### Technische Umsetzung
- Tabelle: `analyse_korrekturen` (job_id, feld, alt, neu, user_id, created_at)
- Cron-Job: Monatliche Aggregation → Report an LaneCore-Team
- Prompt-Versioning: Jeder Prompt bekommt eine Version, A/B-Vergleich möglich
- Kein TensorFlow/PyTorch nötig — Claude's Stärke ist Prompt-Engineering

### Aufwand: 2-3 Wochen
### Priorität: Hoch — differenziert uns vom Wettbewerb

---

## v2.2: Lizenzierung + Zugangskontrolle

### Problem
- Kunden die nicht zahlen müssen gesperrt werden können
- Programm darf nicht an Kollegen weitergegeben werden
- Testversion für Neukunden

### Lösung: Clerk Auth + Subscription-Management

1. **Clerk Auth Integration** (bereits im Tech-Stack vorgesehen):
   - Login via E-Mail/Passwort oder Google
   - Jeder User bekommt eine Clerk User-ID (ersetzt "dev-user")
   - Session-Management über Clerk

2. **Subscription-Tiers**:
   ```
   TRIAL:      14 Tage, max 3 Analysen, Wasserzeichen auf PDF
   STARTER:    49 EUR/Monat, 20 Analysen/Monat, 1 User
   BUSINESS:   149 EUR/Monat, unbegrenzt, 5 User, Priority-Support
   ENTERPRISE: Individuell, API-Zugang, On-Premise Option
   ```

3. **Zugangs-Kontrolle**:
   - Middleware checkt Subscription-Status bei jedem API-Call
   - Admin-Dashboard für LaneCore-Team: User sperren, Plan ändern, Usage sehen
   - IP-basierte Session-Limitierung (max 2 gleichzeitige Sessions)

4. **Testversion**:
   - Registrierung ohne Kreditkarte
   - 14 Tage voll funktionsfähig
   - Max 3 Analysen
   - PDF-Export mit "TESTVERSION — LaneCore AI" Wasserzeichen
   - Nach Ablauf: Read-only Zugang auf bisherige Ergebnisse

5. **Anti-Weitergabe**:
   - Login per E-Mail + Gerätebindung (Device-Fingerprint)
   - Gleichzeitige Logins limitiert
   - Usage-Monitoring: Ungewöhnliche Patterns → Alert

### Technische Umsetzung
- Clerk: clerk.com (React + Python SDK)
- Stripe: Subscription Billing
- Middleware: `app/core/auth.py` erweitern
- Admin-Panel: Separates Dashboard für LaneCore-Team

### Aufwand: 3-4 Wochen
### Priorität: Kritisch für Monetarisierung

---

## v2.3: Plan-Versions-Vergleich (Diff-View)

### Problem
Bauprojekte durchlaufen dutzende Revisionen. Der Unternehmer will wissen:
"Was hat sich in Version 3 gegenüber Version 2 geändert?"

### Lösung: Analyse-Diff

1. **Vergleichs-Endpoint**:
   - `GET /api/v1/bauplan/diff?job_a={id}&job_b={id}`
   - Returns: Neue Positionen, entfallene Positionen, geänderte Maße

2. **Frontend Diff-View**:
   - 2-Spalten-Ansicht: Alt | Neu
   - Grün: Neue Positionen
   - Rot: Entfallene Positionen
   - Gelb: Geänderte Werte (mit Delta)
   - Delta-Kalkulation: "Version 3 kostet X EUR mehr"

3. **Automatische Erkennung**:
   - Räume über raum_nr matchen
   - Wände über Position (von_raum/zu_raum) matchen
   - Decken über raum_nr matchen

### Aufwand: 2 Wochen
### Priorität: Mittel-Hoch — macht LaneCore unverzichtbar

---

## v2.4: Erweiterte Features (Backlog)

- **Google Maps API** für exakte Anfahrtskosten-Berechnung (Entfernung + Fahrzeit)
- **Materialbestellung direkt** — One-Click Bestellung beim günstigsten Lieferanten
- **Bautagebuch** — Tägliche Fortschrittsdokumentation
- **Sub-Unternehmer-Portal** — Subs bekommen eigenen Zugang mit ihren Aufgaben
- **DATEV-Export** — Rechnungsdaten direkt an Buchhaltung
- **BIM/IFC-Import** — 3D-Modelle direkt analysieren (statt 2D-PDF)
- **Mobile App** — Baustellenfotos → automatische Aufmaßprüfung

---

## Timeline

| Phase | Zeitraum | Features |
|-------|----------|----------|
| MVP (v1.0) | Bis 26.05.2026 | Alles was jetzt gebaut ist ✅ |
| v1.1 | Juni 2026 | Bug-Fixes, Performance, Pilot-Feedback |
| v2.1 | Juli 2026 | ML Feedback-Loop |
| v2.2 | Aug 2026 | Lizenzierung + Billing |
| v2.3 | Sep 2026 | Plan-Vergleich |
| v2.4 | Q4 2026 | Erweiterte Features |
