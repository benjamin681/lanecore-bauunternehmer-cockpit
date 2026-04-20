"""Pricing-API (B+1 Foundation): Upload von Lieferanten-Preislisten,
Tenant-Overrides, Rabatt-Regeln.

Dieser Router ist PARALLEL zu /api/v1/price-lists (altes Modell). Kein
Parsing- oder Lookup-Code hier — das kommt in B+2 und B+3.
"""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status as http_status,
)

from app.core.deps import CurrentUser, DbSession
from app.models.pricing import (
    PricelistStatus,
    SupplierPriceEntry,
    SupplierPriceList,
    TenantDiscountRule,
    TenantPriceOverride,
)
from app.schemas.pricing import (
    SupplierPriceEntryOut,
    SupplierPriceListDetail,
    SupplierPriceListOut,
    TenantDiscountRuleCreate,
    TenantDiscountRuleOut,
    TenantPriceOverrideCreate,
    TenantPriceOverrideOut,
)
from app.workers.pricelist_parse_worker import run_pricelist_parse

router = APIRouter(prefix="/pricing", tags=["pricing"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
_ALLOWED_EXT = {".pdf", ".xlsx", ".xls", ".csv"}
_MAX_UPLOAD_MB = 50
_SLUG_RE = re.compile(r"[^a-z0-9_-]+")


def _slug(value: str) -> str:
    """Einfacher ASCII-Slug fuer Pfad-Segmente (supplier_name, etc.)."""
    lower = value.strip().lower().replace(" ", "_")
    # Umlaute raus
    table = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
    lower = lower.translate(table)
    return _SLUG_RE.sub("_", lower).strip("_") or "unknown"


def _storage_root() -> Path:
    """storage/pricelists/ auf Projektebene (ausserhalb von backend/)."""
    # Struktur: lv-preisrechner/backend/app/api/pricing.py
    # -> parents[3] = lv-preisrechner/
    return Path(__file__).resolve().parents[3] / "storage" / "pricelists"


# ---------------------------------------------------------------------------
# POST /pricing/upload — Datei speichern + DB-Entry
# ---------------------------------------------------------------------------
@router.post(
    "/upload",
    response_model=SupplierPriceListOut,
    status_code=http_status.HTTP_201_CREATED,
)
async def upload_pricelist(
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    supplier_name: str = Form(...),
    list_name: str = Form(...),
    valid_from: str = Form(..., description="ISO-Datum YYYY-MM-DD"),
    supplier_location: str | None = Form(None),
    valid_until: str | None = Form(None, description="ISO-Datum YYYY-MM-DD"),
    auto_parse: bool = Form(True, description="Parser sofort starten"),
) -> SupplierPriceListOut:
    """Lädt eine Lieferanten-Preisliste hoch.

    - Validiert Dateiformat und -größe.
    - Speichert unter storage/pricelists/{tenant_id}/{supplier}/{name}_{ts}.{ext}.
    - Berechnet SHA256 des Inhalts.
    - Duplikat-Check: gleicher Hash im gleichen Tenant → 409.
    - Status wird auf PENDING_PARSE gesetzt. Kein Parsing hier (das macht B+2).
    """
    # --- Validierung ---
    if not file.filename:
        raise HTTPException(400, "Dateiname fehlt")
    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            400,
            f"Dateiformat {ext} nicht unterstuetzt. Erlaubt: {sorted(_ALLOWED_EXT)}",
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > _MAX_UPLOAD_MB:
        raise HTTPException(413, f"Datei {size_mb:.1f} MB > {_MAX_UPLOAD_MB} MB")

    # valid_from / valid_until parsen
    from datetime import date as _date

    try:
        vf = _date.fromisoformat(valid_from)
    except ValueError:
        raise HTTPException(422, "valid_from muss ISO-Datum sein (YYYY-MM-DD)")
    vu: _date | None = None
    if valid_until:
        try:
            vu = _date.fromisoformat(valid_until)
        except ValueError:
            raise HTTPException(422, "valid_until muss ISO-Datum sein (YYYY-MM-DD)")
        if vu < vf:
            raise HTTPException(422, "valid_until muss >= valid_from sein")

    # --- Hash + Duplikat-Check ---
    file_hash = hashlib.sha256(content).hexdigest()
    dup = (
        db.query(SupplierPriceList)
        .filter(
            SupplierPriceList.tenant_id == user.tenant_id,
            SupplierPriceList.source_file_hash == file_hash,
        )
        .first()
    )
    if dup:
        raise HTTPException(
            409,
            f"Datei wurde bereits hochgeladen (pricelist_id={dup.id}, "
            f"status={dup.status})",
        )

    # --- Dateipfad ---
    supplier_slug = _slug(supplier_name)
    ts = int(time.time())
    safe_name = _slug(Path(file.filename).stem)
    target_dir = _storage_root() / user.tenant_id / supplier_slug
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{safe_name}_{ts}{ext}"
    target_path.write_bytes(content)

    # --- DB-Entry ---
    entry = SupplierPriceList(
        tenant_id=user.tenant_id,
        supplier_name=supplier_name,
        supplier_location=supplier_location,
        list_name=list_name,
        valid_from=vf,
        valid_until=vu,
        source_file_path=str(target_path),
        source_file_hash=file_hash,
        status=PricelistStatus.PENDING_PARSE.value,
        uploaded_by_user_id=user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # --- Background-Parsing anstossen ---
    if auto_parse:
        background_tasks.add_task(run_pricelist_parse, entry.id)

    return SupplierPriceListOut.model_validate(entry)


# ---------------------------------------------------------------------------
# GET /pricing/pricelists — Listing
# ---------------------------------------------------------------------------
@router.get("/pricelists", response_model=list[SupplierPriceListOut])
def list_pricelists(
    user: CurrentUser,
    db: DbSession,
    status: str | None = Query(None, description="Filter auf Status"),
    supplier_name: str | None = Query(None),
    active: bool | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[SupplierPriceListOut]:
    q = db.query(SupplierPriceList).filter(
        SupplierPriceList.tenant_id == user.tenant_id
    )
    if status is not None:
        q = q.filter(SupplierPriceList.status == status)
    if supplier_name is not None:
        q = q.filter(SupplierPriceList.supplier_name == supplier_name)
    if active is not None:
        q = q.filter(SupplierPriceList.is_active.is_(active))
    q = q.order_by(SupplierPriceList.uploaded_at.desc()).offset(offset).limit(limit)
    return [SupplierPriceListOut.model_validate(p) for p in q.all()]


# ---------------------------------------------------------------------------
# GET /pricing/pricelists/{id}
# ---------------------------------------------------------------------------
@router.get("/pricelists/{pricelist_id}", response_model=SupplierPriceListDetail)
def get_pricelist(
    pricelist_id: str,
    user: CurrentUser,
    db: DbSession,
    include_entries: bool = Query(False),
    entries_offset: int = Query(0, ge=0),
    entries_limit: int = Query(100, ge=1, le=500),
) -> SupplierPriceListDetail:
    p = (
        db.query(SupplierPriceList)
        .filter(
            SupplierPriceList.id == pricelist_id,
            SupplierPriceList.tenant_id == user.tenant_id,
        )
        .first()
    )
    if p is None:
        raise HTTPException(404, "Preisliste nicht gefunden")

    detail = SupplierPriceListDetail.model_validate(p)
    if include_entries:
        entries = p.entries[entries_offset : entries_offset + entries_limit]
        from app.schemas.pricing import SupplierPriceEntryOut

        detail.entries = [SupplierPriceEntryOut.model_validate(e) for e in entries]
    return detail


# ---------------------------------------------------------------------------
# DELETE /pricing/pricelists/{id} — Soft-Delete (Archive)
# ---------------------------------------------------------------------------
@router.delete(
    "/pricelists/{pricelist_id}",
    response_model=SupplierPriceListOut,
)
def archive_pricelist(
    pricelist_id: str,
    user: CurrentUser,
    db: DbSession,
) -> SupplierPriceListOut:
    p = (
        db.query(SupplierPriceList)
        .filter(
            SupplierPriceList.id == pricelist_id,
            SupplierPriceList.tenant_id == user.tenant_id,
        )
        .first()
    )
    if p is None:
        raise HTTPException(404, "Preisliste nicht gefunden")
    p.status = PricelistStatus.ARCHIVED.value
    p.is_active = False
    db.commit()
    db.refresh(p)
    return SupplierPriceListOut.model_validate(p)


# ---------------------------------------------------------------------------
# POST /pricing/pricelists/{id}/activate
# ---------------------------------------------------------------------------
@router.post(
    "/pricelists/{pricelist_id}/activate",
    response_model=SupplierPriceListOut,
)
def activate_pricelist(
    pricelist_id: str,
    user: CurrentUser,
    db: DbSession,
) -> SupplierPriceListOut:
    """Setzt die Preisliste aktiv. Deaktiviert alle anderen Preislisten
    desselben Lieferanten im selben Tenant."""
    p = (
        db.query(SupplierPriceList)
        .filter(
            SupplierPriceList.id == pricelist_id,
            SupplierPriceList.tenant_id == user.tenant_id,
        )
        .first()
    )
    if p is None:
        raise HTTPException(404, "Preisliste nicht gefunden")

    # Alle anderen Preislisten des gleichen Lieferanten deaktivieren
    db.query(SupplierPriceList).filter(
        SupplierPriceList.tenant_id == user.tenant_id,
        SupplierPriceList.supplier_name == p.supplier_name,
        SupplierPriceList.id != p.id,
    ).update({"is_active": False})

    p.is_active = True
    db.commit()
    db.refresh(p)
    return SupplierPriceListOut.model_validate(p)


# ---------------------------------------------------------------------------
# POST /pricing/overrides
# ---------------------------------------------------------------------------
@router.post(
    "/overrides",
    response_model=TenantPriceOverrideOut,
    status_code=http_status.HTTP_201_CREATED,
)
def create_override(
    payload: TenantPriceOverrideCreate,
    user: CurrentUser,
    db: DbSession,
) -> TenantPriceOverrideOut:
    entry = TenantPriceOverride(
        tenant_id=user.tenant_id,
        article_number=payload.article_number,
        manufacturer=payload.manufacturer,
        override_price=payload.override_price,
        unit=payload.unit,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        notes=payload.notes,
        created_by_user_id=user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return TenantPriceOverrideOut.model_validate(entry)


@router.get("/overrides", response_model=list[TenantPriceOverrideOut])
def list_overrides(
    user: CurrentUser,
    db: DbSession,
    article_number: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[TenantPriceOverrideOut]:
    q = db.query(TenantPriceOverride).filter(
        TenantPriceOverride.tenant_id == user.tenant_id
    )
    if article_number:
        q = q.filter(TenantPriceOverride.article_number == article_number)
    q = q.order_by(TenantPriceOverride.created_at.desc()).offset(offset).limit(limit)
    return [TenantPriceOverrideOut.model_validate(o) for o in q.all()]


@router.delete(
    "/overrides/{override_id}", status_code=http_status.HTTP_204_NO_CONTENT
)
def delete_override(
    override_id: str,
    user: CurrentUser,
    db: DbSession,
) -> None:
    o = (
        db.query(TenantPriceOverride)
        .filter(
            TenantPriceOverride.id == override_id,
            TenantPriceOverride.tenant_id == user.tenant_id,
        )
        .first()
    )
    if o is None:
        raise HTTPException(404, "Override nicht gefunden")
    db.delete(o)
    db.commit()


# ---------------------------------------------------------------------------
# POST /pricing/discount-rules
# ---------------------------------------------------------------------------
@router.post(
    "/discount-rules",
    response_model=TenantDiscountRuleOut,
    status_code=http_status.HTTP_201_CREATED,
)
def create_discount_rule(
    payload: TenantDiscountRuleCreate,
    user: CurrentUser,
    db: DbSession,
) -> TenantDiscountRuleOut:
    entry = TenantDiscountRule(
        tenant_id=user.tenant_id,
        supplier_name=payload.supplier_name,
        discount_percent=payload.discount_percent,
        category=payload.category,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        notes=payload.notes,
        created_by_user_id=user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return TenantDiscountRuleOut.model_validate(entry)


@router.get("/discount-rules", response_model=list[TenantDiscountRuleOut])
def list_discount_rules(
    user: CurrentUser,
    db: DbSession,
    supplier_name: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[TenantDiscountRuleOut]:
    q = db.query(TenantDiscountRule).filter(
        TenantDiscountRule.tenant_id == user.tenant_id
    )
    if supplier_name:
        q = q.filter(TenantDiscountRule.supplier_name == supplier_name)
    q = q.order_by(TenantDiscountRule.created_at.desc()).offset(offset).limit(limit)
    return [TenantDiscountRuleOut.model_validate(r) for r in q.all()]


@router.delete(
    "/discount-rules/{rule_id}", status_code=http_status.HTTP_204_NO_CONTENT
)
def delete_discount_rule(
    rule_id: str,
    user: CurrentUser,
    db: DbSession,
) -> None:
    r = (
        db.query(TenantDiscountRule)
        .filter(
            TenantDiscountRule.id == rule_id,
            TenantDiscountRule.tenant_id == user.tenant_id,
        )
        .first()
    )
    if r is None:
        raise HTTPException(404, "Discount-Rule nicht gefunden")
    db.delete(r)
    db.commit()


# ---------------------------------------------------------------------------
# POST /pricing/pricelists/{id}/parse  (manueller Trigger)
# ---------------------------------------------------------------------------
@router.post(
    "/pricelists/{pricelist_id}/parse",
    response_model=SupplierPriceListOut,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def trigger_parse(
    pricelist_id: str,
    user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> SupplierPriceListOut:
    """Stoesst das Parsen einer Preisliste manuell an.

    Erlaubt bei Status PENDING_PARSE oder ERROR (Retry). Bei PARSING oder
    PARSED muss zuerst ueber einen Re-Upload oder manuelle Status-Aenderung
    gegangen werden (verhindert Race-Conditions).
    """
    p = (
        db.query(SupplierPriceList)
        .filter(
            SupplierPriceList.id == pricelist_id,
            SupplierPriceList.tenant_id == user.tenant_id,
        )
        .first()
    )
    if p is None:
        raise HTTPException(404, "Preisliste nicht gefunden")
    if p.status not in (
        PricelistStatus.PENDING_PARSE.value,
        PricelistStatus.ERROR.value,
    ):
        raise HTTPException(
            409,
            f"Parse kann nur aus Status PENDING_PARSE oder ERROR getriggert "
            f"werden. Aktueller Status: {p.status}",
        )

    background_tasks.add_task(run_pricelist_parse, p.id)
    # Sofort auf PARSING setzen (Client sieht direkt den Fortschritt).
    p.status = PricelistStatus.PARSING.value
    p.parse_error = None
    db.commit()
    db.refresh(p)
    return SupplierPriceListOut.model_validate(p)


# ---------------------------------------------------------------------------
# GET /pricing/pricelists/{id}/review-needed
# ---------------------------------------------------------------------------
@router.get(
    "/pricelists/{pricelist_id}/review-needed",
    response_model=list[SupplierPriceEntryOut],
)
def list_entries_needing_review(
    pricelist_id: str,
    user: CurrentUser,
    db: DbSession,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[SupplierPriceEntryOut]:
    """Listet alle Entries mit needs_review=True, sortiert nach Confidence aufsteigend.

    UI-Kontext: Reviewer arbeitet die unsichersten Entries zuerst ab.
    """
    # Tenant-Check uber Pricelist (nicht direkt Entry, weil Angreifer koennte
    # sonst ueber fremde pricelist_id an Entries kommen)
    pl = (
        db.query(SupplierPriceList)
        .filter(
            SupplierPriceList.id == pricelist_id,
            SupplierPriceList.tenant_id == user.tenant_id,
        )
        .first()
    )
    if pl is None:
        raise HTTPException(404, "Preisliste nicht gefunden")

    q = (
        db.query(SupplierPriceEntry)
        .filter(
            SupplierPriceEntry.pricelist_id == pricelist_id,
            SupplierPriceEntry.tenant_id == user.tenant_id,
            SupplierPriceEntry.needs_review.is_(True),
        )
        .order_by(SupplierPriceEntry.parser_confidence.asc())
        .offset(offset)
        .limit(limit)
    )
    return [SupplierPriceEntryOut.model_validate(e) for e in q.all()]
