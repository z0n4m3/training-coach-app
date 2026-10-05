from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.cycling_equipment import (
    normalize_cycling_discipline,
    normalize_training_environment,
)
from app.domain.sport import normalize_sport
from app.models.entities import (
    Athlete,
    Device,
    SportProfile,
    ZoneSet,
)
from app.schemas.performance import (
    ZoneSetCreate,
)


class PerformanceProfileService:
    def __init__(
        self,
        db: Session,
    ):
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

        environment = (
            self._resolve_environment(
                context=payload.context,
                environment=
                    payload.environment,
            )
        )

        discipline = (
            self._normalize_discipline(
                sport=sport,
                discipline=
                    payload.discipline,
            )
        )

        if payload.power_source_id is not None:
            self._validate_power_source(
                athlete_id=
                    payload.athlete_id,
                power_source_id=
                    payload.power_source_id,
                environment=environment,
            )

        profile_key = self._profile_key(
            sport=sport,
            environment=environment,
            discipline=discipline,
            power_source_id=
                payload.power_source_id,
        )

        profile = self.db.scalar(
            select(SportProfile).where(
                SportProfile.athlete_id
                == payload.athlete_id,
                SportProfile.profile_key
                == profile_key,
            )
        )

        if profile is None:
            profile = SportProfile(
                athlete_id=
                    payload.athlete_id,
                sport=sport,
                context=environment,
                environment=environment,
                discipline=discipline,
                power_source_id=
                    payload.power_source_id,
                profile_key=profile_key,
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
        context: str | None = None,
        environment: str | None = None,
        discipline: str | None = None,
        power_source_id:
            uuid.UUID | None = None,
    ) -> list[dict]:
        profile = self._profile(
            athlete_id=athlete_id,
            sport=sport,
            context=context,
            environment=environment,
            discipline=discipline,
            power_source_id=
                power_source_id,
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
        context: str | None = None,
        at: datetime | None = None,
        environment: str | None = None,
        discipline: str | None = None,
        power_source_id:
            uuid.UUID | None = None,
    ) -> dict | None:
        if at is None:
            raise ValueError(
                "Effective date is required"
            )

        profile = self._profile(
            athlete_id=athlete_id,
            sport=sport,
            context=context,
            environment=environment,
            discipline=discipline,
            power_source_id=
                power_source_id,
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
        *,
        athlete_id: uuid.UUID,
        sport: str,
        context: str | None,
        environment: str | None,
        discipline: str | None,
        power_source_id:
            uuid.UUID | None,
    ) -> SportProfile | None:
        normalized_sport = (
            normalize_sport(sport)
        )

        resolved_environment = (
            self._resolve_environment(
                context=context,
                environment=environment,
                default="outdoor",
            )
        )

        normalized_discipline = (
            self._normalize_discipline(
                sport=normalized_sport,
                discipline=discipline,
            )
        )

        profile_key = self._profile_key(
            sport=normalized_sport,
            environment=
                resolved_environment,
            discipline=
                normalized_discipline,
            power_source_id=
                power_source_id,
        )

        return self.db.scalar(
            select(SportProfile).where(
                SportProfile.athlete_id
                == athlete_id,
                SportProfile.profile_key
                == profile_key,
            )
        )

    @staticmethod
    def _resolve_environment(
        *,
        context: str | None,
        environment: str | None,
        default: str | None = None,
    ) -> str:
        if (
            context is not None
            and environment is not None
        ):
            context_value = (
                normalize_training_environment(
                    context
                )
            )
            environment_value = (
                normalize_training_environment(
                    environment
                )
            )

            if (
                context_value
                != environment_value
            ):
                raise ValueError(
                    (
                        "environment and legacy "
                        "context must match"
                    )
                )

            return environment_value

        value = (
            environment
            if environment is not None
            else context
        )

        if value is None:
            if default is None:
                raise ValueError(
                    (
                        "Performance environment "
                        "is required"
                    )
                )

            value = default

        return normalize_training_environment(
            value
        )

    @staticmethod
    def _normalize_discipline(
        *,
        sport: str,
        discipline: str | None,
    ) -> str | None:
        if discipline is None:
            return None

        if sport != "cycling":
            raise ValueError(
                (
                    "Discipline-specific performance "
                    "profiles currently support "
                    "cycling only"
                )
            )

        return normalize_cycling_discipline(
            discipline
        )

    def _validate_power_source(
        self,
        *,
        athlete_id: uuid.UUID,
        power_source_id: uuid.UUID,
        environment: str,
    ) -> None:
        device = self.db.get(
            Device,
            power_source_id,
        )

        if (
            device is None
            or device.athlete_id
            != athlete_id
        ):
            raise LookupError(
                "Power source not found"
            )

        if not device.active:
            raise ValueError(
                "Power source is inactive"
            )

        if device.category not in {
            "power_meter",
            "trainer",
        }:
            raise ValueError(
                (
                    "Device cannot be used as "
                    "a power source"
                )
            )

        if device.category == "trainer":
            if environment != "indoor":
                raise ValueError(
                    (
                        "Trainer power profile "
                        "requires indoor environment"
                    )
                )

            if not bool(
                device.capabilities.get(
                    "power_measurement"
                )
            ):
                raise ValueError(
                    (
                        "Trainer cannot have a "
                        "power profile without "
                        "power_measurement capability"
                    )
                )

    @staticmethod
    def _profile_key(
        *,
        sport: str,
        environment: str,
        discipline: str | None,
        power_source_id:
            uuid.UUID | None,
    ) -> str:
        discipline_key = (
            discipline
            if discipline is not None
            else "*"
        )

        power_key = (
            str(power_source_id)
            if power_source_id is not None
            else "*"
        )

        return (
            f"{sport}|"
            f"{discipline_key}|"
            f"{environment}|"
            f"{power_key}"
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

            # Legacy field retained.
            "context":
                profile.environment,

            "environment":
                profile.environment,
            "discipline":
                profile.discipline,
            "power_source_id":
                profile.power_source_id,
            "profile_key":
                profile.profile_key,
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
