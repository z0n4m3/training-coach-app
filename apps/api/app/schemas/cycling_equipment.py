from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class BikeCreate(BaseModel):
    athlete_id: uuid.UUID
    name: str = Field(
        min_length=1,
        max_length=200,
    )
    discipline: str
    details: dict[str, Any] = Field(
        default_factory=dict,
    )


class DeviceCreate(BaseModel):
    athlete_id: uuid.UUID
    name: str = Field(
        min_length=1,
        max_length=200,
    )
    category: str
    mobility: str
    capabilities: dict[str, Any] = Field(
        default_factory=dict,
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
    )


class BikeDeviceAssignmentCreate(
    BaseModel
):
    athlete_id: uuid.UUID
    bike_id: uuid.UUID
    device_id: uuid.UUID
    role: str
    notes: str | None = None
