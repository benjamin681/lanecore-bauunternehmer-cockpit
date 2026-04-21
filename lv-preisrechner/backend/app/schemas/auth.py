"""Auth-Schemas."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    firma: str = Field(min_length=1, max_length=200)
    vorname: str = ""
    nachname: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    firma: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    vorname: str
    nachname: str
    tenant_id: str
    firma: str
    stundensatz_eur: float
    bgk_prozent: float
    agk_prozent: float
    wg_prozent: float
    # B+4.3.1: Neue Preis-Engine (Lookup ueber SupplierPriceList/Overrides)
    use_new_pricing: bool = False


class TenantUpdate(BaseModel):
    """Patch Kalkulations-Defaults des Betriebs."""

    firma: str | None = Field(default=None, max_length=200)
    stundensatz_eur: float | None = Field(default=None, ge=0, le=500)
    bgk_prozent: float | None = Field(default=None, ge=0, le=100)
    agk_prozent: float | None = Field(default=None, ge=0, le=100)
    wg_prozent: float | None = Field(default=None, ge=0, le=100)
    # B+4.3.1: explizites Setzen (None = nicht aendern)
    use_new_pricing: bool | None = None
