"""Source-aware performance profiles

Revision ID: 0009_source_profiles
Revises: 0008_session_setup_context
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0009_source_profiles"
down_revision: Union[str, None] = (
    "0008_session_setup_context"
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
    op.add_column(
        "sport_profiles",
        sa.Column(
            "discipline",
            sa.String(32),
            nullable=True,
        ),
    )

    op.add_column(
        "sport_profiles",
        sa.Column(
            "environment",
            sa.String(32),
            nullable=True,
        ),
    )

    op.add_column(
        "sport_profiles",
        sa.Column(
            "power_source_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.add_column(
        "sport_profiles",
        sa.Column(
            "profile_key",
            sa.String(255),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE sport_profiles
        SET
            environment = context,
            profile_key =
                sport || '|*|' ||
                context || '|*'
        """
    )

    op.alter_column(
        "sport_profiles",
        "environment",
        nullable=False,
    )

    op.alter_column(
        "sport_profiles",
        "profile_key",
        nullable=False,
    )

    op.drop_constraint(
        "uq_sport_profile_athlete_sport_context",
        "sport_profiles",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_sport_profile_athlete_key",
        "sport_profiles",
        [
            "athlete_id",
            "profile_key",
        ],
    )

    op.create_foreign_key(
        "fk_sport_profiles_power_source_id",
        "sport_profiles",
        "devices",
        ["power_source_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_index(
        "ix_sport_profiles_power_source_id",
        "sport_profiles",
        ["power_source_id"],
    )


def downgrade() -> None:
    # Source- and discipline-specific profiles
    # cannot be represented by the old model.
    # Removing them makes the downgrade
    # deterministic and restores the old
    # athlete/sport/context uniqueness.
    op.execute(
        """
        DELETE FROM sport_profiles
        WHERE
            discipline IS NOT NULL
            OR power_source_id IS NOT NULL
        """
    )

    op.drop_index(
        "ix_sport_profiles_power_source_id",
        table_name="sport_profiles",
    )

    op.drop_constraint(
        "fk_sport_profiles_power_source_id",
        "sport_profiles",
        type_="foreignkey",
    )

    op.drop_constraint(
        "uq_sport_profile_athlete_key",
        "sport_profiles",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_sport_profile_athlete_sport_context",
        "sport_profiles",
        [
            "athlete_id",
            "sport",
            "context",
        ],
    )

    op.drop_column(
        "sport_profiles",
        "profile_key",
    )
    op.drop_column(
        "sport_profiles",
        "power_source_id",
    )
    op.drop_column(
        "sport_profiles",
        "environment",
    )
    op.drop_column(
        "sport_profiles",
        "discipline",
    )
