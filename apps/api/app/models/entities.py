from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Warsaw")
    locale: Mapped[str] = mapped_column(String(16), default="pl-PL")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Athlete(Base):
    __tablename__ = "athletes"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    display_name: Mapped[str] = mapped_column(String(200))
    primary_sport: Mapped[str] = mapped_column(String(64), default="cycling")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ExternalConnection(Base):
    __tablename__ = "external_connections"
    __table_args__ = (UniqueConstraint("athlete_id", "provider", name="uq_connection_athlete_provider"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(64))
    provider_athlete_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SourceActivity(Base):
    __tablename__ = "source_activities"
    __table_args__ = (
        UniqueConstraint("athlete_id", "provider", "provider_activity_id", name="uq_source_activity_provider_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64), default="intervals")
    provider_activity_id: Mapped[str] = mapped_column(String(128))
    recording_source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sport: Mapped[str] = mapped_column(String(64))
    indoor: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalized_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_hr_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_hr_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cadence_rpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    work_kj: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_load: Mapped[float | None] = mapped_column(Float, nullable=True)
    paired_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CanonicalSession(Base):
    __tablename__ = "canonical_sessions"
    __table_args__ = (UniqueConstraint("athlete_id", "fingerprint", name="uq_canonical_athlete_fingerprint"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    athlete_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("athletes.id", ondelete="CASCADE"), index=True)
    sport: Mapped[str] = mapped_column(String(64))
    indoor: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    training_setup_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "training_setups.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalized_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_hr_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_hr_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cadence_rpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    work_kj: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_load: Mapped[float | None] = mapped_column(Float, nullable=True)
    duplicate_status: Mapped[str] = mapped_column(String(32), default="single")
    analysis_level: Mapped[str] = mapped_column(String(32), default="basic")
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CanonicalSessionSource(Base):
    __tablename__ = "canonical_session_sources"
    canonical_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("canonical_sessions.id", ondelete="CASCADE"), primary_key=True)
    source_activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_activities.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(32))
    duplicate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False)


class SessionMetricSource(Base):
    __tablename__ = "session_metric_sources"
    __table_args__ = (UniqueConstraint("canonical_session_id", "metric_name", name="uq_canonical_metric"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    canonical_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("canonical_sessions.id", ondelete="CASCADE"))
    metric_name: Mapped[str] = mapped_column(String(64))
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_activities.id", ondelete="CASCADE"))
    quality_score: Mapped[float] = mapped_column(Float)
    selection_reason: Mapped[str] = mapped_column(String(255))



class SyncState(Base):
    __tablename__ = "sync_state"

    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    resource: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_successful_sync: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="idle")



class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="planning")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class GoalEvent(Base):
    __tablename__ = "goal_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    season_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"),
        index=True,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200))
    event_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(String(16), default="A")
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_time_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    goal_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class Macrocycle(Base):
    __tablename__ = "macrocycles"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "sequence",
            name="uq_macrocycle_season_sequence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    season_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"),
        index=True,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200))
    sequence: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="planned")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class TrainingWeek(Base):
    __tablename__ = "training_weeks"
    __table_args__ = (
        UniqueConstraint(
            "macrocycle_id",
            "week_number",
            name="uq_training_week_macrocycle_number",
        ),
        UniqueConstraint(
            "athlete_id",
            "start_date",
            name="uq_training_week_athlete_start",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    macrocycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("macrocycles.id", ondelete="CASCADE"),
        index=True,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        index=True,
    )
    week_number: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="planned")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class PlannedSession(Base):
    __tablename__ = "planned_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    training_week_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("training_weeks.id", ondelete="CASCADE"),
        index=True,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        index=True,
    )
    planned_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200))
    sport: Mapped[str] = mapped_column(String(64), default="cycling")
    training_setup_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "training_setups.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    session_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="SUPPORT")
    status: Mapped[str] = mapped_column(String(32), default="planned")
    planned_duration_s: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    planned_distance_m: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    targets: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    workout_structure: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    intervals_event_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class SessionMatch(Base):
    __tablename__ = "session_matches"
    __table_args__ = (
        UniqueConstraint(
            "planned_session_id",
            name="uq_session_match_planned",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        index=True,
    )
    planned_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("planned_sessions.id", ondelete="CASCADE"),
    )
    canonical_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canonical_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    match_method: Mapped[str] = mapped_column(
        String(32),
        default="auto",
    )
    match_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    match_evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )
    manual_override: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class SessionAnalysis(Base):
    __tablename__ = "session_analyses"
    __table_args__ = (
        UniqueConstraint(
            "canonical_session_id",
            name="uq_session_analysis_canonical",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        index=True,
    )
    canonical_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("canonical_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    planned_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("planned_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analysis_version: Mapped[str] = mapped_column(
        String(64),
        default="deterministic-v1",
    )
    classification: Mapped[str] = mapped_column(
        String(64),
    )
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )
    flags: Mapped[list[Any]] = mapped_column(
        JSON,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class SportProfile(Base):
    __tablename__ = "sport_profiles"
    __table_args__ = (
        UniqueConstraint(
            "athlete_id",
            "profile_key",
            name="uq_sport_profile_athlete_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    sport: Mapped[str] = mapped_column(
        String(64),
    )

    # Kept for backward compatibility.
    # New code uses environment.
    context: Mapped[str] = mapped_column(
        String(32),
    )

    discipline: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    environment: Mapped[str] = mapped_column(
        String(32),
    )
    power_source_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        ForeignKey(
            "devices.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    profile_key: Mapped[str] = mapped_column(
        String(255),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class ZoneSet(Base):
    __tablename__ = "zone_sets"
    __table_args__ = (
        UniqueConstraint(
            "sport_profile_id",
            "effective_from",
            name="uq_zone_set_profile_effective_from",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    sport_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "sport_profiles.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    ftp_w: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    threshold_hr_bpm: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    power_zones: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )
    hr_zones: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )
    source: Mapped[str] = mapped_column(
        String(32),
        default="manual",
    )
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )


class Bike(Base):
    __tablename__ = "bikes"
    __table_args__ = (
        UniqueConstraint(
            "athlete_id",
            "name",
            name="uq_bike_athlete_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
    )
    discipline: Mapped[str] = mapped_column(
        String(32),
    )
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint(
            "athlete_id",
            "name",
            name="uq_device_athlete_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
    )
    category: Mapped[str] = mapped_column(
        String(64),
    )
    mobility: Mapped[str] = mapped_column(
        String(32),
    )
    capabilities: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSON,
        default=dict,
    )
    details: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSON,
        default=dict,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class BikeDeviceAssignment(Base):
    __tablename__ = "bike_device_assignments"
    __table_args__ = (
        UniqueConstraint(
            "bike_id",
            "device_id",
            "role",
            name="uq_bike_device_assignment",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    bike_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "bikes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "devices.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(64),
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )


class TrainingSetup(Base):
    __tablename__ = "training_setups"
    __table_args__ = (
        UniqueConstraint(
            "athlete_id",
            "name",
            name="uq_training_setup_athlete_name",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(200),
    )
    sport: Mapped[str] = mapped_column(
        String(64),
        default="cycling",
    )
    discipline: Mapped[str] = mapped_column(
        String(32),
    )
    environment: Mapped[str] = mapped_column(
        String(32),
    )
    bike_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "bikes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class TrainingSetupDevice(Base):
    __tablename__ = "training_setup_devices"
    __table_args__ = (
        UniqueConstraint(
            "training_setup_id",
            "role",
            name="uq_training_setup_device_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    training_setup_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        ForeignKey(
            "training_setups.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "devices.id",
            ondelete="CASCADE",
        ),
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(64),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )


class PerformanceTest(Base):
    __tablename__ = "performance_tests"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    canonical_session_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        ForeignKey(
            "canonical_sessions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    training_setup_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        ForeignKey(
            "training_setups.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    sport: Mapped[str] = mapped_column(
        String(64),
        default="cycling",
    )

    discipline: Mapped[
        str | None
    ] = mapped_column(
        String(32),
        nullable=True,
    )

    environment: Mapped[str] = mapped_column(
        String(32),
    )

    test_type: Mapped[str] = mapped_column(
        String(32),
    )

    protocol: Mapped[str] = mapped_column(
        String(64),
    )

    tested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    protocol_data: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSON,
        default=dict,
    )

    notes: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class PerformanceTestResult(Base):
    __tablename__ = "performance_test_results"

    __table_args__ = (
        UniqueConstraint(
            "performance_test_id",
            "power_source_id",
            name=(
                "uq_performance_test_"
                "power_source"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    performance_test_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        ForeignKey(
            "performance_tests.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    power_source_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        ForeignKey(
            "devices.id",
            ondelete="RESTRICT",
        ),
        index=True,
    )

    observed_power_w: Mapped[
        float
    ] = mapped_column(
        Float,
    )

    measurement_window_s: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    estimated_ftp_w: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    estimate_method: Mapped[str] = mapped_column(
        String(32),
        default="none",
    )

    confidence: Mapped[str] = mapped_column(
        String(16),
        default="medium",
    )

    derivation: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSON,
        default=dict,
    )

    metrics: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSON,
        default=dict,
    )

    notes: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )


class PerformanceChangeProposal(Base):
    __tablename__ = "performance_change_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    proposal_type: Mapped[str] = mapped_column(
        String(32),
        default="ftp",
    )

    sport: Mapped[str] = mapped_column(
        String(64),
        default="cycling",
    )

    discipline: Mapped[
        str | None
    ] = mapped_column(
        String(32),
        nullable=True,
    )

    environment: Mapped[str] = mapped_column(
        String(32),
    )

    power_source_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        ForeignKey(
            "devices.id",
            ondelete="RESTRICT",
        ),
        index=True,
    )

    source_performance_test_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        ForeignKey(
            "performance_tests.id",
            ondelete="RESTRICT",
        ),
        index=True,
    )

    baseline_zone_set_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        ForeignKey(
            "zone_sets.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    baseline_ftp_w: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    proposed_ftp_w: Mapped[float] = mapped_column(
        Float,
    )

    confidence: Mapped[
        str | None
    ] = mapped_column(
        String(16),
        nullable=True,
    )

    recommended_effective_from: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
    )

    evidence: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSON,
        default=dict,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        index=True,
    )

    decision_note: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    decided_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    applied_zone_set_id: Mapped[
        uuid.UUID | None
    ] = mapped_column(
        ForeignKey(
            "zone_sets.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class SessionFeedback(Base):
    __tablename__ = "session_feedback"

    __table_args__ = (
        UniqueConstraint(
            "canonical_session_id",
            name="uq_session_feedback_canonical",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    canonical_session_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        ForeignKey(
            "canonical_sessions.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    # Session RPE / CR10 style scale.
    rpe: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    # 0 = fresh legs, 5 = very high muscular fatigue.
    leg_fatigue: Mapped[
        float | None
    ] = mapped_column(
        Float,
        nullable=True,
    )

    comment: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    # Optional athlete-specific signals.
    # Not part of the default feedback UI.
    custom_metrics: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSON,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class WeeklyReview(Base):
    __tablename__ = "weekly_reviews"

    __table_args__ = (
        UniqueConstraint(
            "training_week_id",
            name="uq_weekly_review_training_week",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "athletes.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    training_week_id: Mapped[
        uuid.UUID
    ] = mapped_column(
        ForeignKey(
            "training_weeks.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    review_version: Mapped[str] = mapped_column(
        String(64),
    )

    summary: Mapped[
        dict[str, Any]
    ] = mapped_column(
        JSON,
        default=dict,
    )

    flags: Mapped[
        list[Any]
    ] = mapped_column(
        JSON,
        default=list,
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )
