"""M0/M1 core schema

Revision ID: 0001_m0_m1_core
Revises:
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_m0_m1_core"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=True, unique=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Europe/Warsaw"),
        sa.Column("locale", sa.String(16), nullable=False, server_default="pl-PL"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "athletes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("primary_sport", sa.String(64), nullable=False, server_default="cycling"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "external_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_athlete_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("athlete_id", "provider", name="uq_connection_athlete_provider"),
    )

    op.create_table(
        "source_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_activity_id", sa.String(128), nullable=False),
        sa.Column("recording_source", sa.String(128), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("sport", sa.String(64), nullable=False),
        sa.Column("indoor", sa.Boolean(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("avg_power_w", sa.Float(), nullable=True),
        sa.Column("normalized_power_w", sa.Float(), nullable=True),
        sa.Column("avg_hr_bpm", sa.Float(), nullable=True),
        sa.Column("max_hr_bpm", sa.Float(), nullable=True),
        sa.Column("avg_cadence_rpm", sa.Float(), nullable=True),
        sa.Column("work_kj", sa.Float(), nullable=True),
        sa.Column("training_load", sa.Float(), nullable=True),
        sa.Column("paired_event_id", sa.String(128), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("athlete_id", "provider", "provider_activity_id", name="uq_source_activity_provider_id"),
    )
    op.create_index("ix_source_activities_athlete_start", "source_activities", ["athlete_id", "start_at"])

    op.create_table(
        "canonical_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sport", sa.String(64), nullable=False),
        sa.Column("indoor", sa.Boolean(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("elevation_m", sa.Float(), nullable=True),
        sa.Column("avg_power_w", sa.Float(), nullable=True),
        sa.Column("normalized_power_w", sa.Float(), nullable=True),
        sa.Column("avg_hr_bpm", sa.Float(), nullable=True),
        sa.Column("max_hr_bpm", sa.Float(), nullable=True),
        sa.Column("avg_cadence_rpm", sa.Float(), nullable=True),
        sa.Column("work_kj", sa.Float(), nullable=True),
        sa.Column("training_load", sa.Float(), nullable=True),
        sa.Column("duplicate_status", sa.String(32), nullable=False),
        sa.Column("analysis_level", sa.String(32), nullable=False, server_default="basic"),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("athlete_id", "fingerprint", name="uq_canonical_athlete_fingerprint"),
    )
    op.create_index("ix_canonical_sessions_athlete_start", "canonical_sessions", ["athlete_id", "start_at"])

    op.create_table(
        "canonical_session_sources",
        sa.Column("canonical_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("canonical_sessions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_activities.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("duplicate_score", sa.Float(), nullable=True),
        sa.Column("manual_override", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "session_metric_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("canonical_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_name", sa.String(64), nullable=False),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("value_text", sa.String(255), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("source_activity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("selection_reason", sa.String(255), nullable=False),
        sa.UniqueConstraint("canonical_session_id", "metric_name", name="uq_canonical_metric"),
    )

    op.create_table(
        "sync_state",
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("resource", sa.String(64), primary_key=True),
        sa.Column("last_successful_sync", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cursor", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="idle"),
    )

    op.create_table(
        "webhook_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("provider", "event_hash", name="uq_webhook_provider_hash"),
    )


def downgrade() -> None:
    op.drop_table("webhook_receipts")
    op.drop_table("sync_state")
    op.drop_table("session_metric_sources")
    op.drop_table("canonical_session_sources")
    op.drop_index("ix_canonical_sessions_athlete_start", table_name="canonical_sessions")
    op.drop_table("canonical_sessions")
    op.drop_index("ix_source_activities_athlete_start", table_name="source_activities")
    op.drop_table("source_activities")
    op.drop_table("external_connections")
    op.drop_table("athletes")
    op.drop_table("users")
