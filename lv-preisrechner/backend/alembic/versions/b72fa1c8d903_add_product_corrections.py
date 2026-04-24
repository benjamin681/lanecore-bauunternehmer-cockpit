"""add lvp_product_corrections for P4 manual review workflow

Revision ID: b72fa1c8d903
Revises: f8a2b3e91d04
Create Date: 2026-04-24 17:30:00.000000

Neue Tabelle `lvp_product_corrections` nimmt manuelle Nutzer-Korrekturen
an Preislisten-Eintraegen auf (z.B. fehlende Bundgroessen). Der Parser
wendet sie beim Re-Upload automatisch an — Matching ueber
(manufacturer, article_number) mit Fallback auf product_name.

UniqueConstraint nutzt `NULLS NOT DISTINCT` (Postgres 15+), damit auch
NULL-Artikelnummern als Kollisionen zaehlen und ein Tenant nicht aus
Versehen 10 Korrekturen fuer denselben anonymen Produkttitel
akkumuliert.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b72fa1c8d903"
down_revision: Union[str, Sequence[str], None] = "f8a2b3e91d04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lvp_product_corrections",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(),
            sa.ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("manufacturer", sa.String(length=200), nullable=True),
        sa.Column("article_number", sa.String(length=100), nullable=True),
        sa.Column("product_name_fallback", sa.String(length=500), nullable=True),
        sa.Column("correction_type", sa.String(length=50), nullable=False),
        sa.Column("corrected_value", sa.JSON(), nullable=True),
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "manufacturer",
            "article_number",
            "correction_type",
            name="uq_lvp_product_corrections_tenant_key",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        "ix_lvp_product_corrections_tenant_id",
        "lvp_product_corrections",
        ["tenant_id"],
    )
    op.create_index(
        "ix_lvp_product_corrections_tenant_article",
        "lvp_product_corrections",
        ["tenant_id", "article_number"],
    )
    op.create_index(
        "ix_lvp_product_corrections_tenant_manufacturer",
        "lvp_product_corrections",
        ["tenant_id", "manufacturer"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lvp_product_corrections_tenant_manufacturer",
        table_name="lvp_product_corrections",
    )
    op.drop_index(
        "ix_lvp_product_corrections_tenant_article",
        table_name="lvp_product_corrections",
    )
    op.drop_index(
        "ix_lvp_product_corrections_tenant_id",
        table_name="lvp_product_corrections",
    )
    op.drop_table("lvp_product_corrections")
