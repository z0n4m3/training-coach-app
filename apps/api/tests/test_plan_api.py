from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import Athlete, User


engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base.metadata.create_all(engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def create_athlete():
    db = TestingSessionLocal()

    user = User(timezone="Europe/Warsaw")
    db.add(user)
    db.flush()

    athlete = Athlete(
        user_id=user.id,
        display_name="Test Athlete",
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)

    athlete_id = str(athlete.id)

    db.close()

    return athlete_id


def test_full_plan_hierarchy_can_be_created_and_read():
    athlete_id = create_athlete()

    season_response = client.post(
        "/v1/plans/seasons",
        json={
            "athlete_id": athlete_id,
            "name": "Ultra 2027",
            "start_date": "2026-11-23",
            "end_date": "2027-10-31",
        },
    )

    assert season_response.status_code == 201
    season = season_response.json()

    event_response = client.post(
        (
            f"/v1/plans/seasons/{season['id']}/goal-events"
            f"?athlete_id={athlete_id}"
        ),
        json={
            "name": "RAP900",
            "event_start_at": "2027-06-01T06:00:00+02:00",
            "priority": "A",
            "distance_km": 900,
            "goal_text": "Primary ultra goal",
        },
    )

    assert event_response.status_code == 201

    macrocycle_response = client.post(
        (
            f"/v1/plans/seasons/{season['id']}/macrocycles"
            f"?athlete_id={athlete_id}"
        ),
        json={
            "name": "Base 1",
            "sequence": 1,
            "start_date": "2026-11-23",
            "end_date": "2027-01-17",
            "objective": "Aerobic base and strength",
        },
    )

    assert macrocycle_response.status_code == 201
    macrocycle = macrocycle_response.json()

    week_response = client.post(
        (
            f"/v1/plans/macrocycles/{macrocycle['id']}/weeks"
            f"?athlete_id={athlete_id}"
        ),
        json={
            "week_number": 1,
            "start_date": "2026-11-23",
            "end_date": "2026-11-29",
            "notes": "First week",
        },
    )

    assert week_response.status_code == 201
    week = week_response.json()

    session_response = client.post(
        (
            f"/v1/plans/weeks/{week['id']}/sessions"
            f"?athlete_id={athlete_id}"
        ),
        json={
            "planned_start_at": "2026-11-24T17:00:00+01:00",
            "name": "END 75'",
            "sport": "cycling",
            "session_type": "END",
            "priority": "SUPPORT",
            "planned_duration_s": 4500,
            "targets": {
                "rpe": [2, 3],
                "intensity": "endurance"
            },
            "workout_structure": {
                "type": "steady",
                "duration_s": 4500
            },
        },
    )

    assert session_response.status_code == 201

    tree_response = client.get(
        (
            f"/v1/plans/seasons/{season['id']}"
            f"?athlete_id={athlete_id}"
        )
    )

    assert tree_response.status_code == 200

    tree = tree_response.json()

    assert tree["name"] == "Ultra 2027"
    assert tree["goal_events"][0]["name"] == "RAP900"

    assert (
        tree["macrocycles"][0]["name"]
        == "Base 1"
    )

    assert (
        tree["macrocycles"][0]["weeks"][0]["week_number"]
        == 1
    )

    planned = (
        tree["macrocycles"][0]
        ["weeks"][0]
        ["sessions"][0]
    )

    assert planned["name"] == "END 75'"
    assert planned["priority"] == "SUPPORT"
    assert planned["targets"]["rpe"] == [2, 3]


def test_invalid_session_priority_is_rejected():
    athlete_id = create_athlete()

    response = client.post(
        "/v1/plans/seasons",
        json={
            "athlete_id": athlete_id,
            "name": "Test season",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
    )

    season_id = response.json()["id"]

    macrocycle_response = client.post(
        (
            f"/v1/plans/seasons/{season_id}/macrocycles"
            f"?athlete_id={athlete_id}"
        ),
        json={
            "name": "Base",
            "sequence": 1,
            "start_date": "2026-01-01",
            "end_date": "2026-02-28",
        },
    )

    macrocycle_id = macrocycle_response.json()["id"]

    week_response = client.post(
        (
            f"/v1/plans/macrocycles/{macrocycle_id}/weeks"
            f"?athlete_id={athlete_id}"
        ),
        json={
            "week_number": 1,
            "start_date": "2026-01-05",
            "end_date": "2026-01-11",
        },
    )

    week_id = week_response.json()["id"]

    session_response = client.post(
        (
            f"/v1/plans/weeks/{week_id}/sessions"
            f"?athlete_id={athlete_id}"
        ),
        json={
            "planned_start_at": "2026-01-06T18:00:00+01:00",
            "name": "Test",
            "priority": "VERY_IMPORTANT",
        },
    )

    assert session_response.status_code == 422
