from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class TrainingSetupCreate(BaseModel):
    athlete_id: uuid.UUID

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    bike_id: uuid.UUID

    environment: str

    device_roles: dict[
        str,
        uuid.UUID,
    ] = Field(
        default_factory=dict,
    )

    notes: str | None = None
