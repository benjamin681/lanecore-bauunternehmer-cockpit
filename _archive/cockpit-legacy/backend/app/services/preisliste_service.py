"""Preislisten-Import — Verarbeitung von Preis-PDFs via Claude Vision."""

import json
import re
from uuid import UUID

import anthropic
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.database import AsyncSessionLocal as async_session_factory
from app.models.preisliste import Preisliste, Produkt
from app.services.pdf_service import validate_pdf, pdf_to_images

log = structlog.get_logger()


@retry(
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APITimeoutError, anthropic.APIConnectionError)),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(3),
    before_sleep=lambda rs: log.warning("preisliste_claude_retry", attempt=rs.attempt_number),
)
async def _call_claude_for_preisliste(client: anthropic.AsyncAnthropic, **kwargs) -> anthropic.types.Message:
    """Claude call with retry on rate-limit/timeout/connection errors."""
    return await client.messages.create(**kwargs)

PREISLISTE_EXTRACT_PROMPT = """Du bist ein Experte für Baustoff-Preislisten. Analysiere dieses PDF-Bild einer Preisliste und extrahiere ALLE Produkte.

Für jedes Produkt extrahiere:
- artikel_nr: Artikelnummer (falls vorhanden)
- bezeichnung: Vollständige Produktbezeichnung
- hersteller: Hersteller (falls erkennbar)
- kategorie: Eine der folgenden Kategorien:
  - "CW-Profil" (Ständerwerk)
  - "UW-Profil" (Boden-/Deckenanschluss)
  - "CD-Profil" (Deckenunterkonstruktion)
  - "UD-Profil" (Randprofil Decke)
  - "GK-Platte" (Gipskarton)
  - "GKF-Platte" (Gipskarton Feuerschutz)
  - "GKFi-Platte" (Gipskarton Feuerschutz imprägniert)
  - "Daemmung" (Mineralwolle, Steinwolle etc.)
  - "Befestigung" (Schrauben, Dübel, Klammern)
  - "Spachtel" (Spachtelmasse, Fugenspachtel)
  - "Band" (Fugenband, Bewehrungsstreifen)
  - "Zubehoer" (Direktabhänger, Noniusabhänger, etc.)
  - "Akustik" (Akustikplatten, Lochplatten)
  - "Sonstiges"
- einheit: Verkaufseinheit (Stk, m, m², Pkg, Bund, Palette, etc.)
- preis_netto: Netto-Preis in EUR (nur Zahl, kein €-Zeichen)
- preis_brutto: Brutto-Preis falls angegeben
- menge_pro_einheit: Bei Paketen/Bündeln die enthaltene Menge (z.B. Paket à 10 Platten → 10)

WICHTIG:
- Extrahiere NUR Trockenbau-relevante Produkte
- Ignoriere Versandkosten, Rabatthinweise, AGBs
- Bei unklaren Preisen: den niedrigsten (vermutlich Nettopreis) als preis_netto
- Alle Preise in EUR

Antwort als JSON-Array:
```json
[
  {
    "artikel_nr": "12345",
    "bezeichnung": "Knauf CW 75 x 0,6 x 2750",
    "hersteller": "Knauf",
    "kategorie": "CW-Profil",
    "einheit": "Stk",
    "preis_netto": 3.45,
    "preis_brutto": 4.11,
    "menge_pro_einheit": null
  }
]
```"""


