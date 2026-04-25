"""B+4.9 — Tenant-Profil + Customer/Project CRUD."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.deps import CurrentUser, DbSession
from app.models.customer import Customer, Project
from app.models.lv import LV
from app.models.tenant import Tenant
from app.schemas.tenant import (
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    TenantProfileOut,
    TenantProfileUpdate,
)

router = APIRouter()


# --------------------------------------------------------------------------- #
# /tenant/profile
# --------------------------------------------------------------------------- #
@router.get("/tenant/profile", response_model=TenantProfileOut, tags=["tenant"])
def get_tenant_profile(user: CurrentUser, db: DbSession) -> TenantProfileOut:
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant nicht gefunden")
    return TenantProfileOut.model_validate(tenant)


@router.patch("/tenant/profile", response_model=TenantProfileOut, tags=["tenant"])
def update_tenant_profile(
    payload: TenantProfileUpdate,
    user: CurrentUser,
    db: DbSession,
) -> TenantProfileOut:
    tenant = db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant nicht gefunden")
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        # Whitespace-Strip fuer String-Felder
        if isinstance(v, str):
            v = v.strip()
            if k in ("bank_iban", "bank_bic"):
                v = v.replace(" ", "").upper()
        setattr(tenant, k, v if v != "" else None)
    db.commit()
    db.refresh(tenant)
    return TenantProfileOut.model_validate(tenant)


# --------------------------------------------------------------------------- #
# /customers
# --------------------------------------------------------------------------- #
customer_router = APIRouter(prefix="/customers", tags=["customers"])


@customer_router.get("", response_model=list[CustomerOut])
def list_customers(
    user: CurrentUser,
    db: DbSession,
    search: str | None = Query(None, max_length=100),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[CustomerOut]:
    q = db.query(Customer).filter(Customer.tenant_id == user.tenant_id)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(Customer.name.ilike(like))
    rows = q.order_by(Customer.name).offset(offset).limit(limit).all()
    return [CustomerOut.model_validate(c) for c in rows]


@customer_router.post("", response_model=CustomerOut, status_code=201)
def create_customer(
    payload: CustomerCreate, user: CurrentUser, db: DbSession,
) -> CustomerOut:
    data = payload.model_dump(exclude_unset=True)
    customer = Customer(tenant_id=user.tenant_id, **data)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerOut.model_validate(customer)


@customer_router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: str, user: CurrentUser, db: DbSession) -> CustomerOut:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)
        .first()
    )
    if customer is None:
        raise HTTPException(404, "Kunde nicht gefunden")
    return CustomerOut.model_validate(customer)


@customer_router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    user: CurrentUser,
    db: DbSession,
) -> CustomerOut:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)
        .first()
    )
    if customer is None:
        raise HTTPException(404, "Kunde nicht gefunden")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(customer, k, v)
    db.commit()
    db.refresh(customer)
    return CustomerOut.model_validate(customer)


@customer_router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: str, user: CurrentUser, db: DbSession) -> None:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == user.tenant_id)
        .first()
    )
    if customer is None:
        raise HTTPException(404, "Kunde nicht gefunden")
    # Restrict-FK auf projects; bei haengenden Projekten weigern.
    has_projects = (
        db.query(Project).filter(Project.customer_id == customer_id).first()
    )
    if has_projects is not None:
        raise HTTPException(
            409,
            "Kunde hat Projekte — bitte erst Projekte loeschen oder umzuordnen.",
        )
    db.delete(customer)
    db.commit()


# --------------------------------------------------------------------------- #
# /projects
# --------------------------------------------------------------------------- #
project_router = APIRouter(prefix="/projects", tags=["projects"])


@project_router.get("", response_model=list[ProjectOut])
def list_projects(
    user: CurrentUser,
    db: DbSession,
    customer_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[ProjectOut]:
    q = db.query(Project).filter(Project.tenant_id == user.tenant_id)
    if customer_id:
        q = q.filter(Project.customer_id == customer_id)
    if status:
        q = q.filter(Project.status == status)
    rows = q.order_by(Project.created_at.desc()).offset(offset).limit(limit).all()
    return [ProjectOut.model_validate(p) for p in rows]


@project_router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectCreate, user: CurrentUser, db: DbSession,
) -> ProjectOut:
    # Customer muss zum Tenant gehoeren
    customer = (
        db.query(Customer)
        .filter(
            Customer.id == payload.customer_id,
            Customer.tenant_id == user.tenant_id,
        )
        .first()
    )
    if customer is None:
        raise HTTPException(422, "customer_id ungueltig oder fremder Tenant")
    data = payload.model_dump(exclude_unset=True)
    if not data.get("status"):
        data["status"] = "draft"
    project = Project(tenant_id=user.tenant_id, **data)
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate(project)


@project_router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, user: CurrentUser, db: DbSession) -> ProjectOut:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.tenant_id == user.tenant_id)
        .first()
    )
    if project is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    return ProjectOut.model_validate(project)


@project_router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    user: CurrentUser,
    db: DbSession,
) -> ProjectOut:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.tenant_id == user.tenant_id)
        .first()
    )
    if project is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    updates = payload.model_dump(exclude_unset=True)
    if "customer_id" in updates and updates["customer_id"]:
        # Customer muss zum Tenant gehoeren
        c = (
            db.query(Customer)
            .filter(
                Customer.id == updates["customer_id"],
                Customer.tenant_id == user.tenant_id,
            )
            .first()
        )
        if c is None:
            raise HTTPException(422, "customer_id ungueltig oder fremder Tenant")
    for k, v in updates.items():
        setattr(project, k, v)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate(project)


@project_router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, user: CurrentUser, db: DbSession) -> None:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.tenant_id == user.tenant_id)
        .first()
    )
    if project is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    # LVs am Projekt: project_id wird durch ON DELETE SET NULL aufgeloest.
    db.delete(project)
    db.commit()


@project_router.get("/{project_id}/lvs")
def list_project_lvs(
    project_id: str, user: CurrentUser, db: DbSession,
) -> list[dict]:
    """Liste aller LVs eines Projekts. Tenant-scoped."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.tenant_id == user.tenant_id)
        .first()
    )
    if project is None:
        raise HTTPException(404, "Projekt nicht gefunden")
    lvs = (
        db.query(LV)
        .filter(LV.project_id == project_id, LV.tenant_id == user.tenant_id)
        .order_by(LV.created_at.desc())
        .all()
    )
    return [
        {
            "id": lv.id,
            "projekt_name": lv.projekt_name,
            "auftraggeber": lv.auftraggeber,
            "status": lv.status,
            "angebotssumme_netto": lv.angebotssumme_netto,
            "positionen_gesamt": lv.positionen_gesamt,
            "created_at": lv.created_at.isoformat() if lv.created_at else None,
        }
        for lv in lvs
    ]
