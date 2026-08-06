"""runbooks, runbook_chunks, historical_incidents, hypothesis critique fields

Revision ID: 006
Revises: 005
Create Date: 2026-08-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    op.create_table(
        "runbooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_path", sa.String(length=500), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_runbooks_source_path", "runbooks", ["source_path", "is_current"])
    op.create_index("ux_runbooks_checksum_current", "runbooks", ["checksum"], unique=True)

    op.execute(
        f"""
        CREATE TABLE runbook_chunks (
            id uuid PRIMARY KEY,
            runbook_id uuid NOT NULL REFERENCES runbooks(id) ON DELETE CASCADE,
            chunk_index int NOT NULL,
            heading_path text NOT NULL,
            content text NOT NULL,
            content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('spanish', content)) STORED,
            embedding vector({EMBEDDING_DIM}) NOT NULL,
            model_name text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_runbook_chunks_runbook ON runbook_chunks (runbook_id, chunk_index)"
    )
    op.execute(
        "CREATE INDEX ix_runbook_chunks_embedding ON runbook_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX ix_runbook_chunks_tsv ON runbook_chunks USING gin (content_tsv)")

    op.create_table(
        "historical_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("service_name", sa.String(length=200), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("resolution", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        f"""
        ALTER TABLE historical_incidents
        ADD COLUMN search_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('spanish', search_text)) STORED
        """
    )
    op.execute(
        f"""
        ALTER TABLE historical_incidents
        ADD COLUMN embedding vector({EMBEDDING_DIM}) NOT NULL
        """
    )
    op.execute(
        "ALTER TABLE historical_incidents ADD COLUMN model_name text NOT NULL DEFAULT 'unknown'"
    )
    op.execute(
        "CREATE INDEX ix_historical_incidents_embedding ON historical_incidents "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_historical_incidents_tsv ON historical_incidents USING gin (search_tsv)"
    )

    op.add_column(
        "hypotheses",
        sa.Column(
            "confidence_breakdown",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "hypotheses",
        sa.Column("grounding", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "hypotheses",
        sa.Column("critic_verdict", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "hypotheses",
        sa.Column("assumptions", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "hypotheses",
        sa.Column(
            "missing_evidence",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "hypotheses",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "hypotheses",
        sa.Column("hypothesis_type", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("hypotheses", "hypothesis_type")
    op.drop_column("hypotheses", "rejection_reason")
    op.drop_column("hypotheses", "missing_evidence")
    op.drop_column("hypotheses", "assumptions")
    op.drop_column("hypotheses", "critic_verdict")
    op.drop_column("hypotheses", "grounding")
    op.drop_column("hypotheses", "confidence_breakdown")

    op.drop_index("ix_historical_incidents_tsv", table_name="historical_incidents")
    op.drop_index("ix_historical_incidents_embedding", table_name="historical_incidents")
    op.drop_table("historical_incidents")

    op.drop_index("ix_runbook_chunks_tsv", table_name="runbook_chunks")
    op.drop_index("ix_runbook_chunks_embedding", table_name="runbook_chunks")
    op.drop_index("ix_runbook_chunks_runbook", table_name="runbook_chunks")
    op.drop_table("runbook_chunks")

    op.drop_index("ux_runbooks_checksum_current", table_name="runbooks")
    op.drop_index("ix_runbooks_source_path", table_name="runbooks")
    op.drop_table("runbooks")
