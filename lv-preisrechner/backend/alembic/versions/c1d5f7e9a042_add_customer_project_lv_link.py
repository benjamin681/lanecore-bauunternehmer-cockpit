"""add customers + projects + lv.project_id link

Revision ID: c1d5f7e9a042
Revises: b9c4e1f2a583
Create Date: 2026-04-25 11:30:00.000000

B+4.9 Foundation des Vertriebs-Workflows:

1. lvp_customers: Stammdaten der Auftraggeber. Tenant-scoped.
2. lvp_projects: Bauvorhaben. Verknuepft Customer ↔ N LVs.
3. lvp_lvs.project_id: optionaler FK aufs Project. Bei null = "Lose
   LVs"-Bucket (z.B. wenn Auto-Anlage aus dem Header scheitert).

Alle drei Schritte additiv, keine bestehenden Daten gehen verloren.
lv.auftraggeber bleibt als Snapshot-Cache erhalten — die normalisierte
Stammdaten-Wahrheit liegt ab jetzt im Customer-Modell.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d5f7e9a042"
down_revision: Union[str, Sequence[str], None] = "b9c4e1f2a583"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lvp_customers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(),
            sa.ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("contact_person", sa.String(length=200), nullable=True),
        sa.Column("address_street", sa.String(length=200), nullable=True),
        sa.Column("address_zip", sa.String(length=20), nullable=True),
        sa.Column("address_city", sa.String(length=100), nullable=True),
        sa.Column(
            "address_country", sa.String(length=2),
            nullable=False, server_default="DE",
        ),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        "ix_lvp_customers_tenant_name",
        "lvp_customers", ["tenant_id", "name"],
    )

    op.create_table(
        "lvp_projects",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(),
            sa.ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id", sa.String(),
            sa.ForeignKey("lvp_customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("address_street", sa.String(length=200), nullable=True),
        sa.Column("address_zip", sa.String(length=20), nullable=True),
        sa.Column("address_city", sa.String(length=100), nullable=True),
        sa.Column(
            "status", sa.String(length=20),
            nullable=False, server_default="draft",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        "ix_lvp_projects_tenant_id",
        "lvp_projects", ["tenant_id"],
    )
    op.create_index(
        "ix_lvp_projects_customer_id",
        "lvp_projects", ["customer_id"],
    )
    op.create_index(
        "ix_lvp_projects_tenant_status",
        "lvp_projects", ["tenant_id", "status"],
    )

    # LV-Project-FK additiv und nullable, damit Bestands-LVs nicht brechen.
    with op.batch_alter_table("lvp_lvs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "project_id", sa.String(),
                sa.ForeignKey("lvp_projects.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
    op.create_index(
        "ix_lvp_lvs_project_id",
        "lvp_lvs", ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lvp_lvs_project_id", table_name="lvp_lvs")
    with op.batch_alter_table("lvp_lvs") as batch_op:
        batch_op.drop_column("project_id")

    op.drop_index("ix_lvp_projects_tenant_status", table_name="lvp_projects")
    op.drop_index("ix_lvp_projects_customer_id", table_name="lvp_projects")
    op.drop_index("ix_lvp_projects_tenant_id", table_name="lvp_projects")
    op.drop_table("lvp_projects")

    op.drop_index("ix_lvp_customers_tenant_name", table_name="lvp_customers")
    op.drop_table("lvp_customers")
