"""add invoices + invoice_status_changes + dunnings (B+4.13 Iteration 5)

Revision ID: f7c2b9e3a418
Revises: e4b9d3f5c721
Create Date: 2026-04-26 09:30:00.000000

B+4.13 Schlussrechnung und Mahnwesen:

1. lvp_invoices: Rechnung mit Snapshot der Final-Offer-Summen.
   Eindeutige durchlaufende Nummer pro Tenant pro Jahr (UNIQUE-Index).
2. lvp_invoice_status_changes: Audit-Trail je Status-Wechsel.
3. lvp_dunnings: Mahnstufen 1-3 mit eskalierender Frist + Gebuehr.

Alle drei Tabellen additiv, FKs auf lvp_offers + lvp_aufmasse + lvp_lvs +
lvp_tenants + lvp_users.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7c2b9e3a418"
down_revision: Union[str, Sequence[str], None] = "e4b9d3f5c721"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lvp_invoices",
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
        sa.Column(
            "source_aufmass_id", sa.String(),
            sa.ForeignKey("lvp_aufmasse.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("invoice_number", sa.String(length=32), nullable=False),
        sa.Column(
            "invoice_type", sa.String(length=30),
            nullable=False, server_default="schlussrechnung",
        ),
        sa.Column(
            "status", sa.String(length=20),
            nullable=False, server_default="draft",
        ),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("sent_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column(
            "paid_amount", sa.Numeric(14, 2),
            nullable=False, server_default="0",
        ),
        sa.Column("betrag_netto", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("betrag_ust", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("betrag_brutto", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("position_count", sa.Integer(), nullable=False, server_default="0"),
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
    op.create_index("ix_lvp_invoices_tenant_id", "lvp_invoices", ["tenant_id"])
    op.create_index("ix_lvp_invoices_lv_id", "lvp_invoices", ["lv_id"])
    op.create_index("ix_lvp_invoices_status", "lvp_invoices", ["status"])
    op.create_index("ix_lvp_invoices_due_date", "lvp_invoices", ["due_date"])
    op.create_index(
        "ix_lvp_invoices_tenant_invoice_number",
        "lvp_invoices", ["tenant_id", "invoice_number"], unique=True,
    )

    op.create_table(
        "lvp_invoice_status_changes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "invoice_id", sa.String(),
            sa.ForeignKey("lvp_invoices.id", ondelete="CASCADE"),
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
        "ix_lvp_invoice_status_changes_invoice_id",
        "lvp_invoice_status_changes", ["invoice_id"],
    )

    op.create_table(
        "lvp_dunnings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(),
            sa.ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id", sa.String(),
            sa.ForeignKey("lvp_invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dunning_level", sa.Integer(), nullable=False),
        sa.Column("dunning_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column(
            "mahngebuehr_betrag", sa.Numeric(10, 2),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "mahnzinsen_betrag", sa.Numeric(10, 2),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "status", sa.String(length=20),
            nullable=False, server_default="draft",
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
    op.create_index("ix_lvp_dunnings_tenant_id", "lvp_dunnings", ["tenant_id"])
    op.create_index("ix_lvp_dunnings_invoice_id", "lvp_dunnings", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_lvp_dunnings_invoice_id", table_name="lvp_dunnings")
    op.drop_index("ix_lvp_dunnings_tenant_id", table_name="lvp_dunnings")
    op.drop_table("lvp_dunnings")

    op.drop_index(
        "ix_lvp_invoice_status_changes_invoice_id",
        table_name="lvp_invoice_status_changes",
    )
    op.drop_table("lvp_invoice_status_changes")

    op.drop_index("ix_lvp_invoices_tenant_invoice_number", table_name="lvp_invoices")
    op.drop_index("ix_lvp_invoices_due_date", table_name="lvp_invoices")
    op.drop_index("ix_lvp_invoices_status", table_name="lvp_invoices")
    op.drop_index("ix_lvp_invoices_lv_id", table_name="lvp_invoices")
    op.drop_index("ix_lvp_invoices_tenant_id", table_name="lvp_invoices")
    op.drop_table("lvp_invoices")
