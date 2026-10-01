from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.sport import normalize_sport
from app.models.entities import (
    Athlete,
    SportProfile,
    ZoneSet,
)
from app.schemas.performance import ZoneSetCreate


VALID_CONTEXTS = {
    "indoor",
    "outdoor",
}


class PerformanceProfileService:
    def __init__(self, db: Session):
        self.db = db

    def create_zone_set(
        self,
        payload: ZoneSetCreate,
    ) -> dict:
        athlete = self.db.get(
            Athlete,
            payload.athlete_id,
        )

        if athlete is None:
            raise LookupError(
                "Athlete not found"
            )

        sport = normalize_sport(
            payload.sport
        )

        if not sport:
            raise ValueError(
                "Sport cannot be empty"
            )

        context = payload.context.lower()

        if context not in VALID_CONTEXTS:
            raise ValueError(
                "Unsupported performance context"
            )

        profile = self.db.scalar(
            select(SportProfile).where(
                SportProfile.athlete_id
                == payload.athlete_id,
                SportProfile.sport
                == sport,
                SportProfile.context
                == context,
            )
        )

        if profile is None:
            profile = SportProfile(
                athlete_id=payload.athlete_id,
                sport=sport,
                context=context,
            )

            self.db.add(profile)
            self.db.flush()

        existing = self.db.scalar(
            select(ZoneSet).where(
                ZoneSet.sport_profile_id
                == profile.id,
                ZoneSet.effective_from
                == payload.effective_from,
            )
        )

        if existing is not None:
            raise ValueError(
                "Zone set already exists for "
                "this effective_from"
            )

        zone_set = ZoneSet(
            sport_profile_id=profile.id,
            athlete_id=payload.athlete_id,
            effective_from=
                payload.effective_from,
            ftp_w=payload.ftp_w,
            threshold_hr_bpm=
                payload.threshold_hr_bpm,
            power_zones=
                payload.power_zones,
            hr_zones=
                payload.hr_zones,
            source=payload.source,
            note=payload.note,
        )

        self.db.add(zone_set)
        self.db.commit()
        self.db.refresh(zone_set)

        return self._serialize(
            profile,
            zone_set,
        )

    def list_zone_sets(
        self,
        athlete_id: uuid.UUID,
        sport: str,
        context: str,
    ) -> list[dict]:
        profile = self._profile(
            athlete_id=athlete_id,
            sport=sport,
            context=context,
        )

        if profile is None:
            return []

        zone_sets = self.db.scalars(
            select(ZoneSet)
            .where(
                ZoneSet.sport_profile_id
                == profile.id
            )
            .order_by(
                ZoneSet.effective_from.desc()
            )
        ).all()

        return [
            self._serialize(
                profile,
                zone_set,
            )
            for zone_set in zone_sets
        ]

    def effective_zone_set(
        self,
        athlete_id: uuid.UUID,
        sport: str,
        context: str,
        at: datetime,
    ) -> dict | None:
        profile = self._profile(
            athlete_id=athlete_id,
            sport=sport,
            context=context,
        )

        if profile is None:
            return None

        zone_set = self.db.scalar(
            select(ZoneSet)
            .where(
                ZoneSet.sport_profile_id
                == profile.id,
                ZoneSet.effective_from
                <= at,
            )
            .order_by(
                ZoneSet.effective_from.desc()
            )
            .limit(1)
        )

        if zone_set is None:
            return None

        return self._serialize(
            profile,
            zone_set,
        )

    def _profile(
        self,
        athlete_id: uuid.UUID,
        sport: str,
        context: str,
    ) -> SportProfile | None:
        context = context.lower()

        if context not in VALID_CONTEXTS:
            raise ValueError(
                "Unsupported performance context"
            )

        normalized_sport = normalize_sport(
            sport
        )

        return self.db.scalar(
            select(SportProfile).where(
                SportProfile.athlete_id
                == athlete_id,
                SportProfile.sport
                == normalized_sport,
                SportProfile.context
                == context,
            )
        )

    @staticmethod
    def _serialize(
        profile: SportProfile,
        zone_set: ZoneSet,
    ) -> dict:
        return {
            "id": zone_set.id,
            "sport_profile_id":
                profile.id,
            "athlete_id":
                zone_set.athlete_id,
            "sport":
                profile.sport,
            "context":
                profile.context,
            "effective_from":
                zone_set.effective_from,
            "ftp_w":
                zone_set.ftp_w,
            "threshold_hr_bpm":
                zone_set.threshold_hr_bpm,
            "power_zones":
                zone_set.power_zones,
            "hr_zones":
                zone_set.hr_zones,
            "source":
                zone_set.source,
            "note":
                zone_set.note,
        }
