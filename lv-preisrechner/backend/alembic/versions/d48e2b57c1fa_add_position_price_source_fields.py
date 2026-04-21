"""add position price source aggregation fields (B+4.2)

Revision ID: d48e2b57c1fa
Revises: c3a42fb05e91
Create Date: 2026-04-21 09:30:00.000000

Ergaenzt `lvp_positions` um zwei Aggregat-Felder:
- needs_price_review (Boolean, default False) — True wenn mindestens ein
  Material der Position needs_review=True liefert.
- price_source_summary (String 300, default "") — Text-Zusammenfassung der
  Preisquellen, z. B. "2x supplier_price, 1x override".

Diese Felder werden von der neuen Pricing-Pipeline (B+4.1/B+4.2) gesetzt
und erlauben der UI, Positionen mit Review-Bedarf schnell zu filtern.

Im Legacy-Pfad (Flag=False) werden die Felder mit Default-Werten gefuellt
(needs_price_review=False / price_source_summary="1x legacy, ..."). Keine
Auswirkung auf bestehende Kalkulations-Ergebnisse.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d48e2b57c1fa"
down_revision: Union[str, Sequence[str], None] = "c3a42fb05e91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("lvp_positions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "needs_price_review",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "price_source_summary",
                sa.String(length=300),
                nullable=False,
                server_default="",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("lvp_positions") as batch_op:
        batch_op.drop_column("price_source_summary")
        batch_op.drop_column("needs_price_review")
