# Projekt-Plan — LaneCore AI
## Offene Punkte & Prioritäten

**Erstellt:** 14.04.2026
**MVP:** 26.05.2026 | **Vollversion:** 30.06.2026
**Nächster Termin:** 17.04.2026 — Ulm (Harun's Vater)

---

## KRITISCHER PFAD (Was blockiert alles andere)

```
Termin 17.04. → Beispiel-Baupläne erhalten
       ↓
Prompt-Test mit echten Plänen (diese Woche)
       ↓
Sprint 1: Backend-Grundstruktur (ab 21.04.)
       ↓
Sprint 2: Analyse-Engine auf >90% Genauigkeit (ab 05.05.)
       ↓
Sprint 3: Frontend + MVP-Launch (bis 26.05.)
```

---

## Diese Woche (KW 16, bis 18.04.)

| Priorität | Aufgabe | Deadline | Status |
|-----------|---------|----------|--------|
| 🔴 KRITISCH | Termin 17.04. vorbereiten + Lastenheft mitnehmen | 17.04. | Bereit |
| 🔴 KRITISCH | Beispiel-Bauplan für Demo beschaffen | 16.04. | Offen |
| 🔴 KRITISCH | Claude API Key beschaffen (Anthropic Console) | 16.04. | Offen |
| 🟡 HOCH | Ersten Bauplan-Prompt in Claude.ai testen | 18.04. | Offen |
| 🟡 HOCH | Railway-Account erstellen + PostgreSQL aufsetzen | 18.04. | Offen |
| 🟡 HOCH | Cloudflare R2 Bucket erstellen | 18.04. | Offen |
| 🟢 MITTEL | Clerk-Account erstellen | 18.04. | Offen |
| 🟢 MITTEL | GitHub Repo erstellen (nach lokalem Init) | 18.04. | Offen |

---

## Sprint 1 (KW 17–18, 21.04.–02.05.)

| Priorität | Aufgabe | Wer | Status |
|-----------|---------|-----|--------|
| 🔴 | FastAPI-App mit Docker-Compose (lokal) | Dev | Offen |
| 🔴 | PDF-Upload-Endpoint + S3-Verbindung | Dev | Offen |
| 🔴 | PDF → Bilder Pipeline (pdf2image) | Dev | Offen |
| 🔴 | Claude Vision API Call implementieren | Dev | Offen |
| 🔴 | Job-Status in PostgreSQL speichern | Dev | Offen |
| 🟡 | BackgroundTask für Analyse-Pipeline | Dev | Offen |
| 🟡 | Basis-Tests (Upload, Validierung) | Dev | Offen |
| 🟡 | Railway-Deployment des Backends | Dev | Offen |

**Sprint-1-Ziel:** `curl -F "file=@grundriss.pdf" https://api.lanecore.ai/api/v1/bauplan/upload` gibt `{"job_id": "...", "status": "pending"}` zurück, und nach 2min ist das Ergebnis in `/result` verfügbar.

---

## Sprint 2 (KW 19–20, 05.–16.05.)

| Priorität | Aufgabe | Wer | Status |
|-----------|---------|-----|--------|
| 🔴 | Prompt-Optimierung mit 5+ echten Plänen | Dev | Offen |
| 🔴 | Mehrseiter-PDFs: Grundriss-Erkennung | Dev | Offen |
| 🔴 | Plausibilitäts-Validierung | Dev | Offen |
| 🔴 | Benchmark: 10 Pläne vs. Manuelle Ermittlung | Dev+Harun | Offen |
| 🟡 | Kosten-Tracking (Tokens, €/Analyse) | Dev | Offen |
| 🟡 | Retry-Logik + Timeout-Handling | Dev | Offen |
| 🟢 | Test-Suite ausbauen (20+ Tests) | Dev | Offen |

---

## Sprint 3 (KW 21–22, 19.–26.05.) — MVP

| Priorität | Aufgabe | Wer | Status |
|-----------|---------|-----|--------|
| 🔴 | Next.js-App aufsetzen (Clerk, shadcn) | Dev | Offen |
| 🔴 | Dashboard-Layout | Dev | Offen |
| 🔴 | Upload-Page (Drag & Drop) | Dev | Offen |
| 🔴 | Analyse-Status Polling + Fortschrittsanzeige | Dev | Offen |
| 🔴 | Ergebnis-Anzeige (Räume, Wände, Decken) | Dev | Offen |
| 🔴 | Warnungen sichtbar und erklärend | Dev | Offen |
| 🔴 | Excel-Export | Dev | Offen |
| 🔴 | Vercel-Deployment | Dev | Offen |
| 🟡 | Projekt-Management (erstellen, benennen) | Dev | Offen |
| 🟡 | Nutzertest mit Harun's Vater | Ben+Harun | Offen |

---

## Offene Entscheidungen (treffen bis Datum)

| Entscheidung | Option A | Option B | Deadline |
|-------------|----------|----------|----------|
| Auth | Clerk (einfacher) | Supabase Auth (günstiger) | 18.04. |
| Job-Queue | FastAPI BackgroundTasks (MVP) | Celery+Redis (robuster) | 21.04. |
| Storage | Cloudflare R2 (günstig) | AWS S3 (Standard) | 18.04. |
| Preismodell | €500/Monat Flat | Usage-Based | Nach Termin 17.04. |

**Empfehlung:** Clerk + BackgroundTasks + R2 für MVP — einfachste Stack, schnellste Launch

---

## Risiken & Mitigationen

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Claude-Analyse zu ungenau | Mittel | Konfidenz-Schwellwert, manuelle Korrektur-Option |
| Termin 17.04. ohne Commitment | Niedrig | ROI-Rechnung vorbereiten, Demo live zeigen |
| Sprint-Verzögerung | Mittel | MVP-Scope reduzieren: erst Tabellen-Anzeige, kein Export |
| API-Kosten übersteigen Erwartungen | Niedrig | Cost-Tracking ab Tag 1, Sonnet-First-Strategie |
| Baupläne nicht für Tests verfügbar | Niedrig | DIN-Standard-Pläne aus Architektur-Lehrmaterial |

---

## Nächste Meilensteine

```
17.04. → Ulm-Termin, Lastenheft-Gespräch, Pläne erhalten
18.04. → Prompt-Test mit erstem echten Plan
21.04. → Sprint 1 Start
02.05. → Sprint 1 Abschluss: API-Endpunkt funktionsfähig
05.05. → Sprint 2 Start
~07.05. → Demo-Termin mit Harun's Vater (Prototyp)
16.05. → Sprint 2 Abschluss: Analyse-Engine validiert
26.05. → 🎯 MVP LIVE — Pilot-Start
30.06. → 🎯 Vollversion 1.0
```

---

## Backlog (nach MVP)

- [ ] Manuelle Wert-Korrektur im UI
- [ ] Zweiter Test-Kunde gewinnen (Referenz für Sales)
- [ ] Preislisten-Import (Säule 2)
- [ ] Angebots-Generator (Säule 3)
- [ ] Multi-User (Rollen: Inhaber / Bürokraft)
- [ ] Analyse-Geschichte mit Vergleich (vorher/nachher manuell)
- [ ] GAEB-Export (für öffentliche Ausschreibungen)
- [ ] Onboarding-Flow für Self-Service-Anmeldung

---

*Dieser Plan wird wöchentlich aktualisiert. Letzter Stand: 14.04.2026*
