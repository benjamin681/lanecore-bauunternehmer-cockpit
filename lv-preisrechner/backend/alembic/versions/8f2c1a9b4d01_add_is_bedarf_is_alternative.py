"""add is_bedarf and is_alternative to position

Revision ID: 8f2c1a9b4d01
Revises: 074b144a36ad
Create Date: 2026-04-20 10:45:00.000000

Fuegt zwei Boolean-Flags zur lvp_positions-Tabelle hinzu:
- is_bedarf:      Position ist eine Bedarfsposition (LV-Marker "*** Bedarfsposition")
- is_alternative: Position ist eine Alternativposition (LV-Marker "Alternativprodukt")

Beide Flags schliessen Positionen aus der Angebotssumme aus (Kalkulation),
die Position bleibt aber im Output sichtbar.

server_default="false" stellt sicher, dass bestehende Positionen (z.B.
in bereits vorhandenen LVs) als "nicht Bedarf, nicht Alternative" eingestuft
werden - das ist das sichere Verhalten.

Migration wurde manuell verfasst (nicht via autogenerate) weil die lokale
SQLite-DB nicht mit der Head-Revision synchron war.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f2c1a9b4d01"
down_revision: Union[str, Sequence[str], None] = "074b144a36ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lvp_positions",
        sa.Column(
            "is_bedarf",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "lvp_positions",
        sa.Column(
            "is_alternative",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("lvp_positions", "is_alternative")
    op.drop_column("lvp_positions", "is_bedarf")
