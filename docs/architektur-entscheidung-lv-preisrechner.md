# ADR-006: LV-Preisrechner als separates Projekt

**Datum:** 17.04.2026
**Status:** Entschieden — umgesetzt
**Entscheider:** Ben + Claude (3-Agenten-Evaluation)

---

## Kontext

Nach dem Kundengespräch vom 17.04.2026 ist klar: Harun's Vater braucht **jetzt** einen LV-Preisrechner. Sein Problem ist nicht die Bauplan-Analyse (Säule 1), sondern das manuelle Ausfüllen von LVs mit seinen Einkaufspreisen.

Zwei Optionen wurden evaluiert:

---

## Option A: Separates, schlankes Projekt (gewählt)
- Eigenständiges Repository / Verzeichnis
- FastAPI Backend + Streamlit (MVP) oder minimales Next.js Frontend
- SQLite (kein PostgreSQL-Overhead)
- Kein Auth für MVP (nur für Harun's Vater)
- **Time-to-Revenue: ~1 Woche**

## Option B: Integration ins bestehende Cockpit
- LV-Preisrechner als neue Säule im Cockpit-Monorepo
- Nutzung der bestehenden Auth/DB/Infrastruktur
- **Time-to-Revenue: ~4 Wochen** (wegen Cockpit-Komplexität)

---

## Entscheidung: Option A

### Begründung

**3-Agenten-Evaluation (Architektur, Pragmatik, Domäne) — einstimmig für Option A:**

1. **Time-to-Revenue:** 1 Woche vs. 4 Wochen ist entscheidend für Pilot-Erfolg und Early-Adopter-Preis (99€/Monat für 12 Monate)

2. **Risiko-Isolation:** Das Cockpit ist noch in aktiver Entwicklung und instabil. Ein separates Projekt verhindert gegenseitige Blocking.

3. **Scope-Disziplin:** LV-Preisrechner ist ein klar abgegrenztes Problem. Integration verführt zu Feature-Creep und unnötiger Abhängigkeit.

4. **Kundenfeedback zuerst:** Wenn der PoC nicht funktioniert wie erhofft, ist der Verlust minimal. Bei Cockpit-Integration wäre der Aufwand viel höher.

5. **Spätere Integration möglich:** Der LV-Preisrechner kann als Microservice ins Cockpit integriert werden, wenn er sich bewährt hat.

---

## Tech-Stack Entscheidungen

| Komponente | Entscheidung | Begründung |
|------------|-------------|------------|
| Backend | FastAPI (Python 3.12) | Gleiche Patterns wie Cockpit, beste PDF-Libs |
| PDF-Parsing | pdfplumber + Claude Vision | pdfplumber für Text, Claude für Layout |
| PDF-Ausfüllung | PyMuPDF (fitz) | PoC bestätigt: funktioniert sauber |
| LLM | Claude Sonnet → Opus Fallback | Cost-optimiert wie im Cockpit |
| Frontend MVP | Streamlit | Schnellster Weg, kein JS nötig |
| Frontend v2 | Next.js (aus Cockpit übernehmen) | Wenn Pilot erfolgreich |
| Datenbank | SQLite | Kein Overhead, ein User, MVP |
| Auth | Kein Auth im MVP | Nur ein Nutzer (Harun's Vater) |
| Deployment | Lokal oder einfaches VPS | Kein K8s für MVP |

---

## Spätere Integration ins Cockpit

Wenn der LV-Preisrechner sich im Pilotbetrieb bewährt:

```
Cockpit (Next.js)
    └── LV-Preisrechner (FastAPI Microservice)
            ├── /api/v1/lv/upload
            ├── /api/v1/lv/{id}/kalkulation
            └── /api/v1/lv/{id}/export
```

Die Preislisten-Daten (`knowledge/`) können direkt übernommen werden.
Auth kann über Clerk (wie im Cockpit) nachgerüstet werden.

---

## Konsequenzen

- Separates Verzeichnis `lv-preisrechner/` im Monorepo oder eigenes Repo
- Kemmler-Preislisten werden in `knowledge/` im Haupt-Repo versioniert
- Dokumentation bleibt in `docs/` des Haupt-Repos
- Nach erfolgreichem Pilot: Entscheidung Microservice vs. Monolith-Integration
