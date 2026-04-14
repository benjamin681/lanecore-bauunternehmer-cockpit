"""Projekt-Management Endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.core.exceptions import JobNotFoundError
from app.models.projekt import Projekt
from app.models.analyse_job import AnalyseJob
from app.schemas.projekt import (
    AnalyseJobBrief,
    ProjektCreate,
    ProjektResponse,
    ProjektUpdate,
)

router = APIRouter()


@router.get("/", response_model=list[ProjektResponse])
async def list_projekte(
    user_id: str = Depends(get_current_user_id),
    sort: str = Query("updated_at", description="Sort by: auftraggeber, name, status, created_at, updated_at"),
    order: str = Query("desc", description="asc or desc"),
    status: str | None = Query(None, description="Filter by status: aktiv, abgeschlossen, archiviert"),
    search: str | None = Query(None, description="Search in name, auftraggeber, adresse"),
    db: AsyncSession = Depends(get_db),
):
    """Alle Projekte des Nutzers auflisten mit Sortierung und Filter."""
    query = (
        select(Projekt)
        .options(selectinload(Projekt.analyse_jobs))
        .where(Projekt.user_id == user_id)
    )

    # Filter by status
    if status:
        query = query.where(Projekt.status == status)

    # Search
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            Projekt.name.ilike(search_pattern)
            | Projekt.auftraggeber.ilike(search_pattern)
            | Projekt.adresse.ilike(search_pattern)
            | Projekt.bauherr.ilike(search_pattern)
        )

    # Sort
    sort_column = getattr(Projekt, sort, Projekt.updated_at)
    if order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    result = await db.execute(query)
    projekte = result.scalars().all()

    responses = []
    for p in projekte:
        analysen = [
            AnalyseJobBrief(
                id=j.id,
                filename=j.filename,
                status=j.status,
                progress=j.progress,
                created_at=j.created_at,
            )
            for j in (p.analyse_jobs or [])
        ]
        responses.append(ProjektResponse(
            id=p.id,
            name=p.name,
            auftraggeber=p.auftraggeber,
            bauherr=p.bauherr,
            architekt=p.architekt,
            adresse=p.adresse,
            plan_nr=p.plan_nr,
            status=p.status,
            beschreibung=p.beschreibung,
            created_at=p.created_at,
            updated_at=p.updated_at,
            analyse_count=len(analysen),
            analysen=analysen,
        ))

    return responses


@router.post("/", response_model=ProjektResponse, status_code=201)
async def create_projekt(
    data: ProjektCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Neues Projekt erstellen."""
    projekt = Projekt(
        user_id=user_id,
        name=data.name,
        auftraggeber=data.auftraggeber,
        adresse=data.adresse,
        beschreibung=data.beschreibung,
    )
    db.add(projekt)
    await db.commit()
    await db.refresh(projekt)
    return ProjektResponse.model_validate(projekt)


@router.get("/{projekt_id}", response_model=ProjektResponse)
async def get_projekt(
    projekt_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Einzelnes Projekt mit allen Analysen abrufen."""
    result = await db.execute(
        select(Projekt)
        .options(selectinload(Projekt.analyse_jobs))
        .where(Projekt.id == projekt_id, Projekt.user_id == user_id)
    )
    projekt = result.scalar_one_or_none()
    if not projekt:
        raise JobNotFoundError(str(projekt_id))

    analysen = [
        AnalyseJobBrief(
            id=j.id,
            filename=j.filename,
            status=j.status,
            progress=j.progress,
            created_at=j.created_at,
        )
        for j in (projekt.analyse_jobs or [])
    ]
    return ProjektResponse(
        id=projekt.id,
        name=projekt.name,
        auftraggeber=projekt.auftraggeber,
        bauherr=projekt.bauherr,
        architekt=projekt.architekt,
        adresse=projekt.adresse,
        plan_nr=projekt.plan_nr,
        status=projekt.status,
        beschreibung=projekt.beschreibung,
        created_at=projekt.created_at,
        updated_at=projekt.updated_at,
        analyse_count=len(analysen),
        analysen=analysen,
    )


@router.get("/{projekt_id}/kalkulation")
async def get_projekt_kalkulation(
    projekt_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Aggregierte Kalkulation über alle abgeschlossenen Analysen eines Projekts.

    Merges all completed analyses into one combined kalkulation with
    materials, price matching, and Kundenangebot.
    """
    from app.services.kalkulation_service import erstelle_projekt_kalkulation

    # Verify the project belongs to this user
    result = await db.execute(
        select(Projekt).where(Projekt.id == projekt_id, Projekt.user_id == user_id)
    )
    projekt = result.scalar_one_or_none()
    if not projekt:
        raise JobNotFoundError(str(projekt_id))

    kalkulation = await erstelle_projekt_kalkulation(projekt_id, db)
    kalkulation["projekt_id"] = str(projekt_id)
    kalkulation["projekt_name"] = projekt.name

    return kalkulation


@router.delete("/{projekt_id}", status_code=204)
async def delete_projekt(
    projekt_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Projekt und alle zugehoerigen Analysen loeschen."""
    result = await db.execute(
        select(Projekt)
        .options(selectinload(Projekt.analyse_jobs))
        .where(Projekt.id == projekt_id, Projekt.user_id == user_id)
    )
    projekt = result.scalar_one_or_none()
    if not projekt:
        raise JobNotFoundError(str(projekt_id))

    await db.delete(projekt)
    await db.commit()
    return None


@router.patch("/{projekt_id}", response_model=ProjektResponse)
async def update_projekt(
    projekt_id: UUID,
    data: ProjektUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Projekt aktualisieren."""
    result = await db.execute(
        select(Projekt).where(Projekt.id == projekt_id, Projekt.user_id == user_id)
    )
    projekt = result.scalar_one_or_none()
    if not projekt:
        raise JobNotFoundError(str(projekt_id))

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(projekt, field, value)

    await db.commit()
    await db.refresh(projekt)
    return ProjektResponse.model_validate(projekt)
