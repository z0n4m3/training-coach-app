"""Cycling equipment inventory

Revision ID: 0006_cycling_equipment_inventory
Revises: 0005_performance_profiles
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = (
    "0006_cycling_equipment_inventory"
)

down_revision: Union[str, None] = (
    "0005_performance_profiles"
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
        "bikes",
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
            "discipline",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "details",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
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
            name="uq_bike_athlete_name",
        ),
    )

    op.create_index(
        "ix_bikes_athlete_id",
        "bikes",
        ["athlete_id"],
    )

    op.create_table(
        "devices",
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
            "category",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "mobility",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "capabilities",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
        ),
        sa.Column(
            "details",
            postgresql.JSONB(
                astext_type=sa.Text()
            ),
            nullable=False,
            server_default=sa.text(
                "'{}'::jsonb"
            ),
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
            name="uq_device_athlete_name",
        ),
    )

    op.create_index(
        "ix_devices_athlete_id",
        "devices",
        ["athlete_id"],
    )

    op.create_table(
        "bike_device_assignments",
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
            "bike_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "bikes.id",
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
            "bike_id",
            "device_id",
            "role",
            name="uq_bike_device_assignment",
        ),
    )

    op.create_index(
        "ix_bike_device_assignments_athlete_id",
        "bike_device_assignments",
        ["athlete_id"],
    )

    op.create_index(
        "ix_bike_device_assignments_bike_id",
        "bike_device_assignments",
        ["bike_id"],
    )

    op.create_index(
        "ix_bike_device_assignments_device_id",
        "bike_device_assignments",
        ["device_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bike_device_assignments_device_id",
        table_name="bike_device_assignments",
    )
    op.drop_index(
        "ix_bike_device_assignments_bike_id",
        table_name="bike_device_assignments",
    )
    op.drop_index(
        "ix_bike_device_assignments_athlete_id",
        table_name="bike_device_assignments",
    )
    op.drop_table(
        "bike_device_assignments"
    )

    op.drop_index(
        "ix_devices_athlete_id",
        table_name="devices",
    )
    op.drop_table("devices")

    op.drop_index(
        "ix_bikes_athlete_id",
        table_name="bikes",
    )
    op.drop_table("bikes")
