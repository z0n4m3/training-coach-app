"""M4 plan domain

Revision ID: 0002_plan_domain
Revises: 0001_m0_m1_core
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_plan_domain"
down_revision: Union[str, None] = "0001_m0_m1_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seasons",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "athlete_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("athletes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="planning",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_seasons_athlete_id",
        "seasons",
        ["athlete_id"],
    )

    op.create_table(
        "goal_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "season_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "athlete_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("athletes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "event_start_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.String(16),
            nullable=False,
            server_default="A",
        ),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("target_time_s", sa.Float(), nullable=True),
        sa.Column("goal_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_goal_events_season_id",
        "goal_events",
        ["season_id"],
    )
    op.create_index(
        "ix_goal_events_athlete_id",
        "goal_events",
        ["athlete_id"],
    )

    op.create_table(
        "macrocycles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "season_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("seasons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "athlete_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("athletes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="planned",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "season_id",
            "sequence",
            name="uq_macrocycle_season_sequence",
        ),
    )
    op.create_index(
        "ix_macrocycles_season_id",
        "macrocycles",
        ["season_id"],
    )
    op.create_index(
        "ix_macrocycles_athlete_id",
        "macrocycles",
        ["athlete_id"],
    )

    op.create_table(
        "training_weeks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "macrocycle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("macrocycles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "athlete_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("athletes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="planned",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "macrocycle_id",
            "week_number",
            name="uq_training_week_macrocycle_number",
        ),
        sa.UniqueConstraint(
            "athlete_id",
            "start_date",
            name="uq_training_week_athlete_start",
        ),
    )
    op.create_index(
        "ix_training_weeks_macrocycle_id",
        "training_weeks",
        ["macrocycle_id"],
    )
    op.create_index(
        "ix_training_weeks_athlete_id",
        "training_weeks",
        ["athlete_id"],
    )

    op.create_table(
        "planned_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "training_week_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("training_weeks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "athlete_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("athletes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "planned_start_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "sport",
            sa.String(64),
            nullable=False,
            server_default="cycling",
        ),
        sa.Column("session_type", sa.String(64), nullable=True),
        sa.Column(
            "priority",
            sa.String(16),
            nullable=False,
            server_default="SUPPORT",
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="planned",
        ),
        sa.Column("planned_duration_s", sa.Float(), nullable=True),
        sa.Column("planned_distance_m", sa.Float(), nullable=True),
        sa.Column(
            "targets",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "workout_structure",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "intervals_event_id",
            sa.String(128),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_planned_sessions_training_week_id",
        "planned_sessions",
        ["training_week_id"],
    )
    op.create_index(
        "ix_planned_sessions_athlete_id",
        "planned_sessions",
        ["athlete_id"],
    )
    op.create_index(
        "ix_planned_sessions_planned_start_at",
        "planned_sessions",
        ["planned_start_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_planned_sessions_planned_start_at",
        table_name="planned_sessions",
    )
    op.drop_index(
        "ix_planned_sessions_athlete_id",
        table_name="planned_sessions",
    )
    op.drop_index(
        "ix_planned_sessions_training_week_id",
        table_name="planned_sessions",
    )
    op.drop_table("planned_sessions")

    op.drop_index(
        "ix_training_weeks_athlete_id",
        table_name="training_weeks",
    )
    op.drop_index(
        "ix_training_weeks_macrocycle_id",
        table_name="training_weeks",
    )
    op.drop_table("training_weeks")

    op.drop_index(
        "ix_macrocycles_athlete_id",
        table_name="macrocycles",
    )
    op.drop_index(
        "ix_macrocycles_season_id",
        table_name="macrocycles",
    )
    op.drop_table("macrocycles")

    op.drop_index(
        "ix_goal_events_athlete_id",
        table_name="goal_events",
    )
    op.drop_index(
        "ix_goal_events_season_id",
        table_name="goal_events",
    )
    op.drop_table("goal_events")

    op.drop_index(
        "ix_seasons_athlete_id",
        table_name="seasons",
    )
    op.drop_table("seasons")
