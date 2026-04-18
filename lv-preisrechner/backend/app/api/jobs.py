"""Jobs-API: Status-Polling."""

from fastapi import APIRouter, HTTPException

from app.core.deps import CurrentUser, DbSession
from app.models.job import Job
from app.schemas.job import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: CurrentUser, db: DbSession) -> JobOut:
    job = db.query(Job).filter(Job.id == job_id, Job.tenant_id == user.tenant_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    return JobOut.model_validate(job)
