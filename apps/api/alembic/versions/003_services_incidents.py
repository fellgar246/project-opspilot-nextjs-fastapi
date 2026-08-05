"""services, incidents, evidence, hypotheses

Revision ID: 003
Revises: 002
Create Date: 2026-08-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("repository", sa.String(length=500), nullable=True),
        sa.Column(
            "environment",
            sa.Enum("production", "staging", "demo", name="service_environment", native_enum=False),
            nullable=False,
        ),
        sa.Column("owner_team", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("sev1", "sev2", "sev3", "sev4", name="incident_severity", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "investigating",
                "mitigating",
                "monitoring",
                "resolved",
                "closed",
                name="incident_status",
                native_enum=False,
            ),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column(
            "source",
            sa.Enum("manual", "alert", "simulator", name="incident_source", native_enum=False),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
    op.create_index("ix_incidents_started_at", "incidents", ["started_at", "id"])
    op.create_index("ix_incidents_status_sev", "incidents", ["status", "severity"])

    op.create_table(
        "incident_services",
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        ),
    )
    op.create_index("ix_incident_services_svc", "incident_services", ["service_id"])

    op.create_table(
        "incident_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False, server_default=sa.text("'user'")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_incident_notes_incident_id", "incident_notes", ["incident_id"])

    op.create_table(
        "incident_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False, server_default=sa.text("'user'")),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_incident_status_history_incident_id",
        "incident_status_history",
        ["incident_id"],
    )

    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_type",
            sa.Enum(
                "metric",
                "log",
                "deployment",
                "commit",
                "pull_request",
                "feature_flag",
                "runbook",
                "similar_incident",
                "note",
                name="evidence_source_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "structured_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_evidence_incident", "evidence", ["incident_id", "observed_at"])
    op.create_index(
        "ux_evidence_dedup",
        "evidence",
        ["incident_id", "source_type", "source_reference", "checksum"],
        unique=True,
    )

    op.create_table(
        "hypotheses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("proposed", "accepted", "rejected", name="hypothesis_status", native_enum=False),
            nullable=False,
            server_default=sa.text("'proposed'"),
        ),
        sa.Column(
            "supporting_evidence",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
        sa.Column(
            "contradicting_evidence",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
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
    op.create_index("ix_hypotheses_incident", "hypotheses", ["incident_id", "confidence"])


def downgrade() -> None:
    op.drop_table("hypotheses")
    op.drop_table("evidence")
    op.drop_table("incident_status_history")
    op.drop_table("incident_notes")
    op.drop_table("incident_services")
    op.drop_table("incidents")
    op.drop_table("services")
    op.execute("DROP TYPE IF EXISTS hypothesis_status")
    op.execute("DROP TYPE IF EXISTS evidence_source_type")
    op.execute("DROP TYPE IF EXISTS incident_source")
    op.execute("DROP TYPE IF EXISTS incident_status")
    op.execute("DROP TYPE IF EXISTS incident_severity")
    op.execute("DROP TYPE IF EXISTS service_environment")
