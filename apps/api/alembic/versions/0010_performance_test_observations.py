"""Multi-source performance test observations

Revision ID: 0010_test_obs
Revises: 0009_source_profiles
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0010_test_obs"

down_revision: Union[
    str,
    None,
] = "0009_source_profiles"

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
        "performance_tests",
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
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column(
            "training_setup_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "training_setups.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column(
            "sport",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "discipline",
            sa.String(32),
            nullable=True,
        ),
        sa.Column(
            "environment",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "test_type",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "protocol",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "tested_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "protocol_data",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),
        sa.Column(
            "notes",
            sa.Text(),
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
        "ix_performance_tests_athlete_id",
        "performance_tests",
        ["athlete_id"],
    )

    op.create_index(
        "ix_performance_tests_session_id",
        "performance_tests",
        ["canonical_session_id"],
    )

    op.create_index(
        "ix_performance_tests_setup_id",
        "performance_tests",
        ["training_setup_id"],
    )

    op.create_index(
        "ix_performance_tests_tested_at",
        "performance_tests",
        ["tested_at"],
    )

    op.create_table(
        "performance_test_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "performance_test_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "performance_tests.id",
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
            "power_source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "devices.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "observed_power_w",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "measurement_window_s",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "estimated_ftp_w",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "estimate_method",
            sa.String(32),
            nullable=False,
            server_default="none",
        ),
        sa.Column(
            "confidence",
            sa.String(16),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "derivation",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),
        sa.Column(
            "metrics",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "performance_test_id",
            "power_source_id",
            name=(
                "uq_performance_test_"
                "power_source"
            ),
        ),
    )

    op.create_index(
        "ix_test_results_test_id",
        "performance_test_results",
        ["performance_test_id"],
    )

    op.create_index(
        "ix_test_results_athlete_id",
        "performance_test_results",
        ["athlete_id"],
    )

    op.create_index(
        "ix_test_results_power_source_id",
        "performance_test_results",
        ["power_source_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_test_results_power_source_id",
        table_name=
            "performance_test_results",
    )

    op.drop_index(
        "ix_test_results_athlete_id",
        table_name=
            "performance_test_results",
    )

    op.drop_index(
        "ix_test_results_test_id",
        table_name=
            "performance_test_results",
    )

    op.drop_table(
        "performance_test_results"
    )

    op.drop_index(
        "ix_performance_tests_tested_at",
        table_name="performance_tests",
    )

    op.drop_index(
        "ix_performance_tests_setup_id",
        table_name="performance_tests",
    )

    op.drop_index(
        "ix_performance_tests_session_id",
        table_name="performance_tests",
    )

    op.drop_index(
        "ix_performance_tests_athlete_id",
        table_name="performance_tests",
    )

    op.drop_table(
        "performance_tests"
    )
