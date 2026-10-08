"""Coach decisions

Revision ID: 0014_coach_decisions
Revises: 0013_weekly_reviews
"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0014_coach_decisions"

down_revision: Union[
    str,
    None,
] = "0013_weekly_reviews"

branch_labels: Union[
    str,
    Sequence[str],
    None,
] = None

depends_on: Union[
    str,
    Sequence[str],
    None,
] = None


def upgrade() -> None:
    op.create_table(
        "coach_decisions",

        sa.Column(
            "id",
            postgresql.UUID(
                as_uuid=True
            ),
            primary_key=True,
        ),

        sa.Column(
            "athlete_id",
            postgresql.UUID(
                as_uuid=True
            ),
            sa.ForeignKey(
                "athletes.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "training_week_id",
            postgresql.UUID(
                as_uuid=True
            ),
            sa.ForeignKey(
                "training_weeks.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "weekly_review_id",
            postgresql.UUID(
                as_uuid=True
            ),
            sa.ForeignKey(
                "weekly_reviews.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "decision_version",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "input_hash",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
        ),

        sa.Column(
            "decision",
            sa.String(32),
            nullable=True,
        ),

        sa.Column(
            "confidence",
            sa.String(16),
            nullable=False,
        ),

        sa.Column(
            "selected_rule",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "reasons",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'[]'::jsonb"
            ),
        ),

        sa.Column(
            "evidence",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),

        sa.Column(
            "constraints",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),

        sa.Column(
            "source_review_version",
            sa.String(64),
            nullable=False,
        ),

        sa.Column(
            "source_review_generated_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
        ),

        sa.Column(
            "generated_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
        ),

        sa.UniqueConstraint(
            "training_week_id",
            "decision_version",
            "input_hash",
            name=(
                "uq_coach_decision_"
                "week_version_input"
            ),
        ),
    )

    op.create_index(
        "ix_coach_decisions_athlete",
        "coach_decisions",
        ["athlete_id"],
    )

    op.create_index(
        "ix_coach_decisions_week",
        "coach_decisions",
        ["training_week_id"],
    )

    op.create_index(
        "ix_coach_decisions_review",
        "coach_decisions",
        ["weekly_review_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_coach_decisions_review",
        table_name="coach_decisions",
    )

    op.drop_index(
        "ix_coach_decisions_week",
        table_name="coach_decisions",
    )

    op.drop_index(
        "ix_coach_decisions_athlete",
        table_name="coach_decisions",
    )

    op.drop_table(
        "coach_decisions"
    )
