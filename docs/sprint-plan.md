# Sprint-Plan — LaneCore AI MVP

**MVP-Deadline:** 26.05.2026
**Vollversion:** 30.06.2026
**Pilot-Kick-off:** nach Termin 17.04.2026 in Ulm

---

## Sprint-Übersicht

| Sprint | KW | Zeitraum | Ziel | Status |
|--------|-----|----------|------|--------|
| 0 | 16 | 14.–18.04. | Setup, Termin Ulm, Spec | In Arbeit |
| 1 | 17–18 | 21.04.–02.05. | Backend + Claude-Integration | Offen |
| 2 | 19–20 | 05.–16.05. | Analyse-Engine, Tests | Offen |
| 3 | 21–22 | 19.–26.05. | **MVP: Frontend, E2E, Pilot** | Offen |
| 4 | 23–24 | 27.05.–07.06. | Feedback-Iteration | Offen |
| 5 | 25–26 | 08.–30.06. | Säule 2 Vorbereitung, Polishing | Offen |

---

## Sprint 0 (KW 16) — Setup & Discovery

**Ziel:** Fundament legen, Anforderungen mit Pilot-Kunde validieren

### Aufgaben
- [x] Projektordner und Architektur anlegen
- [ ] Termin 17.04. vorbereiten → `docs/meeting-17-04-prep.md`
- [ ] Lastenheft-Template für Ulm-Gespräch → `docs/lastenheft-template.md`
- [ ] Claude API Key beschaffen und testen
- [ ] Beispiel-Bauplan beschaffen (idealerweise von Harun's Vater)
- [ ] Ersten Prompt-Test: Bauplan-Analyse manuell in Claude.ai testen
- [ ] Tech-Stack final bestätigen (Auth: Clerk vs. Supabase)
- [ ] Git-Repo erstellen (lokal ✓, GitHub → nach Review)

---

## Sprint 1 (KW 17–18) — Backend + Claude-Integration

**Ziel:** Funktionierender PDF-Upload → Claude-Analyse-Pipeline → JSON-Ergebnis

### Backend
- [ ] FastAPI-App produktionsreif aufsetzen (Docker, Environment)
- [ ] PostgreSQL aufsetzen (lokal + Railway)
- [ ] S3-Bucket konfigurieren (Cloudflare R2 für günstigen Speicher)
- [ ] PDF-Upload-Endpoint implementiert und getestet
- [ ] PDF → Bilder Pipeline (pdf2image)
- [ ] Claude Vision API Call (mit Prompt aus `prompts/bauplan-analyse.md`)
- [ ] JSON-Extraktion und Validierung aus Claude-Antwort
- [ ] Job-Status in DB speichern
- [ ] Basis-Tests (Unit + Integration)

### Deliverable: Sprint 1
Ein Curl-Command `POST /api/v1/bauplan/upload` mit einem echten Bauplan-PDF gibt nach ~2min ein valides JSON-Ergebnis mit Räumen, Wandlängen und Konfidenz zurück.

---

## Sprint 2 (KW 19–20) — Analyse-Engine & Validierung

**Ziel:** Analyse-Qualität auf >90% Konfidenz bringen, Fehler graceful behandeln

### Aufgaben
- [ ] Prompt-Optimierung (basierend auf realen Test-Plänen)
- [ ] Mehrseiter-PDFs: Seiten klassifizieren (Grundriss vs. Rest)
- [ ] Plausibilitäts-Validierung implementieren
- [ ] Fehler-Handling: was passiert bei unlesbarem Plan?
- [ ] Kosten-Tracking pro Analyse (Tokens + Kosten in DB)
- [ ] Retry-Logik für Claude-API-Fehler
- [ ] Benchmark: 10 reale Pläne gegen manuelle Massenermittlung
- [ ] Test-Suite ausbauen (mind. 20 relevante Tests)

### Deliverable: Sprint 2
Analyse von 10 realen Grundrissen mit <5% Abweichung zur manuellen Ermittlung.

---

## Sprint 3 (KW 21–22) — Frontend + MVP Launch

**Ziel:** Nutzbare Web-App für Pilot-Kunde

### Frontend
- [ ] Next.js-Projekt aufsetzen (Clerk Auth, shadcn/ui)
- [ ] Dashboard-Layout (Sidebar, Header)
- [ ] Upload-Page mit Drag & Drop
- [ ] Fortschrittsanzeige (Polling-basiert)
- [ ] Ergebnis-Anzeige (Räume, Wände, Decken in Tabellen)
- [ ] Warnungen sichtbar und erklärend
- [ ] Export: Excel-Download

### MVP-Definition (26.05.)
- Harun's Vater kann PDF-Bauplan hochladen
- Sieht nach <3min ein Ergebnis (Räume, Wandlängen nach Typ)
- Warnungen sind verständlich und handlungsweisend
- Export als Excel funktioniert

---

## Sprint 4 (KW 23–24) — Feedback-Iteration

**Ziel:** Pilot-Feedback einarbeiten, Stabilität verbessern

- [ ] Feedback-Session mit Pilot-Kunde (Screenshare oder vor Ort)
- [ ] Top-3-Probleme beheben
- [ ] Performance-Optimierung (langsame Analysen beschleunigen)
- [ ] Manuelle Korrektur von Analyse-Werten im UI
- [ ] Zweiten Test-Kunden gewinnen (Referenz für Sales)

---

## Sprint 5 (KW 25–26) — Polishing + Säule 2 Vorbereitung

**Ziel:** Vollversion 30.06., Grundlage für Preisvergleich

- [ ] Preislisten-Upload-Struktur (Säule 2 Grundlage)
- [ ] Multi-Projekt-Management
- [ ] Analyse-Historie mit Suche und Filter
- [ ] Onboarding-Flow für neue Nutzer
- [ ] Dokumentation für Pilot-Kunden

---

## Risiken

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| Claude-Analyse ungenau bei schlechten Plänen | Hoch | Hoch | Früh mit echten Plänen testen, Confidence-Threshold |
| Pilot-Kunde lehnt ab | Mittel | Kritisch | Termin 17.04. für Commitment nutzen |
| Sprint-Verzögerung | Mittel | Hoch | Sprint 3 auf 26.05. nicht verschieben — MVP abspecken statt verschieben |
| Claude-API-Kosten höher als erwartet | Niedrig | Mittel | Sonnet-First-Strategie, Cost-Tracking von Anfang an |
