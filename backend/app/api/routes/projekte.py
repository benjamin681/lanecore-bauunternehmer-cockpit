"""Projekt-Management Endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.core.exceptions import JobNotFoundError
from app.models.projekt import Projekt
from app.models.analyse_job import AnalyseJob
from app.schemas.projekt import ProjektCreate, ProjektResponse, ProjektUpdate

router = APIRouter()


@router.get("/", response_model=list[ProjektResponse])
async def list_projekte(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Alle Projekte des Nutzers auflisten."""
    result = await db.execute(
        select(Projekt)
        .where(Projekt.user_id == user_id)
        .order_by(Projekt.updated_at.desc())
    )
    projekte = result.scalars().all()

    responses = []
    for p in projekte:
        # Count analyses per project
        count_result = await db.execute(
            select(func.count(AnalyseJob.id)).where(AnalyseJob.projekt_id == p.id)
        )
        count = count_result.scalar() or 0
        resp = ProjektResponse.model_validate(p)
        resp.analyse_count = count
        responses.append(resp)

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
    """Einzelnes Projekt abrufen."""
    result = await db.execute(
        select(Projekt).where(Projekt.id == projekt_id, Projekt.user_id == user_id)
    )
    projekt = result.scalar_one_or_none()
    if not projekt:
        raise JobNotFoundError(str(projekt_id))
    return ProjektResponse.model_validate(projekt)


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
