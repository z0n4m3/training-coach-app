"""Session feedback

Revision ID: 0012_session_feedback
Revises: 0011_perf_proposals
"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0012_session_feedback"

down_revision: Union[
    str,
    None,
] = "0011_perf_proposals"

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
        "session_feedback",
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
            "canonical_session_id",
            postgresql.UUID(
                as_uuid=True
            ),
            sa.ForeignKey(
                "canonical_sessions.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "rpe",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "leg_fatigue",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "comment",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "custom_metrics",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
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
            "canonical_session_id",
            name=(
                "uq_session_feedback_"
                "canonical"
            ),
        ),
    )

    op.create_index(
        "ix_session_feedback_athlete",
        "session_feedback",
        ["athlete_id"],
    )

    op.create_index(
        "ix_session_feedback_canonical",
        "session_feedback",
        ["canonical_session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_session_feedback_canonical",
        table_name="session_feedback",
    )

    op.drop_index(
        "ix_session_feedback_athlete",
        table_name="session_feedback",
    )

    op.drop_table(
        "session_feedback"
    )
