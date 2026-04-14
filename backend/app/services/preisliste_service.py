"""Preislisten-Import — Verarbeitung von Preis-PDFs via Claude Vision."""

import json
import re
from uuid import UUID

import anthropic
import structlog

from app.core.config import settings
from app.core.database import AsyncSessionLocal as async_session_factory
from app.models.preisliste import Preisliste, Produkt
from app.services.pdf_service import validate_pdf, pdf_to_images

log = structlog.get_logger()

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

                # Convert PDF to images
                pdf_info = validate_pdf(pdf_bytes)
                page_images = pdf_to_images(pdf_bytes)
                images = [pi.base64 for pi in page_images[:20]]

                all_produkte = []

                for page_num, img_b64 in enumerate(images, 1):
                    log.info("extracting_preisliste_page", page=page_num, total=len(images), anbieter=anbieter)

                    response = await self.client.messages.create(
                        model="claude-sonnet-4-20250514",  # Sonnet reicht für strukturierte Tabellen
                        max_tokens=8000,
                        messages=[{
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": img_b64,
                                    },
                                },
                                {"type": "text", "text": PREISLISTE_EXTRACT_PROMPT},
                            ],
                        }],
                    )

                    # Parse JSON from response
                    text = response.content[0].text
                    json_match = re.search(r"\[.*\]", text, re.DOTALL)
                    if json_match:
                        page_produkte = json.loads(json_match.group())
                        all_produkte.extend(page_produkte)

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
                log.error("preisliste_import_failed", error=str(e), preisliste_id=str(preisliste_id))
                await db.rollback()
                result = await db.execute(
                    select(Preisliste).where(Preisliste.id == preisliste_id)
                )
                preisliste = result.scalar_one()
                preisliste.status = "failed"
                preisliste.error_message = str(e)[:500]
                await db.commit()

    async def preisvergleich(
        self, bezeichnung: str, kategorie: str | None = None
    ) -> list[dict]:
        """Findet das günstigste Produkt über alle Anbieter."""
        async with async_session_factory() as db:
            from sqlalchemy import select

            query = select(Produkt).join(Preisliste).where(
                Preisliste.status == "completed",
                Produkt.verfuegbar == True,
            )

            # Fuzzy-Suche: ILIKE auf Bezeichnung
            search_terms = bezeichnung.split()
            for term in search_terms:
                query = query.where(Produkt.bezeichnung.ilike(f"%{term}%"))

            if kategorie:
                query = query.where(Produkt.kategorie == kategorie)

            query = query.order_by(Produkt.preis_netto.asc())

            result = await db.execute(query)
            produkte = result.scalars().all()

            results = []
            guenstigster_preis = None

            for p in produkte:
                preis = float(p.preis_netto)
                if guenstigster_preis is None:
                    guenstigster_preis = preis

                results.append({
                    "anbieter": p.preisliste.anbieter if p.preisliste else "Unbekannt",
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
                    "ist_guenstigster": preis == guenstigster_preis,
                })

            return results
