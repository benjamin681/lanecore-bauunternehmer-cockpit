"""add parse_progress JSON to supplier_pricelists

Revision ID: a4b1e7c30982
Revises: d5e8c3a91f24
Create Date: 2026-04-25 09:30:00.000000

Live-Fortschritt eines laufenden Parses, damit das UI dem Nutzer
zeigen kann was passiert (statt 18 min langem leeren Spinner).

Struktur des JSON:
{
  "current_batch": int,        # 1-basiert
  "total_batches": int,
  "current_action": str,       # z.B. "Verarbeite Seiten 13-15"
  "started_at": "2026-04-25T09:30:00Z",
  "last_update_at": "2026-04-25T09:32:14Z",
  "entries_so_far": int        # nur als Hinweis; echter Commit am Ende
}

Geschrieben in eigener DB-Session pro Update (siehe
PricelistParser._update_progress), damit der Parser-Hauptprozess die
Transaction nicht zwischendurch committen muss.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4b1e7c30982"
down_revision: Union[str, Sequence[str], None] = "d5e8c3a91f24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("lvp_supplier_pricelists") as batch_op:
        batch_op.add_column(
            sa.Column("parse_progress", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("lvp_supplier_pricelists") as batch_op:
        batch_op.drop_column("parse_progress")
