from pydantic import BaseModel, Field


class AthleteCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    timezone: str = "Europe/Warsaw"
