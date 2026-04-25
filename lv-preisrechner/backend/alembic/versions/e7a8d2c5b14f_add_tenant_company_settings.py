"""add tenant.company_settings (JSON) for PDF-export header/footer

Revision ID: e7a8d2c5b14f
Revises: a4b1e7c30982
Create Date: 2026-04-25 11:00:00.000000

Halt der Stammdaten, die das Angebots-PDF im Briefkopf und Footer
zeigt. Kein hartes Schema in der DB — JSON-Feld erlaubt iteratives
Hinzufuegen ohne weitere Migrationen.

Erwartete Keys (alle optional, gestaltbar im Settings-UI):
{
  "firma":           str,
  "anschrift_zeile1": str,
  "anschrift_zeile2": str,
  "telefon":         str,
  "email":           str,
  "website":         str,
  "ust_id":          str,
  "iban":            str,
  "bic":             str,
  "bank_name":       str,
  "footer_text":     str,    # AGB-Hinweis, Zahlungsbedingungen
  "logo_path":       str     # spaeter: Pfad im storage/Volume
}

Additiv, nullable, kein Datenverlust beim Downgrade.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7a8d2c5b14f"
down_revision: Union[str, Sequence[str], None] = "a4b1e7c30982"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("lvp_tenants") as batch_op:
        batch_op.add_column(
            sa.Column("company_settings", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("lvp_tenants") as batch_op:
        batch_op.drop_column("company_settings")
