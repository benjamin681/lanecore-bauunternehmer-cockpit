"""add offers + offer_status_changes (B+4.11 Iteration 3)

Revision ID: d2a8c4e1b057
Revises: c1d5f7e9a042
Create Date: 2026-04-25 23:50:00.000000

B+4.11 Offer-Lifecycle:

1. lvp_offers: Angebot mit Snapshot der LV-Summe + Status-Lifecycle.
   - tenant_id CASCADE, lv_id CASCADE, project_id SET NULL
   - offer_number auto-generiert pro Tenant pro Tag (A-yymmdd-NN)
   - betrag_netto/_brutto/position_count als Snapshot
2. lvp_offer_status_changes: Audit-Trail je Status-Wechsel.

Beide Tabellen additiv, keine bestehenden Daten betroffen.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2a8c4e1b057"
down_revision: Union[str, Sequence[str], None] = "c1d5f7e9a042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lvp_offers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(),
            sa.ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lv_id", sa.String(),
            sa.ForeignKey("lvp_lvs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id", sa.String(),
            sa.ForeignKey("lvp_projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("offer_number", sa.String(length=32), nullable=False),
        sa.Column(
            "status", sa.String(length=20),
            nullable=False, server_default="draft",
        ),
        sa.Column("offer_date", sa.Date(), nullable=False),
        sa.Column("sent_date", sa.Date(), nullable=True),
        sa.Column("accepted_date", sa.Date(), nullable=True),
        sa.Column("rejected_date", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column(
            "betrag_netto", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "betrag_brutto", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "position_count", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "pdf_format", sa.String(length=30),
            nullable=False, server_default="eigenes_layout",
        ),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index(
        "ix_lvp_offers_tenant_id", "lvp_offers", ["tenant_id"],
    )
    op.create_index(
        "ix_lvp_offers_lv_id", "lvp_offers", ["lv_id"],
    )
    op.create_index(
        "ix_lvp_offers_status", "lvp_offers", ["status"],
    )
    op.create_index(
        "ix_lvp_offers_tenant_offer_number",
        "lvp_offers", ["tenant_id", "offer_number"],
        unique=True,
    )

    op.create_table(
        "lvp_offer_status_changes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "offer_id", sa.String(),
            sa.ForeignKey("lvp_offers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_status", sa.String(length=20), nullable=True),
        sa.Column("new_status", sa.String(length=20), nullable=False),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "changed_by", sa.String(),
            sa.ForeignKey("lvp_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_lvp_offer_status_changes_offer_id",
        "lvp_offer_status_changes", ["offer_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lvp_offer_status_changes_offer_id",
        table_name="lvp_offer_status_changes",
    )
    op.drop_table("lvp_offer_status_changes")

    op.drop_index("ix_lvp_offers_tenant_offer_number", table_name="lvp_offers")
    op.drop_index("ix_lvp_offers_status", table_name="lvp_offers")
    op.drop_index("ix_lvp_offers_lv_id", table_name="lvp_offers")
    op.drop_index("ix_lvp_offers_tenant_id", table_name="lvp_offers")
    op.drop_table("lvp_offers")
