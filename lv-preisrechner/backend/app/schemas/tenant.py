"""Pydantic-Schemas fuer Tenant-Profil + Vertriebs-Workflow (B+4.9)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenantProfileOut(BaseModel):
    """GET /api/v1/tenant/profile."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    company_name: str | None
    company_address_street: str | None
    company_address_zip: str | None
    company_address_city: str | None
    company_address_country: str
    tax_id: str | None
    vat_id: str | None
    bank_iban: str | None
    bank_bic: str | None
    bank_name: str | None
    logo_url: str | None
    default_payment_terms_days: int
    default_offer_validity_days: int
    default_agb_text: str | None
    signature_text: str | None
    use_new_pricing: bool
    stundensatz_eur: float
    bgk_prozent: float
    agk_prozent: float
    wg_prozent: float
    created_at: datetime


class TenantProfileUpdate(BaseModel):
    """PATCH /api/v1/tenant/profile — alle Felder optional.

    Validierungen:
    - country: ISO-2-Code (DE, AT, CH, ...). Strikt 2 Zeichen.
    - bank_iban: 15-34 Zeichen, Whitespace wird vor Validierung gestrippt.
    - bank_bic: 8 oder 11 Zeichen.
    - vat_id: max 20 Zeichen, sonst frei (variable Formate je Land).
    - default_payment_terms_days/default_offer_validity_days: 1..365.
    """

    model_config = ConfigDict(extra="forbid")

    company_name: str | None = Field(None, min_length=1, max_length=200)
    company_address_street: str | None = Field(None, max_length=200)
    company_address_zip: str | None = Field(None, max_length=20)
    company_address_city: str | None = Field(None, max_length=100)
    company_address_country: str | None = Field(None, min_length=2, max_length=2)
    tax_id: str | None = Field(None, max_length=50)
    vat_id: str | None = Field(None, max_length=20)
    bank_iban: str | None = Field(None, max_length=34)
    bank_bic: str | None = Field(None, min_length=8, max_length=11)
    bank_name: str | None = Field(None, max_length=120)
    logo_url: str | None = Field(None, max_length=500)
    default_payment_terms_days: int | None = Field(None, ge=1, le=365)
    default_offer_validity_days: int | None = Field(None, ge=1, le=365)
    default_agb_text: str | None = None
    signature_text: str | None = None


# --------------------------------------------------------------------------- #
# Customer-CRUD
# --------------------------------------------------------------------------- #
class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200)
    contact_person: str | None = Field(None, max_length=200)
    address_street: str | None = Field(None, max_length=200)
    address_zip: str | None = Field(None, max_length=20)
    address_city: str | None = Field(None, max_length=100)
    address_country: str | None = Field(None, min_length=2, max_length=2)
    email: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=50)
    notes: str | None = None


class CustomerUpdate(CustomerCreate):
    """PATCH — alle Felder optional."""

    name: str | None = Field(None, min_length=1, max_length=200)


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    name: str
    contact_person: str | None
    address_street: str | None
    address_zip: str | None
    address_city: str | None
    address_country: str
    email: str | None
    phone: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Project-CRUD
# --------------------------------------------------------------------------- #
class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str
    name: str = Field(..., min_length=1, max_length=300)
    address_street: str | None = Field(None, max_length=200)
    address_zip: str | None = Field(None, max_length=20)
    address_city: str | None = Field(None, max_length=100)
    status: str | None = Field(None, pattern="^(draft|active|completed|cancelled)$")
    notes: str | None = None


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = None
    name: str | None = Field(None, min_length=1, max_length=300)
    address_street: str | None = Field(None, max_length=200)
    address_zip: str | None = Field(None, max_length=20)
    address_city: str | None = Field(None, max_length=100)
    status: str | None = Field(None, pattern="^(draft|active|completed|cancelled)$")
    notes: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    customer_id: str
    name: str
    address_street: str | None
    address_zip: str | None
    address_city: str | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
