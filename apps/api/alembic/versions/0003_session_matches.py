"""M5 session matches

Revision ID: 0003_session_matches
Revises: 0002_plan_domain
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_session_matches"
down_revision: Union[str, None] = "0002_plan_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_matches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "athlete_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "athletes.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "planned_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "planned_sessions.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "canonical_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "canonical_sessions.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "match_method",
            sa.String(32),
            nullable=False,
            server_default="auto",
        ),
        sa.Column(
            "match_score",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "match_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "manual_override",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
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
            "planned_session_id",
            name="uq_session_match_planned",
        ),
    )

    op.create_index(
        "ix_session_matches_athlete_id",
        "session_matches",
        ["athlete_id"],
    )

    op.create_index(
        "ix_session_matches_canonical_session_id",
        "session_matches",
        ["canonical_session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_session_matches_canonical_session_id",
        table_name="session_matches",
    )
    op.drop_index(
        "ix_session_matches_athlete_id",
        table_name="session_matches",
    )
    op.drop_table("session_matches")
