from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    Athlete,
    GoalEvent,
    Macrocycle,
    PlannedSession,
    Season,
    TrainingWeek,
)
from app.schemas.plan import (
    GoalEventCreate,
    MacrocycleCreate,
    PlannedSessionCreate,
    SeasonCreate,
    TrainingWeekCreate,
)


class PlanService:
    def __init__(self, db: Session):
        self.db = db

    def create_season(self, payload: SeasonCreate) -> dict:
        athlete = self.db.get(Athlete, payload.athlete_id)
        if athlete is None:
            raise LookupError("Athlete not found")

        season = Season(
            athlete_id=payload.athlete_id,
            name=payload.name,
            start_date=payload.start_date,
            end_date=payload.end_date,
            status="planning",
        )

        self.db.add(season)
        self.db.commit()
        self.db.refresh(season)

        return self._season_summary(season)

    def list_seasons(self, athlete_id: uuid.UUID) -> list[dict]:
        seasons = self.db.scalars(
            select(Season)
            .where(Season.athlete_id == athlete_id)
            .order_by(Season.start_date.desc())
        ).all()

        return [
            self._season_summary(season)
            for season in seasons
        ]

    def get_season_tree(
        self,
        season_id: uuid.UUID,
        athlete_id: uuid.UUID,
    ) -> dict:
        season = self._owned_season(season_id, athlete_id)

        events = self.db.scalars(
            select(GoalEvent)
            .where(GoalEvent.season_id == season.id)
            .order_by(GoalEvent.event_start_at.asc())
        ).all()

        macrocycles = self.db.scalars(
            select(Macrocycle)
            .where(Macrocycle.season_id == season.id)
            .order_by(Macrocycle.sequence.asc())
        ).all()

        result = self._season_summary(season)

        result["goal_events"] = [
            self._goal_event(event)
            for event in events
        ]

        result["macrocycles"] = []

        for macrocycle in macrocycles:
            macrocycle_data = self._macrocycle(macrocycle)

            weeks = self.db.scalars(
                select(TrainingWeek)
                .where(
                    TrainingWeek.macrocycle_id == macrocycle.id
                )
                .order_by(TrainingWeek.week_number.asc())
            ).all()

            macrocycle_data["weeks"] = []

            for week in weeks:
                week_data = self._week(week)

                sessions = self.db.scalars(
                    select(PlannedSession)
                    .where(
                        PlannedSession.training_week_id == week.id
                    )
                    .order_by(
                        PlannedSession.planned_start_at.asc()
                    )
                ).all()

                week_data["sessions"] = [
                    self._planned_session(session)
                    for session in sessions
                ]

                macrocycle_data["weeks"].append(week_data)

            result["macrocycles"].append(macrocycle_data)

        return result

    def create_goal_event(
        self,
        season_id: uuid.UUID,
        athlete_id: uuid.UUID,
        payload: GoalEventCreate,
    ) -> dict:
        season = self._owned_season(season_id, athlete_id)

        event_date = payload.event_start_at.date()

        if not season.start_date <= event_date <= season.end_date:
            raise ValueError(
                "Goal event must fall within the season"
            )

        event = GoalEvent(
            season_id=season.id,
            athlete_id=season.athlete_id,
            name=payload.name,
            event_start_at=payload.event_start_at,
            priority=payload.priority,
            distance_km=payload.distance_km,
            target_time_s=payload.target_time_s,
            goal_text=payload.goal_text,
        )

        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        return self._goal_event(event)

    def create_macrocycle(
        self,
        season_id: uuid.UUID,
        athlete_id: uuid.UUID,
        payload: MacrocycleCreate,
    ) -> dict:
        season = self._owned_season(season_id, athlete_id)

        if (
            payload.start_date < season.start_date
            or payload.end_date > season.end_date
        ):
            raise ValueError(
                "Macrocycle must fall within the season"
            )

        existing = self.db.scalar(
            select(Macrocycle).where(
                Macrocycle.season_id == season.id,
                Macrocycle.sequence == payload.sequence,
            )
        )

        if existing is not None:
            raise ValueError(
                "Macrocycle sequence already exists in this season"
            )

        macrocycle = Macrocycle(
            season_id=season.id,
            athlete_id=season.athlete_id,
            name=payload.name,
            sequence=payload.sequence,
            start_date=payload.start_date,
            end_date=payload.end_date,
            objective=payload.objective,
            status="planned",
        )

        self.db.add(macrocycle)
        self.db.commit()
        self.db.refresh(macrocycle)

        return self._macrocycle(macrocycle)

    def create_training_week(
        self,
        macrocycle_id: uuid.UUID,
        athlete_id: uuid.UUID,
        payload: TrainingWeekCreate,
    ) -> dict:
        macrocycle = self._owned_macrocycle(
            macrocycle_id,
            athlete_id,
        )

        if (
            payload.start_date < macrocycle.start_date
            or payload.end_date > macrocycle.end_date
        ):
            raise ValueError(
                "Training week must fall within the macrocycle"
            )

        existing_number = self.db.scalar(
            select(TrainingWeek).where(
                TrainingWeek.macrocycle_id == macrocycle.id,
                TrainingWeek.week_number == payload.week_number,
            )
        )

        if existing_number is not None:
            raise ValueError(
                "Week number already exists in this macrocycle"
            )

        existing_date = self.db.scalar(
            select(TrainingWeek).where(
                TrainingWeek.athlete_id == athlete_id,
                TrainingWeek.start_date == payload.start_date,
            )
        )

        if existing_date is not None:
            raise ValueError(
                "Training week already exists for this start date"
            )

        week = TrainingWeek(
            macrocycle_id=macrocycle.id,
            athlete_id=macrocycle.athlete_id,
            week_number=payload.week_number,
            start_date=payload.start_date,
            end_date=payload.end_date,
            status="planned",
            notes=payload.notes,
        )

        self.db.add(week)
        self.db.commit()
        self.db.refresh(week)

        return self._week(week)

    def create_planned_session(
        self,
        week_id: uuid.UUID,
        athlete_id: uuid.UUID,
        payload: PlannedSessionCreate,
    ) -> dict:
        week = self._owned_week(
            week_id,
            athlete_id,
        )

        planned_date = payload.planned_start_at.date()

        if not week.start_date <= planned_date <= week.end_date:
            raise ValueError(
                "Planned session must fall within the training week"
            )

        session = PlannedSession(
            training_week_id=week.id,
            athlete_id=week.athlete_id,
            planned_start_at=payload.planned_start_at,
            name=payload.name,
            sport=payload.sport,
            session_type=payload.session_type,
            priority=payload.priority,
            status="planned",
            planned_duration_s=payload.planned_duration_s,
            planned_distance_m=payload.planned_distance_m,
            targets=payload.targets,
            workout_structure=payload.workout_structure,
            notes=payload.notes,
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return self._planned_session(session)

    def _owned_season(
        self,
        season_id: uuid.UUID,
        athlete_id: uuid.UUID,
    ) -> Season:
        season = self.db.scalar(
            select(Season).where(
                Season.id == season_id,
                Season.athlete_id == athlete_id,
            )
        )

        if season is None:
            raise LookupError("Season not found")

        return season

    def _owned_macrocycle(
        self,
        macrocycle_id: uuid.UUID,
        athlete_id: uuid.UUID,
    ) -> Macrocycle:
        macrocycle = self.db.scalar(
            select(Macrocycle).where(
                Macrocycle.id == macrocycle_id,
                Macrocycle.athlete_id == athlete_id,
            )
        )

        if macrocycle is None:
            raise LookupError("Macrocycle not found")

        return macrocycle

    def _owned_week(
        self,
        week_id: uuid.UUID,
        athlete_id: uuid.UUID,
    ) -> TrainingWeek:
        week = self.db.scalar(
            select(TrainingWeek).where(
                TrainingWeek.id == week_id,
                TrainingWeek.athlete_id == athlete_id,
            )
        )

        if week is None:
            raise LookupError("Training week not found")

        return week

    @staticmethod
    def _season_summary(season: Season) -> dict:
        return {
            "id": season.id,
            "athlete_id": season.athlete_id,
            "name": season.name,
            "start_date": season.start_date,
            "end_date": season.end_date,
            "status": season.status,
        }

    @staticmethod
    def _goal_event(event: GoalEvent) -> dict:
        return {
            "id": event.id,
            "season_id": event.season_id,
            "athlete_id": event.athlete_id,
            "name": event.name,
            "event_start_at": event.event_start_at,
            "priority": event.priority,
            "distance_km": event.distance_km,
            "target_time_s": event.target_time_s,
            "goal_text": event.goal_text,
        }

    @staticmethod
    def _macrocycle(macrocycle: Macrocycle) -> dict:
        return {
            "id": macrocycle.id,
            "season_id": macrocycle.season_id,
            "athlete_id": macrocycle.athlete_id,
            "name": macrocycle.name,
            "sequence": macrocycle.sequence,
            "start_date": macrocycle.start_date,
            "end_date": macrocycle.end_date,
            "objective": macrocycle.objective,
            "status": macrocycle.status,
        }

    @staticmethod
    def _week(week: TrainingWeek) -> dict:
        return {
            "id": week.id,
            "macrocycle_id": week.macrocycle_id,
            "athlete_id": week.athlete_id,
            "week_number": week.week_number,
            "start_date": week.start_date,
            "end_date": week.end_date,
            "status": week.status,
            "notes": week.notes,
        }

    @staticmethod
    def _planned_session(session: PlannedSession) -> dict:
        return {
            "id": session.id,
            "training_week_id": session.training_week_id,
            "athlete_id": session.athlete_id,
            "planned_start_at": session.planned_start_at,
            "name": session.name,
            "sport": session.sport,
            "session_type": session.session_type,
            "priority": session.priority,
            "status": session.status,
            "planned_duration_s": session.planned_duration_s,
            "planned_distance_m": session.planned_distance_m,
            "targets": session.targets,
            "workout_structure": session.workout_structure,
            "notes": session.notes,
            "intervals_event_id": session.intervals_event_id,
        }
