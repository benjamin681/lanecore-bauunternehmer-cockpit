"""Initial schema: projekte, analyse_jobs, analyse_ergebnisse.

Revision ID: 001
Revises: None
Create Date: 2026-04-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Projekte
    op.create_table(
        "projekte",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("auftraggeber", sa.String(255)),
        sa.Column("beschreibung", sa.String(2000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Analyse Jobs
    op.create_table(
        "analyse_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("projekt_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projekte.id"), index=True, nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text),
        sa.Column("model_used", sa.String(100)),
        sa.Column("input_tokens", sa.Integer),
        sa.Column("output_tokens", sa.Integer),
        sa.Column("cost_usd", sa.Numeric(10, 6)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Analyse Ergebnisse
    op.create_table(
        "analyse_ergebnisse",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("analyse_jobs.id"), unique=True, nullable=False),
        sa.Column("plantyp", sa.String(50)),
        sa.Column("massstab", sa.String(20)),
        sa.Column("geschoss", sa.String(100)),
        sa.Column("konfidenz", sa.Numeric(4, 3)),
        sa.Column("raeume", postgresql.JSONB),
        sa.Column("waende", postgresql.JSONB),
        sa.Column("decken", postgresql.JSONB),
        sa.Column("oeffnungen", postgresql.JSONB),
        sa.Column("details", postgresql.JSONB),
        sa.Column("gestrichene_positionen", postgresql.JSONB),
        sa.Column("warnungen", postgresql.JSONB),
        sa.Column("raw_claude_response", sa.Text),
        sa.Column("prompt_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("analyse_ergebnisse")
    op.drop_table("analyse_jobs")
    op.drop_table("projekte")
