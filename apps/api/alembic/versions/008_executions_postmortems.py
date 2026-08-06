"""action_executions, approval execution fields, postmortems

Revision ID: 008
Revises: 007
Create Date: 2026-08-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "approvals",
        sa.Column("parameters_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "approvals",
        sa.Column(
            "execution_consumed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_table(
        "action_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "proposed_action_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("proposed_actions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "approval_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("approvals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("execution_status", sa.String(length=32), nullable=False),
        sa.Column(
            "input_payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("output_payload", postgresql.JSONB(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_action_executions_incident",
        "action_executions",
        ["incident_id", "started_at"],
    )
    op.create_index(
        "ix_action_executions_idempotency",
        "action_executions",
        ["idempotency_key"],
        unique=True,
    )

    op.create_table(
        "postmortems",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "invalid_references",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_by",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'agent'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_postmortems_incident_version",
        "postmortems",
        ["incident_id", "version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_postmortems_incident_version", table_name="postmortems")
    op.drop_table("postmortems")
    op.drop_index("ix_action_executions_idempotency", table_name="action_executions")
    op.drop_index("ix_action_executions_incident", table_name="action_executions")
    op.drop_table("action_executions")
    op.drop_column("approvals", "execution_consumed")
    op.drop_column("approvals", "parameters_hash")
