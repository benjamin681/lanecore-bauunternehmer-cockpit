"""Audit service — record changes to entities."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

log = structlog.get_logger()


def _json_safe(value: Any) -> Any:
    """Convert value to a JSON-serializable form (uuid → str, datetime → iso)."""
    from datetime import datetime, date
    from decimal import Decimal
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return str(value)


async def log_field_changes(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    user_id: str,
    old: dict,
    new: dict,
    action: str = "update",
) -> int:
    """Compare old and new dicts and create one AuditLog per changed field.

    Returns the number of entries created.
    """
    count = 0
    all_keys = set(old.keys()) | set(new.keys())
    for key in all_keys:
        o = old.get(key)
        n = new.get(key)
        if o == n:
            continue
        entry = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            field=key,
            old_value={"value": _json_safe(o)} if o is not None else None,
            new_value={"value": _json_safe(n)} if n is not None else None,
        )
        db.add(entry)
        count += 1
    if count > 0:
        try:
            await db.flush()
        except Exception:
            log.exception("audit_log_flush_failed", entity_type=entity_type, entity_id=str(entity_id))
    return count


async def log_entity_action(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    user_id: str,
    action: str,
    details: dict | None = None,
) -> None:
    """Log a create/delete/custom action on an entity."""
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        field=None,
        old_value=None,
        new_value=_json_safe(details) if details else None,
    )
    db.add(entry)
    try:
        await db.flush()
    except Exception:
        log.exception("audit_log_flush_failed", entity_type=entity_type, entity_id=str(entity_id))
