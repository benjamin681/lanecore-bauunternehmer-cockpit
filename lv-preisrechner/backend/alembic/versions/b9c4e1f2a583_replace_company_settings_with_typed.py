"""replace tenant.company_settings JSON with typed business-profile columns

Revision ID: b9c4e1f2a583
Revises: e7a8d2c5b14f
Create Date: 2026-04-25 11:00:00.000000

B+4.9 — Foundation des Vertriebs-Workflows. Das in B+4.8 angelegte
JSON-Feld lvp_tenants.company_settings wird durch typisierte
Einzelspalten ersetzt, damit:
- Pydantic-Validierung pro Feld greift (IBAN-/BIC-/VAT-Format).
- Frontend-Form auf typisiertem Schema basiert.
- PDF-Export-Service ohne dict-Lookups arbeitet.

Risikoanalyse: Kein produktiver Inhalt im JSON-Feld — der einzige
Schreiber war ein Test-Skript fuer den Salach-PDF-Export. Die
Migration dropt company_settings ohne Datenkopie und legt die neuen
Spalten leer an. Das PDF-Service-Refactor erfolgt im selben Commit.

Default-Werte:
- company_address_country = 'DE'
- default_payment_terms_days = 14
- default_offer_validity_days = 30
- default_agb_text = Standard-AGB-Hinweis fuer Trockenbau-Betriebe.

Alle anderen Felder bleiben nullable, damit Tenants existieren
koennen ohne sofort vollstaendiges Profil.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9c4e1f2a583"
down_revision: Union[str, Sequence[str], None] = "e7a8d2c5b14f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DEFAULT_AGB_TEXT = (
    "Es gelten unsere Allgemeinen Geschaeftsbedingungen. "
    "Zahlungsbedingungen: 14 Tage netto ab Rechnungsdatum, ohne Abzug. "
    "Skonto und Boni nur nach gesonderter Vereinbarung."
)


def upgrade() -> None:
    with op.batch_alter_table("lvp_tenants") as batch_op:
        # Drop des in B+4.8 angelegten JSON-Felds — kein Datenverlust,
        # weil das Feld nur vom Test-Skript befuellt wurde.
        batch_op.drop_column("company_settings")

        # Geschaefts-Profil
        batch_op.add_column(sa.Column("company_name", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("company_address_street", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("company_address_zip", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("company_address_city", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column(
                "company_address_country",
                sa.String(length=2),
                nullable=False,
                server_default="DE",
            )
        )

        # Steuer / Rechtliches
        batch_op.add_column(sa.Column("tax_id", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("vat_id", sa.String(length=20), nullable=True))

        # Bank
        batch_op.add_column(sa.Column("bank_iban", sa.String(length=34), nullable=True))
        batch_op.add_column(sa.Column("bank_bic", sa.String(length=11), nullable=True))
        batch_op.add_column(sa.Column("bank_name", sa.String(length=120), nullable=True))

        # Branding / PDF-Footer
        batch_op.add_column(sa.Column("logo_url", sa.String(length=500), nullable=True))
        batch_op.add_column(
            sa.Column(
                "default_payment_terms_days",
                sa.Integer(),
                nullable=False,
                server_default="14",
            )
        )
        batch_op.add_column(
            sa.Column(
                "default_offer_validity_days",
                sa.Integer(),
                nullable=False,
                server_default="30",
            )
        )
        batch_op.add_column(
            sa.Column(
                "default_agb_text",
                sa.Text(),
                nullable=True,
                server_default=_DEFAULT_AGB_TEXT,
            )
        )
        batch_op.add_column(sa.Column("signature_text", sa.Text(), nullable=True))

    # E-Mail/Telefon koennten auch hier wandern — User-Profil-Felder sind
    # bewusst NICHT betroffen (lvp_users.email + .telefon bleiben unangetastet,
    # weil es da pro User unterschiedliche Werte geben kann).


def downgrade() -> None:
    with op.batch_alter_table("lvp_tenants") as batch_op:
        for col in (
            "signature_text",
            "default_agb_text",
            "default_offer_validity_days",
            "default_payment_terms_days",
            "logo_url",
            "bank_name",
            "bank_bic",
            "bank_iban",
            "vat_id",
            "tax_id",
            "company_address_country",
            "company_address_city",
            "company_address_zip",
            "company_address_street",
            "company_name",
        ):
            batch_op.drop_column(col)
        batch_op.add_column(sa.Column("company_settings", sa.JSON(), nullable=True))
