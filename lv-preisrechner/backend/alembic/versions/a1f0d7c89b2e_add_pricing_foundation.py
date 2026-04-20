"""add pricing foundation tables (B+1)

Revision ID: a1f0d7c89b2e
Revises: 8f2c1a9b4d01
Create Date: 2026-04-20 15:00:00.000000

Parallel-Architektur: 4 neue Tabellen additiv zur bestehenden PriceList/
PriceEntry-Infrastruktur. Bestehende Tabellen bleiben unverändert.

- lvp_supplier_pricelists     — Lieferanten-Preislisten mit Metadaten
- lvp_supplier_price_entries  — Einzelartikel mit Einheiten-Normalisierung
- lvp_tenant_price_overrides  — Kundenspezifische Preis-Uberschreibungen
- lvp_tenant_discount_rules   — Rabatt-Regeln auf Lieferanten-Listenpreise

legacy_*_id und migrated_from_legacy Felder sind Platzhalter fuer spaetere
Migration vom alten Modell. Aktuell ungefuellt.

Migration wurde manuell verfasst (autogenerate scheiterte an nicht-synchronem
lokalem SQLite-Stand).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1f0d7c89b2e"
down_revision: Union[str, Sequence[str], None] = "8f2c1a9b4d01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Tabelle 1: lvp_supplier_pricelists
    # ------------------------------------------------------------------
    op.create_table(
        "lvp_supplier_pricelists",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(),
            sa.ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("supplier_name", sa.String(length=200), nullable=False),
        sa.Column("supplier_location", sa.String(length=200), nullable=True),
        sa.Column("list_name", sa.String(length=200), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("source_file_path", sa.String(length=500), nullable=False),
        sa.Column("source_file_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="PENDING_PARSE",
        ),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("entries_total", sa.Integer(), nullable=True),
        sa.Column("entries_reviewed", sa.Integer(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_user_id",
            sa.String(),
            sa.ForeignKey("lvp_users.id"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "approved_by_user_id",
            sa.String(),
            sa.ForeignKey("lvp_users.id"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "legacy_pricelist_id",
            sa.String(),
            sa.ForeignKey("lvp_price_lists.id"),
            nullable=True,
        ),
        sa.Column(
            "migrated_from_legacy",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_lvp_supplier_pricelists_tenant_id",
        "lvp_supplier_pricelists",
        ["tenant_id"],
    )
    op.create_index(
        "ix_lvp_supplier_pricelists_source_file_hash",
        "lvp_supplier_pricelists",
        ["source_file_hash"],
    )
    op.create_index(
        "ix_lvp_supplier_pricelists_tenant_supplier",
        "lvp_supplier_pricelists",
        ["tenant_id", "supplier_name"],
    )
    op.create_index(
        "ix_lvp_supplier_pricelists_tenant_status",
        "lvp_supplier_pricelists",
        ["tenant_id", "status"],
    )

    # ------------------------------------------------------------------
    # Tabelle 2: lvp_supplier_price_entries
    # ------------------------------------------------------------------
    op.create_table(
        "lvp_supplier_price_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "pricelist_id",
            sa.String(),
            sa.ForeignKey("lvp_supplier_pricelists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.String(),
            sa.ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("article_number", sa.String(length=100), nullable=True),
        sa.Column("manufacturer", sa.String(length=200), nullable=True),
        sa.Column("product_name", sa.String(length=500), nullable=False),
        sa.Column("category", sa.String(length=200), nullable=True),
        sa.Column("subcategory", sa.String(length=200), nullable=True),
        sa.Column("price_net", sa.Float(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="EUR",
        ),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("package_size", sa.Float(), nullable=True),
        sa.Column("package_unit", sa.String(length=50), nullable=True),
        sa.Column("pieces_per_package", sa.Integer(), nullable=True),
        sa.Column("effective_unit", sa.String(length=50), nullable=False),
        sa.Column("price_per_effective_unit", sa.Float(), nullable=False),
        sa.Column(
            "attributes",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_row_raw", sa.Text(), nullable=True),
        sa.Column(
            "parser_confidence",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column(
            "needs_review",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "reviewed_by_user_id",
            sa.String(),
            sa.ForeignKey("lvp_users.id"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "correction_applied",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "legacy_entry_id",
            sa.String(),
            sa.ForeignKey("lvp_price_entries.id"),
            nullable=True,
        ),
        sa.Column(
            "migrated_from_legacy",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_lvp_supplier_price_entries_pricelist_id",
        "lvp_supplier_price_entries",
        ["pricelist_id"],
    )
    op.create_index(
        "ix_lvp_supplier_price_entries_tenant_id",
        "lvp_supplier_price_entries",
        ["tenant_id"],
    )
    op.create_index(
        "ix_lvp_supplier_price_entries_pricelist_article",
        "lvp_supplier_price_entries",
        ["pricelist_id", "article_number"],
    )
    op.create_index(
        "ix_lvp_supplier_price_entries_tenant_manufacturer",
        "lvp_supplier_price_entries",
        ["tenant_id", "manufacturer"],
    )
    op.create_index(
        "ix_lvp_supplier_price_entries_tenant_category",
        "lvp_supplier_price_entries",
        ["tenant_id", "category"],
    )

    # ------------------------------------------------------------------
    # Tabelle 3: lvp_tenant_price_overrides
    # ------------------------------------------------------------------
    op.create_table(
        "lvp_tenant_price_overrides",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(),
            sa.ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("article_number", sa.String(length=100), nullable=False),
        sa.Column("manufacturer", sa.String(length=200), nullable=True),
        sa.Column("override_price", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.String(),
            sa.ForeignKey("lvp_users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )
    op.create_index(
        "ix_lvp_tenant_price_overrides_tenant_id",
        "lvp_tenant_price_overrides",
        ["tenant_id"],
    )
    op.create_index(
        "ix_lvp_tenant_price_overrides_tenant_article",
        "lvp_tenant_price_overrides",
        ["tenant_id", "article_number"],
    )

    # ------------------------------------------------------------------
    # Tabelle 4: lvp_tenant_discount_rules
    # ------------------------------------------------------------------
    op.create_table(
        "lvp_tenant_discount_rules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(),
            sa.ForeignKey("lvp_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("supplier_name", sa.String(length=200), nullable=False),
        sa.Column("discount_percent", sa.Float(), nullable=False),
        sa.Column("category", sa.String(length=200), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            sa.String(),
            sa.ForeignKey("lvp_users.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )
    op.create_index(
        "ix_lvp_tenant_discount_rules_tenant_id",
        "lvp_tenant_discount_rules",
        ["tenant_id"],
    )
    op.create_index(
        "ix_lvp_tenant_discount_rules_tenant_supplier",
        "lvp_tenant_discount_rules",
        ["tenant_id", "supplier_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lvp_tenant_discount_rules_tenant_supplier",
        table_name="lvp_tenant_discount_rules",
    )
    op.drop_index(
        "ix_lvp_tenant_discount_rules_tenant_id",
        table_name="lvp_tenant_discount_rules",
    )
    op.drop_table("lvp_tenant_discount_rules")

    op.drop_index(
        "ix_lvp_tenant_price_overrides_tenant_article",
        table_name="lvp_tenant_price_overrides",
    )
    op.drop_index(
        "ix_lvp_tenant_price_overrides_tenant_id",
        table_name="lvp_tenant_price_overrides",
    )
    op.drop_table("lvp_tenant_price_overrides")

    op.drop_index(
        "ix_lvp_supplier_price_entries_tenant_category",
        table_name="lvp_supplier_price_entries",
    )
    op.drop_index(
        "ix_lvp_supplier_price_entries_tenant_manufacturer",
        table_name="lvp_supplier_price_entries",
    )
    op.drop_index(
        "ix_lvp_supplier_price_entries_pricelist_article",
        table_name="lvp_supplier_price_entries",
    )
    op.drop_index(
        "ix_lvp_supplier_price_entries_tenant_id",
        table_name="lvp_supplier_price_entries",
    )
    op.drop_index(
        "ix_lvp_supplier_price_entries_pricelist_id",
        table_name="lvp_supplier_price_entries",
    )
    op.drop_table("lvp_supplier_price_entries")

    op.drop_index(
        "ix_lvp_supplier_pricelists_tenant_status",
        table_name="lvp_supplier_pricelists",
    )
    op.drop_index(
        "ix_lvp_supplier_pricelists_tenant_supplier",
        table_name="lvp_supplier_pricelists",
    )
    op.drop_index(
        "ix_lvp_supplier_pricelists_source_file_hash",
        table_name="lvp_supplier_pricelists",
    )
    op.drop_index(
        "ix_lvp_supplier_pricelists_tenant_id",
        table_name="lvp_supplier_pricelists",
    )
    op.drop_table("lvp_supplier_pricelists")
