"""Dashboard statistics endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.models.analyse_job import AnalyseJob
from app.models.projekt import Projekt

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard_stats(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dashboard-Statistiken für den aktuellen Nutzer."""
    # Projekte zählen
    proj_count = await db.scalar(
        select(func.count(Projekt.id)).where(Projekt.user_id == user_id)
    ) or 0

    # Analysen zählen
    total_jobs = await db.scalar(select(func.count(AnalyseJob.id))) or 0
    completed_jobs = await db.scalar(
        select(func.count(AnalyseJob.id)).where(AnalyseJob.status == "completed")
    ) or 0

    # Kosten summieren
    total_cost = await db.scalar(
        select(func.sum(AnalyseJob.cost_usd)).where(AnalyseJob.status == "completed")
    ) or 0

    # Tokens summieren
    total_input = await db.scalar(
        select(func.sum(AnalyseJob.input_tokens)).where(AnalyseJob.status == "completed")
    ) or 0
    total_output = await db.scalar(
        select(func.sum(AnalyseJob.output_tokens)).where(AnalyseJob.status == "completed")
    ) or 0

    # Eingesparte Stunden (Annahme: 4h manuell pro Analyse)
    hours_saved = completed_jobs * 4

    return {
        "projekte": proj_count,
        "analysen_gesamt": total_jobs,
        "analysen_erfolgreich": completed_jobs,
        "eingesparte_stunden": hours_saved,
        "kosten_usd_gesamt": round(float(total_cost), 2),
        "tokens_input_gesamt": total_input,
        "tokens_output_gesamt": total_output,
    }
