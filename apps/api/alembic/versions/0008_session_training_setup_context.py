"""Attach training setups to sessions

Revision ID: 0008_session_setup_context
Revises: 0007_training_setups
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = (
    "0008_session_setup_context"
)

down_revision: Union[str, None] = (
    "0007_training_setups"
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
        "planned_sessions",
        sa.Column(
            "training_setup_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_planned_sessions_training_setup_id",
        "planned_sessions",
        "training_setups",
        ["training_setup_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_planned_sessions_training_setup_id",
        "planned_sessions",
        ["training_setup_id"],
    )

    op.add_column(
        "canonical_sessions",
        sa.Column(
            "training_setup_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_canonical_sessions_training_setup_id",
        "canonical_sessions",
        "training_setups",
        ["training_setup_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_canonical_sessions_training_setup_id",
        "canonical_sessions",
        ["training_setup_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_canonical_sessions_training_setup_id",
        table_name="canonical_sessions",
    )

    op.drop_constraint(
        "fk_canonical_sessions_training_setup_id",
        "canonical_sessions",
        type_="foreignkey",
    )

    op.drop_column(
        "canonical_sessions",
        "training_setup_id",
    )

    op.drop_index(
        "ix_planned_sessions_training_setup_id",
        table_name="planned_sessions",
    )

    op.drop_constraint(
        "fk_planned_sessions_training_setup_id",
        "planned_sessions",
        type_="foreignkey",
    )

    op.drop_column(
        "planned_sessions",
        "training_setup_id",
    )