class PreislisteService:
    """Service für Preislisten-Import und Preisvergleich."""

    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=120.0,
        )

    async def process_preisliste_pdf(
        self, preisliste_id: UUID, pdf_bytes: bytes, anbieter: str
    ) -> None:
        """Verarbeitet eine Preislisten-PDF und extrahiert Produkte."""
        async with async_session_factory() as db:
            try:
                # Update status
                from sqlalchemy import select
                result = await db.execute(
                    select(Preisliste).where(Preisliste.id == preisliste_id)
                )
                preisliste = result.scalar_one()
                preisliste.status = "processing"
                await db.commit()

                # Save PDF to disk for retry capability
                import os
                pdf_dir = f"/tmp/lanecore-uploads/preislisten/{preisliste_id}"
                os.makedirs(pdf_dir, exist_ok=True)
                pdf_path = os.path.join(pdf_dir, preisliste.dateiname or "preisliste.pdf")
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)

                # Convert PDF to images
                pdf_info = validate_pdf(pdf_bytes)
                page_images = pdf_to_images(pdf_bytes)
                images_with_mime = [(pi.image_base64, pi.media_type) for pi in page_images[:20]]

                all_produkte = []

                for page_num, (img_b64, mime) in enumerate(images_with_mime, 1):
                    log.info("extracting_preisliste_page", page=page_num, total=len(images_with_mime), anbieter=anbieter)

                    try:
                        response = await _call_claude_for_preisliste(
                            self.client,
                            model=settings.claude_model_simple,
                            max_tokens=8000,
                            messages=[{
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": mime,
                                            "data": img_b64,
                                        },
                                    },
                                    {"type": "text", "text": PREISLISTE_EXTRACT_PROMPT},
                                ],
                            }],
                        )
                    except (anthropic.APIError, anthropic.APIStatusError) as api_err:
                        # After retries exhausted — skip this page but continue with others
                        log.error("preisliste_page_failed_permanently",
                                  page=page_num, error=str(api_err))
                        continue

                    # Parse JSON from response (robust)
                    try:
                        text = response.content[0].text
                        json_match = re.search(r"\[.*\]", text, re.DOTALL)
                        if json_match:
                            page_produkte = json.loads(json_match.group())
                            if isinstance(page_produkte, list):
                                all_produkte.extend(page_produkte)
                    except (json.JSONDecodeError, IndexError, AttributeError) as parse_err:
                        log.warning("preisliste_page_parse_failed",
                                    page=page_num, error=str(parse_err))
                        continue

                # Save products to DB
                for p_data in all_produkte:
                    produkt = Produkt(
                        preisliste_id=preisliste_id,
                        artikel_nr=p_data.get("artikel_nr"),
                        bezeichnung=p_data["bezeichnung"],
                        hersteller=p_data.get("hersteller") or anbieter,
                        kategorie=p_data.get("kategorie", "Sonstiges"),
                        einheit=p_data.get("einheit", "Stk"),
                        preis_netto=float(p_data.get("preis_netto", 0)),
                        preis_brutto=float(p_data["preis_brutto"]) if p_data.get("preis_brutto") else None,
                        menge_pro_einheit=float(p_data["menge_pro_einheit"]) if p_data.get("menge_pro_einheit") else None,
                        raw_text=json.dumps(p_data, ensure_ascii=False),
                    )
                    db.add(produkt)

                preisliste.status = "completed"
                preisliste.produkt_count = len(all_produkte)
                await db.commit()

                log.info("preisliste_import_complete",
                         preisliste_id=str(preisliste_id),
                         anbieter=anbieter,
                         produkte=len(all_produkte))

            except Exception as e:
                log.exception("preisliste_import_failed", preisliste_id=str(preisliste_id))
                try:
                    await db.rollback()
                except Exception:
                    pass
                # Use a FRESH session to mark as failed — previous one may be dirty
                try:
                    async with async_session_factory() as fresh_db:
                        from sqlalchemy import select as _select
                        r = await fresh_db.execute(
                            _select(Preisliste).where(Preisliste.id == preisliste_id)
                        )
                        pl = r.scalar_one_or_none()
                        if pl is not None:
                            pl.status = "failed"
                            # Column name may be `error_message` or `fehler` depending on model
                            err_txt = str(e)[:500]
                            if hasattr(pl, "error_message"):
                                pl.error_message = err_txt
                            if hasattr(pl, "fehler"):
                                pl.fehler = err_txt
                            await fresh_db.commit()
                except Exception:
                    log.exception("preisliste_failed_status_update_failed",
                                  preisliste_id=str(preisliste_id))

    async def preisvergleich(
        self, bezeichnung: str, kategorie: str | None = None, einheit: str | None = None,
    ) -> list[dict]:
        """Findet das günstigste Produkt über alle Anbieter.

        Matching-Strategie (in Reihenfolge):
        1. Kategorie-Filter (exakt, wenn gegeben) — reduziert Treffer drastisch
        2. Stopwords entfernen (Generika wie "Platte", "Profil")
        3. Mindestens 2 Terme müssen im Namen vorkommen (AND-Logik bei >=2 Termen)
        4. Einheiten-Normalisierung (lfm=m=Meter, Stk=Stueck=St)
        5. Sortierung nach Preis (pro Einheit normalisiert)
        """
        async with async_session_factory() as db:
            from sqlalchemy import select, or_

            query = select(Produkt, Preisliste.anbieter).join(Preisliste).where(
                Preisliste.status == "completed",
                Produkt.verfuegbar == True,
            )

            # Normalize input
            STOPWORDS = {"platte", "profil", "der", "die", "das", "und", "mit", "fuer",
                         "für", "von", "zu", "indoor", "standard", "system"}
            raw_terms = [t.strip().lower() for t in bezeichnung.replace(",", " ").split() if len(t.strip()) >= 2]
            # Keep strong discriminators (e.g., "CW", "75", "GKF", "Aquapanel")
            strong_terms = [t for t in raw_terms if t not in STOPWORDS]
            # Mindestens 1 Term behalten
            if not strong_terms and raw_terms:
                strong_terms = raw_terms[:2]

            if strong_terms:
                if len(strong_terms) >= 2:
                    # AND: mindestens 2 Terme müssen matchen
                    # Aber wir relaxen: erster Term MUSS, zweiter Term SOLL
                    query = query.where(Produkt.bezeichnung.ilike(f"%{strong_terms[0]}%"))
                    # Bei 2+ Termen: verlange, dass auch ein weiterer Term matched
                    rest_conds = [Produkt.bezeichnung.ilike(f"%{t}%") for t in strong_terms[1:]]
                    if rest_conds:
                        query = query.where(or_(*rest_conds))
                else:
                    query = query.where(Produkt.bezeichnung.ilike(f"%{strong_terms[0]}%"))

            if kategorie:
                query = query.where(Produkt.kategorie == kategorie)

            # Einheit-Filter (normalisiert)
            UNIT_ALIASES = {
                "lfm": ["lfm", "m", "meter", "laufmeter", "lfd.m"],
                "m²": ["m²", "m2", "qm", "quadratmeter"],
                "stk": ["stk", "st", "stueck", "stück", "pcs"],
                "kg": ["kg", "kilogramm"],
            }
            if einheit:
                ein_lower = einheit.lower()
                aliases = None
                for key, alist in UNIT_ALIASES.items():
                    if ein_lower in alist:
                        aliases = alist
                        break
                if aliases:
                    query = query.where(
                        or_(*[Produkt.einheit.ilike(a) for a in aliases])
                    )

            query = query.order_by(Produkt.preis_netto.asc()).limit(50)

            result = await db.execute(query)
            rows = result.all()

            results = []
            guenstigster_preis = None

            for p, anbieter_name in rows:
                preis = float(p.preis_netto) if p.preis_netto else 0.0
                if guenstigster_preis is None and preis > 0:
                    guenstigster_preis = preis

                # Match-Qualität bewerten (wie viele starke Terme matchen)
                bez_lower = (p.bezeichnung or "").lower()
                match_score = sum(1 for t in strong_terms if t in bez_lower)
                match_quality = "high" if match_score >= len(strong_terms) else (
                    "medium" if match_score >= max(1, len(strong_terms) // 2) else "low"
                )

                results.append({
                    "anbieter": anbieter_name or "Unbekannt",
                    "match_quality": match_quality,
                    "match_score": match_score,
                    "produkt": {
                        "id": str(p.id),
                        "artikel_nr": p.artikel_nr,
                        "bezeichnung": p.bezeichnung,
                        "hersteller": p.hersteller,
                        "kategorie": p.kategorie,
                        "einheit": p.einheit,
                        "preis_netto": preis,
                        "preis_brutto": float(p.preis_brutto) if p.preis_brutto else None,
                        "menge_pro_einheit": float(p.menge_pro_einheit) if p.menge_pro_einheit else None,
                        "verfuegbar": p.verfuegbar,
                    },
                    "ist_guenstigster": preis == guenstigster_preis and preis > 0,
                })

            return results
