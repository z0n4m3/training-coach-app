"""Cycling training setups

Revision ID: 0007_training_setups
Revises: 0006_cycling_equipment_inventory
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007_training_setups"

down_revision: Union[str, None] = (
    "0006_cycling_equipment_inventory"
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
        "training_setups",
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
            "name",
            sa.String(200),
            nullable=False,
        ),
        sa.Column(
            "sport",
            sa.String(64),
            nullable=False,
            server_default="cycling",
        ),
        sa.Column(
            "discipline",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "environment",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "bike_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "bikes.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
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
            "name",
            name="uq_training_setup_athlete_name",
        ),
    )

    op.create_index(
        "ix_training_setups_athlete_id",
        "training_setups",
        ["athlete_id"],
    )

    op.create_index(
        "ix_training_setups_bike_id",
        "training_setups",
        ["bike_id"],
    )

    op.create_table(
        "training_setup_devices",
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
            "training_setup_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "training_setups.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "devices.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "training_setup_id",
            "role",
            name="uq_training_setup_device_role",
        ),
    )

    op.create_index(
        "ix_training_setup_devices_athlete_id",
        "training_setup_devices",
        ["athlete_id"],
    )

    op.create_index(
        "ix_training_setup_devices_training_setup_id",
        "training_setup_devices",
        ["training_setup_id"],
    )

    op.create_index(
        "ix_training_setup_devices_device_id",
        "training_setup_devices",
        ["device_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_training_setup_devices_device_id",
        table_name="training_setup_devices",
    )
    op.drop_index(
        "ix_training_setup_devices_training_setup_id",
        table_name="training_setup_devices",
    )
    op.drop_index(
        "ix_training_setup_devices_athlete_id",
        table_name="training_setup_devices",
    )
    op.drop_table(
        "training_setup_devices"
    )

    op.drop_index(
        "ix_training_setups_bike_id",
        table_name="training_setups",
    )
    op.drop_index(
        "ix_training_setups_athlete_id",
        table_name="training_setups",
    )
    op.drop_table(
        "training_setups"
    )
