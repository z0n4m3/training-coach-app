"""M6 deterministic session analyses

Revision ID: 0004_session_analyses
Revises: 0003_session_matches
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_session_analyses"
down_revision: Union[str, None] = "0003_session_matches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_analyses",
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
            "canonical_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "canonical_sessions.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "planned_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "planned_sessions.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column(
            "analysis_version",
            sa.String(64),
            nullable=False,
            server_default="deterministic-v1",
        ),
        sa.Column(
            "classification",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "flags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
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
            "canonical_session_id",
            name="uq_session_analysis_canonical",
        ),
    )

    op.create_index(
        "ix_session_analyses_athlete_id",
        "session_analyses",
        ["athlete_id"],
    )
    op.create_index(
        "ix_session_analyses_canonical_session_id",
        "session_analyses",
        ["canonical_session_id"],
    )
    op.create_index(
        "ix_session_analyses_planned_session_id",
        "session_analyses",
        ["planned_session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_session_analyses_planned_session_id",
        table_name="session_analyses",
    )
    op.drop_index(
        "ix_session_analyses_canonical_session_id",
        table_name="session_analyses",
    )
    op.drop_index(
        "ix_session_analyses_athlete_id",
        table_name="session_analyses",
    )
    op.drop_table("session_analyses")
