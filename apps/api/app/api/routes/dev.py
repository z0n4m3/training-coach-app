import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Athlete, User
from app.schemas.dev import AthleteCreate

router = APIRouter(prefix="/v1/dev", tags=["development"])


@router.post("/athletes")
def create_athlete(payload: AthleteCreate, db: Session = Depends(get_db)):
    user = User(timezone=payload.timezone)
    db.add(user)
    db.flush()
    athlete = Athlete(user_id=user.id, display_name=payload.display_name)
    db.add(athlete)
    db.commit()
    return {"athlete_id": str(athlete.id), "display_name": athlete.display_name}
