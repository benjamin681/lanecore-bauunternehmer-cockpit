"""Pydantic-Schemas für die Pricing-Foundation (B+1)."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PricelistStatusSchema(str, Enum):
    PENDING_PARSE = "PENDING_PARSE"
    PARSING = "PARSING"
    PARSED = "PARSED"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    ARCHIVED = "ARCHIVED"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# SupplierPriceList
# ---------------------------------------------------------------------------
class _DateRangeMixin(BaseModel):
    """Gueltigkeits-Zeitraum-Validierung."""

    @model_validator(mode="after")
    def _check_dates(self):
        vf = getattr(self, "valid_from", None)
        vu = getattr(self, "valid_until", None)
        if vf and vu and vu < vf:
            raise ValueError("valid_until muss >= valid_from sein")
        return self


class SupplierPriceListCreate(_DateRangeMixin):
    """Upload-Request. Datei-Metadaten werden separat als Multipart angenommen."""

    supplier_name: str = Field(..., min_length=1, max_length=200)
    supplier_location: str | None = Field(None, max_length=200)
    list_name: str = Field(..., min_length=1, max_length=200)
    valid_from: date
    valid_until: date | None = None


class SupplierPriceListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    supplier_name: str
    supplier_location: str | None
    list_name: str
    valid_from: date
    valid_until: date | None
    source_file_path: str
    source_file_hash: str
    status: PricelistStatusSchema
    parse_error: str | None
    entries_total: int | None
    entries_reviewed: int | None
    is_active: bool
    uploaded_by_user_id: str
    uploaded_at: datetime
    approved_by_user_id: str | None
    approved_at: datetime | None


# ---------------------------------------------------------------------------
# SupplierPriceEntry
# ---------------------------------------------------------------------------
class SupplierPriceEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pricelist_id: str
    tenant_id: str
    article_number: str | None
    manufacturer: str | None
    product_name: str
    category: str | None
    subcategory: str | None
    price_net: float
    currency: str
    unit: str
    package_size: float | None
    package_unit: str | None
    pieces_per_package: int | None
    effective_unit: str
    price_per_effective_unit: float
    attributes: dict[str, Any]
    source_page: int | None
    parser_confidence: float
    needs_review: bool
    reviewed_by_user_id: str | None = None
    reviewed_at: datetime | None = None
    correction_applied: bool = False


class SupplierPriceEntryUpdate(BaseModel):
    """Partial-Update fuer einen Entry. Alle Felder optional.

    Der Server erkennt Aenderungen, setzt correction_applied=True und
    markiert den Reviewer. Wenn needs_review von True auf False wechselt,
    wird der entries_reviewed-Counter auf der Parent-Pricelist
    inkrementiert (umgekehrt dekrementiert).
    """

    model_config = ConfigDict(extra="forbid")

    article_number: str | None = Field(None, max_length=100)
    manufacturer: str | None = Field(None, max_length=200)
    product_name: str | None = Field(None, min_length=1, max_length=500)
    category: str | None = Field(None, max_length=200)
    subcategory: str | None = Field(None, max_length=200)
    price_net: float | None = Field(None, gt=0)
    unit: str | None = Field(None, min_length=1, max_length=50)
    effective_unit: str | None = Field(None, min_length=1, max_length=50)
    price_per_effective_unit: float | None = Field(None, gt=0)
    package_size: float | None = Field(None, gt=0)
    package_unit: str | None = Field(None, max_length=50)
    pieces_per_package: int | None = Field(None, gt=0)
    attributes: dict[str, Any] | None = None
    needs_review: bool | None = None


class SupplierPriceListDetail(SupplierPriceListOut):
    entries: list[SupplierPriceEntryOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# TenantPriceOverride
# ---------------------------------------------------------------------------
class TenantPriceOverrideCreate(_DateRangeMixin):
    article_number: str = Field(..., min_length=1, max_length=100)
    manufacturer: str | None = Field(None, max_length=200)
    override_price: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=50)
    valid_from: date
    valid_until: date | None = None
    notes: str | None = None


class TenantPriceOverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    article_number: str
    manufacturer: str | None
    override_price: float
    unit: str
    valid_from: date
    valid_until: date | None
    notes: str | None
    created_by_user_id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# TenantDiscountRule
# ---------------------------------------------------------------------------
class TenantDiscountRuleCreate(_DateRangeMixin):
    supplier_name: str = Field(..., min_length=1, max_length=200)
    discount_percent: float = Field(..., ge=0, le=100)
    category: str | None = Field(None, max_length=200)
    valid_from: date
    valid_until: date | None = None
    notes: str | None = None


class TenantDiscountRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    supplier_name: str
    discount_percent: float
    category: str | None
    valid_from: date
    valid_until: date | None
    notes: str | None
    created_by_user_id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# ProductCorrection / Review-Workflow (B+4.4 P4)
# ---------------------------------------------------------------------------
class ProductCorrectionTypeSchema(str, Enum):
    PIECES_PER_PACKAGE = "pieces_per_package"
    UNIT_OVERRIDE = "unit_override"
    PRICE_PER_EFFECTIVE_UNIT = "price_per_effective_unit"
    CONFIRMED_AS_IS = "confirmed_as_is"


class EntryReviewItem(BaseModel):
    """Ein einzelner Review-Eintrag mit allem Kontext fuers UI."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    pricelist_id: str
    article_number: str | None
    manufacturer: str | None
    product_name: str
    price_net: float
    currency: str
    unit: str
    package_size: float | None
    pieces_per_package: int | None
    effective_unit: str
    price_per_effective_unit: float
    source_page: int | None
    source_row_raw: str | None
    review_reason: str | None
    attributes: dict[str, Any]
    parser_confidence: float


class EntryReviewGroup(BaseModel):
    """Gruppe von Review-Eintraegen mit identischem review_reason."""

    review_reason: str
    count: int
    items: list[EntryReviewItem]


class EntryReviewResponse(BaseModel):
    """Top-Level-Antwort von GET /pricing/entries/{pricelist_id}/review."""

    pricelist_id: str
    total_needs_review: int
    groups: list[EntryReviewGroup]


class EntryCorrectionRequest(BaseModel):
    """POST /pricing/entries/{entry_id}/correct.

    corrected_value ist typ-abhaengig — Validierung im Service-Layer:
    - PIECES_PER_PACKAGE: {"pieces_per_package": int > 0}
    - UNIT_OVERRIDE: {"unit": str, "package_size": float | null,
                       "effective_unit": str | null}
    - PRICE_PER_EFFECTIVE_UNIT: {"price_per_effective_unit": float > 0,
                                  "effective_unit": str | null}
    - CONFIRMED_AS_IS: {} (leerer Dict reicht; setzt nur Flags)
    """

    model_config = ConfigDict(extra="forbid")

    correction_type: ProductCorrectionTypeSchema
    corrected_value: dict[str, Any] = Field(default_factory=dict)
    persist: bool = Field(
        default=True,
        description=(
            "Wenn true, wird die Korrektur in lvp_product_corrections "
            "gespeichert und beim naechsten Upload automatisch angewendet."
        ),
    )


class EntryCorrectionResponse(BaseModel):
    """Antwort nach angewandter Korrektur."""

    entry: SupplierPriceEntryOut
    correction_persisted: bool
    correction_id: str | None = None
