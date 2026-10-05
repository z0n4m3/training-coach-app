from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


class FtpProposalCreate(BaseModel):
    athlete_id: uuid.UUID

    power_source_id: uuid.UUID

    environment: Literal[
        "indoor",
        "outdoor",
    ]

    discipline: str | None = Field(
        default=None,
        max_length=32,
    )

    at: datetime | None = None
