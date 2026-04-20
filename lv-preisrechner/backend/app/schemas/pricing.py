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
