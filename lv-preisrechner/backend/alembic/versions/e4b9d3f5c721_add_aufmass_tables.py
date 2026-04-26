"""add aufmass tables + offers.aufmass_id (B+4.12 Iteration 4)

Revision ID: e4b9d3f5c721
Revises: d2a8c4e1b057
Create Date: 2026-04-26 09:00:00.000000

B+4.12 Aufmaß und Final-Kalkulation:

1. lvp_aufmasse: Aufmaß-Container mit Status (in_progress/finalized/cancelled).
   Verknuepft mit accepted Offer als source_offer_id (RESTRICT).
2. lvp_aufmass_positions: Snapshot je LV-Position + editierbare gemessene_menge.
3. lvp_offers.aufmass_id: optionaler FK fuer Final-Offers
   (pdf_format=aufmass_basiert).

Alle Schritte additiv.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4b9d3f5c721"
down_revision: Union[str, Sequence[str], None] = "d2a8c4e1b057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lvp_aufmasse",
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
            "source_offer_id", sa.String(),
            sa.ForeignKey("lvp_offers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("aufmass_number", sa.String(length=32), nullable=False),
        sa.Column(
            "status", sa.String(length=20),
            nullable=False, server_default="in_progress",
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "finalized_by", sa.String(),
            sa.ForeignKey("lvp_users.id", ondelete="SET NULL"),
            nullable=True,
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
        "ix_lvp_aufmasse_tenant_id", "lvp_aufmasse", ["tenant_id"],
    )
    op.create_index(
        "ix_lvp_aufmasse_lv_id", "lvp_aufmasse", ["lv_id"],
    )

    op.create_table(
        "lvp_aufmass_positions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "aufmass_id", sa.String(),
            sa.ForeignKey("lvp_aufmasse.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lv_position_id", sa.String(),
            sa.ForeignKey("lvp_positions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("oz", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("kurztext", sa.Text(), nullable=False, server_default=""),
        sa.Column("einheit", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("lv_menge", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("ep", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("gemessene_menge", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("gp_lv_snapshot", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("gp_aufmass", sa.Numeric(14, 2), nullable=False, server_default="0"),
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
        "ix_lvp_aufmass_positions_aufmass_id",
        "lvp_aufmass_positions", ["aufmass_id"],
    )

    # Final-Offer-FK auf das Aufmaß
    with op.batch_alter_table("lvp_offers") as batch_op:
        batch_op.add_column(
            sa.Column(
                "aufmass_id", sa.String(),
                sa.ForeignKey("lvp_aufmasse.id", ondelete="SET NULL"),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("lvp_offers") as batch_op:
        batch_op.drop_column("aufmass_id")

    op.drop_index(
        "ix_lvp_aufmass_positions_aufmass_id",
        table_name="lvp_aufmass_positions",
    )
    op.drop_table("lvp_aufmass_positions")

    op.drop_index("ix_lvp_aufmasse_lv_id", table_name="lvp_aufmasse")
    op.drop_index("ix_lvp_aufmasse_tenant_id", table_name="lvp_aufmasse")
    op.drop_table("lvp_aufmasse")
