"""defensive schema: widen currency column to varchar(10) to absorb parser noise

Revision ID: f8a2b3e91d04
Revises: d48e2b57c1fa
Create Date: 2026-04-24 15:20:00.000000

Hintergrund:
Der LLM-basierte Parser liefert in seltenen Faellen fuer die currency-
Spalte Werte wie "EURO", "Euro", "€/Sack" oder " EUR " (mit Whitespace).
Bisher war die Spalte `varchar(3) NOT NULL` und das ganze Insert einer
Preisliste rollte zurueck, sobald ein einziger Eintrag einen laengeren
Currency-Wert hatte — faktisch Totalausfall fuer den Parse-Durchlauf
obwohl 99% der Eintraege sauber waren.

Zweigleisige Abmilderung:
1. Schema: Spalte auf varchar(10) erweitern. Fasst EUR/USD/CHF/GBP und
   typische Parser-Artefakte und toleriert kuenftige Modell-Drifts.
2. Parser: in _build_entry wird der Wert zusaetzlich auf eine Whitelist
   normalisiert (EUR als Fallback) und der Rohwert in
   attributes["raw_currency"] fuer Debugging gespiegelt.

Die additive Erweiterung ist risk-less: keine Daten gehen verloren,
bestehende 'EUR'-Eintraege bleiben gueltig.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8a2b3e91d04"
down_revision: Union[str, Sequence[str], None] = "d48e2b57c1fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("lvp_supplier_price_entries") as batch_op:
        batch_op.alter_column(
            "currency",
            existing_type=sa.String(length=3),
            type_=sa.String(length=10),
            existing_nullable=False,
            existing_server_default="EUR",
        )


def downgrade() -> None:
    # Bei Downgrade koennten Werte > 3 Zeichen Truncation verursachen.
    # Wir erzwingen erst eine Normalisierung auf 'EUR' wo noetig, damit
    # das Rueckschrumpfen nicht haengen bleibt.
    op.execute(
        "UPDATE lvp_supplier_price_entries "
        "SET currency = 'EUR' WHERE LENGTH(currency) > 3"
    )
    with op.batch_alter_table("lvp_supplier_price_entries") as batch_op:
        batch_op.alter_column(
            "currency",
            existing_type=sa.String(length=10),
            type_=sa.String(length=3),
            existing_nullable=False,
            existing_server_default="EUR",
        )
