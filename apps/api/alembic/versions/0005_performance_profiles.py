"""Versioned sport profiles and zone sets

Revision ID: 0005_performance_profiles
Revises: 0004_session_analyses
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_performance_profiles"
down_revision: Union[str, None] = (
    "0004_session_analyses"
)
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
        "sport_profiles",
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
            "sport",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "context",
            sa.String(32),
            nullable=False,
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
            "athlete_id",
            "sport",
            "context",
            name=(
                "uq_sport_profile_"
                "athlete_sport_context"
            ),
        ),
    )

    op.create_index(
        "ix_sport_profiles_athlete_id",
        "sport_profiles",
        ["athlete_id"],
    )

    op.create_table(
        "zone_sets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "sport_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "sport_profiles.id",
                ondelete="CASCADE",
            ),
            nullable=False,
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
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "ftp_w",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "threshold_hr_bpm",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "power_zones",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),
        sa.Column(
            "hr_zones",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),
        sa.Column(
            "source",
            sa.String(32),
            nullable=False,
            server_default="manual",
        ),
        sa.Column(
            "note",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "sport_profile_id",
            "effective_from",
            name=(
                "uq_zone_set_"
                "profile_effective_from"
            ),
        ),
    )

    op.create_index(
        "ix_zone_sets_sport_profile_id",
        "zone_sets",
        ["sport_profile_id"],
    )
    op.create_index(
        "ix_zone_sets_athlete_id",
        "zone_sets",
        ["athlete_id"],
    )
    op.create_index(
        "ix_zone_sets_effective_from",
        "zone_sets",
        ["effective_from"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_zone_sets_effective_from",
        table_name="zone_sets",
    )
    op.drop_index(
        "ix_zone_sets_athlete_id",
        table_name="zone_sets",
    )
    op.drop_index(
        "ix_zone_sets_sport_profile_id",
        table_name="zone_sets",
    )
    op.drop_table("zone_sets")

    op.drop_index(
        "ix_sport_profiles_athlete_id",
        table_name="sport_profiles",
    )
    op.drop_table("sport_profiles")
