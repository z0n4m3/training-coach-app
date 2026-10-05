from __future__ import annotations

import uuid

from pydantic import BaseModel


class SessionTrainingSetupUpdate(
    BaseModel
):
    training_setup_id: (
        uuid.UUID | None
    ) = None
