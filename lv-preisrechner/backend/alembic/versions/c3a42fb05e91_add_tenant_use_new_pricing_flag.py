"""add tenant use_new_pricing feature flag (B+4.1)

Revision ID: c3a42fb05e91
Revises: a1f0d7c89b2e
Create Date: 2026-04-21 08:30:00.000000

Ergaenzt `lvp_tenants.use_new_pricing` als boolesches Feature-Flag.
Default False fuer alle bestehenden und neuen Tenants. Das Flag steuert
zukuenftig die Entscheidung ob die Kalkulation ueber das neue
SupplierPriceEntry-Modell oder die alte PriceEntry-Pipeline laeuft.

In diesem Sub-Block wird das Flag nur DB-seitig angelegt und im Model
exponiert -- die Integration in die Kalkulation folgt in B+4.2.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3a42fb05e91"
down_revision: Union[str, Sequence[str], None] = "a1f0d7c89b2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Neue Spalte mit server_default "false" -- dadurch bekommen bestehende
    # Zeilen automatisch False. Nach dem Backfill koennte man den Default
    # entfernen; fuer SQLite ist das jedoch unnoetig (keine ALTER DEFAULT-Syntax).
    with op.batch_alter_table("lvp_tenants") as batch_op:
        batch_op.add_column(
            sa.Column(
                "use_new_pricing",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("lvp_tenants") as batch_op:
        batch_op.drop_column("use_new_pricing")
