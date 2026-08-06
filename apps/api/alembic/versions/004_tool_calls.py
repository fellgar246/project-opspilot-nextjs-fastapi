"""tool_calls audit table

Revision ID: 004
Revises: 003
Create Date: 2026-08-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("tool_version", sa.String(length=32), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_summary", sa.String(length=4000), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="low"),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_tool_calls_incident", "tool_calls", ["incident_id", "created_at"])
    op.create_index("ix_tool_calls_incident_id", "tool_calls", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_tool_calls_incident_id", table_name="tool_calls")
    op.drop_index("ix_tool_calls_incident", table_name="tool_calls")
    op.drop_table("tool_calls")
