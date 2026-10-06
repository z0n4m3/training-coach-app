"""Weekly reviews

Revision ID: 0013_weekly_reviews
Revises: 0012_session_feedback
"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0013_weekly_reviews"

down_revision: Union[
    str,
    None,
] = "0012_session_feedback"

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
        "weekly_reviews",
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
            "review_version",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "summary",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),
        sa.Column(
            "flags",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'[]'::jsonb"
            ),
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
        sa.Column(
            "updated_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "training_week_id",
            name=(
                "uq_weekly_review_"
                "training_week"
            ),
        ),
    )

    op.create_index(
        "ix_weekly_reviews_athlete",
        "weekly_reviews",
        ["athlete_id"],
    )

    op.create_index(
        "ix_weekly_reviews_week",
        "weekly_reviews",
        ["training_week_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_weekly_reviews_week",
        table_name="weekly_reviews",
    )

    op.drop_index(
        "ix_weekly_reviews_athlete",
        table_name="weekly_reviews",
    )

    op.drop_table(
        "weekly_reviews"
    )
