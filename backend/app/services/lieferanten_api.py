"""Lieferanten-API Integration — direct price queries from suppliers.

Supports both PDF upload (existing) and direct API queries (new).
Each supplier gets an adapter class.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ProduktAngebot:
    """A product offer from a supplier."""
    artikel_nr: str
    bezeichnung: str
    hersteller: str
    einheit: str
    preis_netto: Decimal
    verfuegbar: bool
    lieferzeit_tage: int | None = None
    mindestmenge: int | None = None
    staffelpreise: list[dict] | None = None  # [{"ab_menge": 100, "preis": 1.20}]


class LieferantAdapter(ABC):
    """Base class for supplier API adapters."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def suche_produkt(self, suchbegriff: str, kategorie: str | None = None) -> list[ProduktAngebot]: ...

    @abstractmethod
    async def preis_abfrage(self, artikel_nr: str, menge: int = 1) -> ProduktAngebot | None: ...

    @abstractmethod
    async def verfuegbarkeit(self, artikel_nrs: list[str]) -> dict[str, bool]: ...


class KEMLERAdapter(LieferantAdapter):
    """KEMLER Baustoffe API adapter (placeholder — needs real API endpoint)."""

    @property
    def name(self) -> str:
        return "KEMLER Baustoffe"

    def __init__(self, api_url: str = "", api_key: str = ""):
        self.api_url = api_url
        self.api_key = api_key

    async def suche_produkt(self, suchbegriff: str, kategorie: str | None = None) -> list[ProduktAngebot]:
        # TODO: Implement when KEMLER provides API access
        # For now, fall back to PDF-imported data
        return []

    async def preis_abfrage(self, artikel_nr: str, menge: int = 1) -> ProduktAngebot | None:
        return None

    async def verfuegbarkeit(self, artikel_nrs: list[str]) -> dict[str, bool]:
        return {}


class ManuellerLieferant(LieferantAdapter):
    """Adapter that queries the local Preislisten database (from PDF uploads)."""

    @property
    def name(self) -> str:
        return "PDF-Import"

    def __init__(self, db_session):
        self.db = db_session

    async def suche_produkt(self, suchbegriff: str, kategorie: str | None = None) -> list[ProduktAngebot]:
        from sqlalchemy import select
        from app.models.preisliste import Produkt, Preisliste

        query = (
            select(Produkt, Preisliste.anbieter)
            .join(Preisliste)
            .where(Preisliste.status == "completed")
            .where(Produkt.verfuegbar == True)
            .where(Produkt.bezeichnung.ilike(f"%{suchbegriff}%"))
            .order_by(Produkt.preis_netto.asc())
            .limit(20)
        )
        result = await self.db.execute(query)

        return [
            ProduktAngebot(
                artikel_nr=p.artikel_nr or "",
                bezeichnung=p.bezeichnung,
                hersteller=p.hersteller or anbieter,
                einheit=p.einheit or "Stk",
                preis_netto=Decimal(str(p.preis_netto)),
                verfuegbar=True,
            )
            for p, anbieter in result.all()
        ]

    async def preis_abfrage(self, artikel_nr: str, menge: int = 1) -> ProduktAngebot | None:
        return None

    async def verfuegbarkeit(self, artikel_nrs: list[str]) -> dict[str, bool]:
        return {}


# Registry of all available supplier adapters
LIEFERANTEN_REGISTRY: dict[str, type[LieferantAdapter]] = {
    "kemler": KEMLERAdapter,
    "pdf": ManuellerLieferant,
}
