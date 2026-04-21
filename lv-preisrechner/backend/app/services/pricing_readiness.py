"""Readiness-Pruefung fuer die neue Preis-Engine (B+4.3.1).

Die neue Lookup-Engine (kalkulation.py mit Flag=True) verlangt Variante
A-plus: mindestens eine aktive SupplierPriceList ODER mindestens ein
TenantPriceOverride. Dieses Modul kapselt den Check, damit sowohl der
readiness-Endpoint als auch das Flag-Toggle dieselbe Quelle verwenden.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.pricing import (
    PricelistStatus,
    SupplierPriceList,
    TenantPriceOverride,
)


@dataclass
class Readiness:
    has_active_pricelist: bool
    has_overrides: bool

    @property
    def ready_for_new_pricing(self) -> bool:
        return self.has_active_pricelist or self.has_overrides


def compute_readiness(db: Session, tenant_id: str) -> Readiness:
    """Einzelne Existenz-Queries, minimaler DB-Aufwand."""
    has_list = (
        db.query(SupplierPriceList.id)
        .filter(
            SupplierPriceList.tenant_id == tenant_id,
            SupplierPriceList.is_active.is_(True),
            SupplierPriceList.status != PricelistStatus.ARCHIVED.value,
        )
        .first()
        is not None
    )
    has_override = (
        db.query(TenantPriceOverride.id)
        .filter(TenantPriceOverride.tenant_id == tenant_id)
        .first()
        is not None
    )
    return Readiness(has_active_pricelist=has_list, has_overrides=has_override)


def is_ready_for_new_pricing(db: Session, tenant_id: str) -> bool:
    return compute_readiness(db, tenant_id).ready_for_new_pricing
