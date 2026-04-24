"""add lvp_lv_gap_resolutions for B+4.6 gap-workflow

Revision ID: d5e8c3a91f24
Revises: c91f4d7a2b85
Create Date: 2026-04-24 20:00:00.000000

Audit-Tabelle fuer Nutzer-Aktionen auf Katalog-Luecken eines LV:
- resolution_type "manual_price": User hat einen manuellen Preis
  festgelegt (zusaetzlich entsteht ein TenantPriceOverride, damit der
  Preis auch in kuenftigen LVs greift).
- resolution_type "skip": User akzeptiert die Luecke bewusst — die
  Position wird in den Reports nicht mehr als Gap gelistet, bleibt
  aber mit EP=0 sichtbar.

UniqueConstraint (lv_id, material_dna, resolution_type): pro LV und
Material-DNA darf es genau eine aktive Resolution pro Typ geben.
Upsert-Semantik beim wiederholten Klick.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5e8c3a91f24"
down_revision: Union[str, Sequence[str], None] = "c91f4d7a2b85"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lvp_lv_gap_resolutions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "lv_id",
            sa.String(),
            sa.ForeignKey("lvp_lvs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(),
            sa.ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("material_dna", sa.String(length=500), nullable=False),
        sa.Column("resolution_type", sa.String(length=50), nullable=False),
        sa.Column("resolved_value", sa.JSON(), nullable=True),
        sa.Column(
            "tenant_price_override_id",
            sa.String(),
            sa.ForeignKey("lvp_tenant_price_overrides.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(),
            sa.ForeignKey("lvp_users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "lv_id",
            "material_dna",
            "resolution_type",
            name="uq_lvp_lv_gap_resolutions_lv_material_type",
        ),
    )
    op.create_index(
        "ix_lvp_lv_gap_resolutions_lv_id",
        "lvp_lv_gap_resolutions",
        ["lv_id"],
    )
    op.create_index(
        "ix_lvp_lv_gap_resolutions_tenant_id",
        "lvp_lv_gap_resolutions",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lvp_lv_gap_resolutions_tenant_id",
        table_name="lvp_lv_gap_resolutions",
    )
    op.drop_index(
        "ix_lvp_lv_gap_resolutions_lv_id",
        table_name="lvp_lv_gap_resolutions",
    )
    op.drop_table("lvp_lv_gap_resolutions")
