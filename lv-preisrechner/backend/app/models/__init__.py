"""SQLAlchemy Models."""

from app.models.aufmass import Aufmass, AufmassPosition, AufmassStatus
from app.models.customer import Customer, Project, ProjectStatus
from app.models.job import Job
from app.models.lv import LV
from app.models.offer import (
    Offer,
    OfferPdfFormat,
    OfferStatus,
    OfferStatusChange,
)
from app.models.position import Position
from app.models.price_entry import PriceEntry
from app.models.price_list import PriceList
from app.models.pricing import (
    PricelistStatus,
    SupplierPriceEntry,
    SupplierPriceList,
    TenantDiscountRule,
    TenantPriceOverride,
)
from app.models.tenant import Tenant
from app.models.user import User

__all__ = [
    "User",
    "Tenant",
    "PriceList",
    "PriceEntry",
    "LV",
    "Position",
    "Job",
    # Neue Pricing-Architektur (B+1, Parallel zum alten Modell)
    "SupplierPriceList",
    "SupplierPriceEntry",
    "TenantPriceOverride",
    "TenantDiscountRule",
    "PricelistStatus",
    # B+4.9 Vertriebs-Workflow
    "Customer",
    "Project",
    "ProjectStatus",
    # B+4.11 Offer-Lifecycle
    "Offer",
    "OfferStatus",
    "OfferStatusChange",
    "OfferPdfFormat",
    # B+4.12 Aufmaß
    "Aufmass",
    "AufmassPosition",
    "AufmassStatus",
]
