from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    CanonicalSession,
    SessionAnalysis,
    User,
)
from app.schemas.cycling_equipment import (
    BikeCreate,
    DeviceCreate,
)
from app.schemas.performance import (
    ZoneSetCreate,
)
from app.schemas.training_setup import (
    TrainingSetupCreate,
)
from app.services.cycling_equipment_service import (
    CyclingEquipmentService,
)
from app.services.performance_profile_service import (
    PerformanceProfileService,
)
from app.services.session_context_service import (
    SessionContextService,
)
from app.services.training_setup_service import (
    TrainingSetupService,
)


def make_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(
        engine
    )

    return Session(engine)


def make_fixture(
    db: Session,
):
    user = User(
        timezone="Europe/Warsaw"
    )

    db.add(user)
    db.flush()

    athlete = Athlete(
        user_id=user.id,
        display_name="Test Athlete",
    )

    db.add(athlete)
    db.flush()

    equipment = (
        CyclingEquipmentService(db)
    )

    bike = equipment.create_bike(
        BikeCreate(
            athlete_id=athlete.id,
            name="Road",
            discipline="road",
        )
    )

    trainer = equipment.create_device(
        DeviceCreate(
            athlete_id=athlete.id,
            name="Trainer",
            category="trainer",
            mobility="shared",
            capabilities={
                "power_measurement": True,
            },
        )
    )

    setup = TrainingSetupService(
        db
    ).create(
        TrainingSetupCreate(
            athlete_id=athlete.id,
            name="Road indoor",
            bike_id=bike["id"],
            environment="indoor",
            device_roles={
                "trainer":
                    trainer["id"],
                "primary_power_source":
                    trainer["id"],
            },
        )
    )

    PerformanceProfileService(
        db
    ).create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            context="indoor",
            effective_from=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            ftp_w=230,
            threshold_hr_bpm=178,
            source="test",
        )
    )

    # Power profile belongs to the actual
    # analytical power source. HR remains
    # source-agnostic.
    PerformanceProfileService(
        db
    ).create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            environment="indoor",
            discipline="road",
            power_source_id=
                trainer["id"],
            effective_from=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            ftp_w=230,
            source="test",
        )
    )

    session = CanonicalSession(
        athlete_id=athlete.id,
        sport="Ride",
        indoor=None,
        start_at=datetime(
            2026,
            10,
            1,
            17,
            0,
            tzinfo=timezone.utc,
        ),
        duration_s=3600,
        avg_power_w=184,
        normalized_power_w=190,
        avg_hr_bpm=145,
        max_hr_bpm=170,
        duplicate_status="single",
        analysis_level="basic",
        fingerprint=(
            "training-context-test"
        ),
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return (
        athlete,
        setup,
        session,
    )


def test_actual_setup_becomes_session_context():
    db = make_db()

    athlete, setup, session = (
        make_fixture(db)
    )

    result = SessionContextService(
        db
    ).set_training_setup(
        athlete_id=athlete.id,
        session_id=session.id,
        training_setup_id=setup["id"],
    )

    assert (
        result["training_setup_id"]
        == setup["id"]
    )

    assert (
        result["training_setup"]
        ["environment"]
        == "indoor"
    )

    analysis = db.scalar(
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    assert analysis is not None

    assert (
        analysis.analysis_version
        == "deterministic-v6"
    )

    assert (
        analysis.evidence[
            "training_setup"
        ]["environment"]
        == "indoor"
    )

    assert (
        analysis.evidence[
            "performance"
        ]["context"]
        == "indoor"
    )

    assert (
        analysis.evidence[
            "performance"
        ]["context_source"]
        == "training_setup"
    )

    assert (
        analysis.evidence[
            "performance"
        ]["ftp_w"]
        == 230
    )

    assert (
        analysis.evidence[
            "performance"
        ]["power_profile"][
            "resolution"
        ]
        == "source_discipline"
    )

    assert (
        analysis.evidence[
            "performance"
        ]["hr_profile"][
            "resolution"
        ]
        == "environment_generic"
    )


def test_explicit_setup_can_expose_import_context_conflict():
    db = make_db()

    athlete, setup, session = (
        make_fixture(db)
    )

    session.indoor = False
    db.commit()

    SessionContextService(
        db
    ).set_training_setup(
        athlete_id=athlete.id,
        session_id=session.id,
        training_setup_id=setup["id"],
    )

    analysis = db.scalar(
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    assert (
        "training_setup_environment_conflict"
        in analysis.flags
    )

    assert (
        analysis.evidence[
            "performance"
        ]["context"]
        == "indoor"
    )


def test_training_setup_can_be_cleared():
    db = make_db()

    athlete, setup, session = (
        make_fixture(db)
    )

    context = SessionContextService(
        db
    )

    context.set_training_setup(
        athlete_id=athlete.id,
        session_id=session.id,
        training_setup_id=setup["id"],
    )

    result = context.set_training_setup(
        athlete_id=athlete.id,
        session_id=session.id,
        training_setup_id=None,
    )

    assert (
        result["training_setup_id"]
        is None
    )

    assert (
        result["training_setup"]
        is None
    )


def test_source_specific_ftp_wins_over_generic_profile():
    db = make_db()

    athlete, setup, session = (
        make_fixture(db)
    )

    primary_source_id = (
        setup["device_roles"]
        ["primary_power_source"]
        ["id"]
    )

    # Later direct test on the same trainer.
    PerformanceProfileService(
        db
    ).create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            environment="indoor",
            discipline="road",
            power_source_id=
                primary_source_id,
            effective_from=datetime(
                2026,
                9,
                15,
                tzinfo=timezone.utc,
            ),
            ftp_w=220,
            source="test",
        )
    )

    SessionContextService(
        db
    ).set_training_setup(
        athlete_id=athlete.id,
        session_id=session.id,
        training_setup_id=setup["id"],
    )

    analysis = db.scalar(
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    performance = analysis.evidence[
        "performance"
    ]

    assert performance["ftp_w"] == 220

    # HR still comes from the generic
    # source-agnostic profile.
    assert (
        performance[
            "threshold_hr_bpm"
        ]
        == 178
    )

    assert (
        performance[
            "power_source_id"
        ]
        == str(primary_source_id)
    )

    assert (
        performance[
            "power_profile"
        ]["resolution"]
        == "source_discipline"
    )

    assert (
        performance[
            "hr_profile"
        ]["resolution"]
        == "environment_generic"
    )

    assert (
        performance[
            "power_profile"
        ]["zone_set_id"]
        != performance[
            "hr_profile"
        ]["zone_set_id"]
    )

    # There is no single zone set that
    # represents both power and HR.
    assert (
        performance["zone_set_id"]
        is None
    )


def test_explicit_power_source_does_not_use_generic_ftp():
    db = make_db()

    athlete, setup, session = (
        make_fixture(db)
    )

    from app.models.entities import (
        SportProfile,
        ZoneSet,
    )

    primary_source_id = (
        setup["device_roles"]
        ["primary_power_source"]
        ["id"]
    )

    source_profile = db.scalar(
        select(SportProfile).where(
            SportProfile.athlete_id
            == athlete.id,
            SportProfile.power_source_id
            == primary_source_id,
        )
    )

    assert source_profile is not None

    source_zone_sets = list(
        db.scalars(
            select(ZoneSet).where(
                ZoneSet.sport_profile_id
                == source_profile.id
            )
        )
    )

    for row in source_zone_sets:
        db.delete(row)

    db.delete(source_profile)
    db.commit()

    SessionContextService(
        db
    ).set_training_setup(
        athlete_id=athlete.id,
        session_id=session.id,
        training_setup_id=setup["id"],
    )

    analysis = db.scalar(
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    performance = analysis.evidence[
        "performance"
    ]

    # Generic indoor profile exists and
    # contains FTP=230, but it must not be
    # silently substituted for the known
    # trainer source.
    assert performance["ftp_w"] is None

    assert (
        performance[
            "threshold_hr_bpm"
        ]
        == 178
    )

    assert (
        performance["status"]
        == "partial"
    )

    assert (
        performance[
            "power_profile"
        ]["status"]
        == "missing"
    )

    assert (
        "no_effective_power_profile"
        in analysis.flags
    )


def test_primary_not_secondary_source_drives_ftp():
    db = make_db()

    athlete, setup, session = (
        make_fixture(db)
    )

    primary_source_id = (
        setup["device_roles"]
        ["primary_power_source"]
        ["id"]
    )

    performance_service = (
        PerformanceProfileService(db)
    )

    # A later FTP version for the primary
    # source must control analysis.
    performance_service.create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            environment="indoor",
            discipline="road",
            power_source_id=
                primary_source_id,
            effective_from=datetime(
                2026,
                9,
                20,
                tzinfo=timezone.utc,
            ),
            ftp_w=225,
            source="test",
        )
    )

    SessionContextService(
        db
    ).set_training_setup(
        athlete_id=athlete.id,
        session_id=session.id,
        training_setup_id=setup["id"],
    )

    analysis = db.scalar(
        select(SessionAnalysis).where(
            SessionAnalysis.canonical_session_id
            == session.id
        )
    )

    performance = analysis.evidence[
        "performance"
    ]

    assert performance["ftp_w"] == 225

    assert (
        performance[
            "power_source_id"
        ]
        == str(primary_source_id)
    )
