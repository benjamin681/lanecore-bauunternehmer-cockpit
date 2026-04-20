"""add is_bedarf and is_alternative to position, plus optional-sum fields to lv

Revision ID: 8f2c1a9b4d01
Revises: 074b144a36ad
Create Date: 2026-04-20 10:45:00.000000

Optional-Positionen (Bedarf/Alternative) werden aus der Angebotssumme
ausgeschlossen — die Position bleibt aber im Output sichtbar.

lvp_positions:
- is_bedarf      (Boolean, default false)
- is_alternative (Boolean, default false)

lvp_lvs (Summen separat ausweisen):
- bedarfspositionen_summe         (Float, default 0.0)
- alternativpositionen_summe      (Float, default 0.0)
- gesamtsumme_inklusive_optional  (Float, default 0.0)

server_default stellt sicher, dass bestehende Daten weiter funktionieren.

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
    # Position-Flags
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
    # LV-Summen
    op.add_column(
        "lvp_lvs",
        sa.Column(
            "bedarfspositionen_summe",
            sa.Float(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "lvp_lvs",
        sa.Column(
            "alternativpositionen_summe",
            sa.Float(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "lvp_lvs",
        sa.Column(
            "gesamtsumme_inklusive_optional",
            sa.Float(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("lvp_lvs", "gesamtsumme_inklusive_optional")
    op.drop_column("lvp_lvs", "alternativpositionen_summe")
    op.drop_column("lvp_lvs", "bedarfspositionen_summe")
    op.drop_column("lvp_positions", "is_alternative")
    op.drop_column("lvp_positions", "is_bedarf")
