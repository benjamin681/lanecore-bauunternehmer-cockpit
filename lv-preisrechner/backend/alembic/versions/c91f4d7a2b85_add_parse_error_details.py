"""add parse_error_details (JSON) to supplier_pricelists

Revision ID: c91f4d7a2b85
Revises: b72fa1c8d903
Create Date: 2026-04-24 19:00:00.000000

Der Parser kann Teilausfaelle haben (ein Batch á 3 Seiten faellt wegen
ungueltigem JSON weg, andere laufen). Das bisherige `parse_error`-
String-Feld haelt nur eine Fehlermeldung. Fuer Observability und
Post-Mortem brauchen wir eine strukturierte Liste — welche Batches,
welche Seiten, welche Exception-Klasse, welcher Attempt, wie viele
Retries ausgeloest.

Das neue `parse_error_details`-JSON-Feld haelt eine Liste von dicts
wie:
[
  {
    "batch_idx": 4,
    "page_range": "10-12",
    "attempts": 3,
    "error_class": "ValueError",
    "error_message": "Claude gab kein gueltiges JSON: ...",
    "raw_response_file": "/home/appuser/storage/parse_logs/{pid}/batch_4_attempt_3.txt"
  },
  ...
]

Additiv, nullable, keine Daten-Migration noetig.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c91f4d7a2b85"
down_revision: Union[str, Sequence[str], None] = "b72fa1c8d903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("lvp_supplier_pricelists") as batch_op:
        batch_op.add_column(
            sa.Column("parse_error_details", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("lvp_supplier_pricelists") as batch_op:
        batch_op.drop_column("parse_error_details")
