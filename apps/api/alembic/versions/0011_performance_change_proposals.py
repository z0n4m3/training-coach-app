"""Performance change proposals

Revision ID: 0011_perf_proposals
Revises: 0010_test_obs
"""

from typing import (
    Sequence,
    Union,
)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0011_perf_proposals"

down_revision: Union[
    str,
    None,
] = "0010_test_obs"

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
        "performance_change_proposals",
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
            "proposal_type",
            sa.String(32),
            nullable=False,
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
            "power_source_id",
            postgresql.UUID(
                as_uuid=True
            ),
            sa.ForeignKey(
                "devices.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "source_performance_test_id",
            postgresql.UUID(
                as_uuid=True
            ),
            sa.ForeignKey(
                "performance_tests.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "baseline_zone_set_id",
            postgresql.UUID(
                as_uuid=True
            ),
            sa.ForeignKey(
                "zone_sets.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column(
            "baseline_ftp_w",
            sa.Float(),
            nullable=True,
        ),
        sa.Column(
            "proposed_ftp_w",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.String(16),
            nullable=True,
        ),
        sa.Column(
            "recommended_effective_from",
            sa.DateTime(
                timezone=True
            ),
            nullable=False,
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
            "status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "decision_note",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "decided_at",
            sa.DateTime(
                timezone=True
            ),
            nullable=True,
        ),
        sa.Column(
            "applied_zone_set_id",
            postgresql.UUID(
                as_uuid=True
            ),
            sa.ForeignKey(
                "zone_sets.id",
                ondelete="SET NULL",
            ),
            nullable=True,
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
    )

    op.create_index(
        "ix_perf_proposals_athlete",
        "performance_change_proposals",
        ["athlete_id"],
    )

    op.create_index(
        "ix_perf_proposals_status",
        "performance_change_proposals",
        ["status"],
    )

    op.create_index(
        "ix_perf_proposals_power_source",
        "performance_change_proposals",
        ["power_source_id"],
    )

    op.create_index(
        "ix_perf_proposals_source_test",
        "performance_change_proposals",
        ["source_performance_test_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_perf_proposals_source_test",
        table_name=
            "performance_change_proposals",
    )

    op.drop_index(
        "ix_perf_proposals_power_source",
        table_name=
            "performance_change_proposals",
    )

    op.drop_index(
        "ix_perf_proposals_status",
        table_name=
            "performance_change_proposals",
    )

    op.drop_index(
        "ix_perf_proposals_athlete",
        table_name=
            "performance_change_proposals",
    )

    op.drop_table(
        "performance_change_proposals"
    )
