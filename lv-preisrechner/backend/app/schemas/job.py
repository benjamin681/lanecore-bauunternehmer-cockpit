"""Job-Schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    status: str
    target_id: str
    target_kind: str
    progress: int
    message: str
    error_message: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
