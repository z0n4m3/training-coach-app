from datetime import (
    datetime,
    timezone,
)

import pytest
from sqlalchemy import (
    create_engine,
    select,
)
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    Athlete,
    Device,
    PerformanceChangeProposal,
    User,
    ZoneSet,
)
from app.schemas.performance import (
    ZoneSetCreate,
)
from app.schemas.performance_proposals import (
    FtpProposalCreate,
)
from app.schemas.performance_tests import (
    PerformanceTestCreate,
    PerformanceTestResultCreate,
)
from app.services.performance_profile_service import (
    PerformanceProfileService,
)
from app.services.performance_proposal_service import (
    PerformanceProposalService,
)
from app.services.performance_test_service import (
    PerformanceTestService,
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

    trainer = Device(
        athlete_id=athlete.id,
        name="Trainer",
        category="trainer",
        mobility="shared",
        capabilities={
            "power_measurement": True,
        },
        details={},
        active=True,
    )

    power_meter = Device(
        athlete_id=athlete.id,
        name="Bike PM",
        category="power_meter",
        mobility="movable",
        capabilities={
            "power_measurement": True,
        },
        details={},
        active=True,
    )

    db.add_all(
        [
            trainer,
            power_meter,
        ]
    )

    db.commit()
    db.refresh(trainer)
    db.refresh(power_meter)

    return (
        athlete,
        trainer,
        power_meter,
    )


def create_baseline(
    db: Session,
    *,
    athlete,
    source,
    ftp_w: float,
    effective_from: datetime,
):
    return PerformanceProfileService(
        db
    ).create_zone_set(
        ZoneSetCreate(
            athlete_id=athlete.id,
            sport="cycling",
            environment="indoor",
            discipline="road",
            power_source_id=
                source.id,
            effective_from=
                effective_from,
            ftp_w=ftp_w,
            source="test",
        )
    )


def record_ftp(
    db: Session,
    *,
    athlete,
    source,
    tested_at: datetime,
    observed_power_w: float,
    estimated_ftp_w: float,
):
    return PerformanceTestService(
        db
    ).create(
        PerformanceTestCreate(
            athlete_id=athlete.id,
            sport="cycling",
            discipline="road",
            environment="indoor",
            test_type="ftp",
            protocol="ftp_20min",
            tested_at=tested_at,
            results=[
                PerformanceTestResultCreate(
                    power_source_id=
                        source.id,
                    observed_power_w=
                        observed_power_w,
                    measurement_window_s=
                        1200,
                    estimated_ftp_w=
                        estimated_ftp_w,
                    estimate_method=
                        "protocol_formula",
                    confidence="high",
                    derivation={
                        "factor": 0.95,
                    },
                )
            ],
        )
    )


def test_ftp_proposal_is_persisted_without_applying_zone_set():
    db = make_db()

    (
        athlete,
        trainer,
        _,
    ) = make_fixture(db)

    baseline = create_baseline(
        db,
        athlete=athlete,
        source=trainer,
        ftp_w=225,
        effective_from=datetime(
            2026,
            9,
            1,
            tzinfo=timezone.utc,
        ),
    )

    test = record_ftp(
        db,
        athlete=athlete,
        source=trainer,
        tested_at=datetime(
            2026,
            9,
            18,
            tzinfo=timezone.utc,
        ),
        observed_power_w=242,
        estimated_ftp_w=230,
    )

    before = list(
        db.scalars(
            select(ZoneSet)
        )
    )

    proposal = (
        PerformanceProposalService(
            db
        ).create_ftp_proposal(
            FtpProposalCreate(
                athlete_id=
                    athlete.id,
                power_source_id=
                    trainer.id,
                environment="indoor",
                discipline="road",
                at=datetime(
                    2026,
                    10,
                    5,
                    tzinfo=timezone.utc,
                ),
            )
        )
    )

    after = list(
        db.scalars(
            select(ZoneSet)
        )
    )

    assert (
        proposal["status"]
        == "pending"
    )

    assert (
        proposal[
            "baseline_zone_set_id"
        ]
        == baseline["id"]
    )

    assert (
        proposal[
            "baseline_ftp_w"
        ]
        == 225
    )

    assert (
        proposal[
            "proposed_ftp_w"
        ]
        == 230
    )

    assert (
        proposal[
            "source_performance_test"
        ]["id"]
        == test["id"]
    )

    assert (
        proposal[
            "recommended_effective_from"
        ]
        == datetime(
            2026,
            9,
            18,
            tzinfo=timezone.utc,
        )
    )

    assert (
        proposal[
            "requires_athlete_approval"
        ]
        is True
    )

    assert (
        proposal[
            "applied_zone_set_id"
        ]
        is None
    )

    assert (
        proposal[
            "evidence"
        ]["conversion_used"]
        is False
    )

    assert (
        len(before)
        == len(after)
        == 1
    )


def test_same_pending_proposal_is_idempotent():
    db = make_db()

    (
        athlete,
        trainer,
        _,
    ) = make_fixture(db)

    create_baseline(
        db,
        athlete=athlete,
        source=trainer,
        ftp_w=225,
        effective_from=datetime(
            2026,
            9,
            1,
            tzinfo=timezone.utc,
        ),
    )

    record_ftp(
        db,
        athlete=athlete,
        source=trainer,
        tested_at=datetime(
            2026,
            9,
            18,
            tzinfo=timezone.utc,
        ),
        observed_power_w=242,
        estimated_ftp_w=230,
    )

    service = (
        PerformanceProposalService(
            db
        )
    )

    payload = FtpProposalCreate(
        athlete_id=athlete.id,
        power_source_id=trainer.id,
        environment="indoor",
        discipline="road",
        at=datetime(
            2026,
            10,
            5,
            tzinfo=timezone.utc,
        ),
    )

    first = (
        service.create_ftp_proposal(
            payload
        )
    )

    second = (
        service.create_ftp_proposal(
            payload
        )
    )

    rows = list(
        db.scalars(
            select(
                PerformanceChangeProposal
            )
        )
    )

    assert (
        first["id"]
        == second["id"]
    )

    assert len(rows) == 1


def test_changed_baseline_supersedes_old_pending_proposal():
    db = make_db()

    (
        athlete,
        trainer,
        _,
    ) = make_fixture(db)

    create_baseline(
        db,
        athlete=athlete,
        source=trainer,
        ftp_w=225,
        effective_from=datetime(
            2026,
            9,
            1,
            tzinfo=timezone.utc,
        ),
    )

    record_ftp(
        db,
        athlete=athlete,
        source=trainer,
        tested_at=datetime(
            2026,
            9,
            18,
            tzinfo=timezone.utc,
        ),
        observed_power_w=242,
        estimated_ftp_w=230,
    )

    service = (
        PerformanceProposalService(
            db
        )
    )

    first = (
        service.create_ftp_proposal(
            FtpProposalCreate(
                athlete_id=
                    athlete.id,
                power_source_id=
                    trainer.id,
                environment="indoor",
                discipline="road",
                at=datetime(
                    2026,
                    9,
                    25,
                    tzinfo=timezone.utc,
                ),
            )
        )
    )

    create_baseline(
        db,
        athlete=athlete,
        source=trainer,
        ftp_w=228,
        effective_from=datetime(
            2026,
            10,
            1,
            tzinfo=timezone.utc,
        ),
    )

    second = (
        service.create_ftp_proposal(
            FtpProposalCreate(
                athlete_id=
                    athlete.id,
                power_source_id=
                    trainer.id,
                environment="indoor",
                discipline="road",
                at=datetime(
                    2026,
                    10,
                    5,
                    tzinfo=timezone.utc,
                ),
            )
        )
    )

    old = service.get(
        athlete_id=athlete.id,
        proposal_id=first["id"],
    )

    assert (
        old["status"]
        == "superseded"
    )

    assert (
        second["status"]
        == "pending"
    )

    assert (
        second[
            "baseline_ftp_w"
        ]
        == 228
    )

    assert (
        second["id"]
        != first["id"]
    )


def test_proposal_requires_direct_result_for_requested_source():
    db = make_db()

    (
        athlete,
        trainer,
        power_meter,
    ) = make_fixture(db)

    record_ftp(
        db,
        athlete=athlete,
        source=power_meter,
        tested_at=datetime(
            2026,
            9,
            18,
            tzinfo=timezone.utc,
        ),
        observed_power_w=263,
        estimated_ftp_w=250,
    )

    with pytest.raises(
        ValueError,
        match="No reviewable FTP change",
    ):
        PerformanceProposalService(
            db
        ).create_ftp_proposal(
            FtpProposalCreate(
                athlete_id=
                    athlete.id,
                power_source_id=
                    trainer.id,
                environment="indoor",
                discipline="road",
                at=datetime(
                    2026,
                    10,
                    5,
                    tzinfo=timezone.utc,
                ),
            )
        )


def test_no_change_does_not_create_proposal():
    db = make_db()

    (
        athlete,
        trainer,
        _,
    ) = make_fixture(db)

    create_baseline(
        db,
        athlete=athlete,
        source=trainer,
        ftp_w=230,
        effective_from=datetime(
            2026,
            9,
            1,
            tzinfo=timezone.utc,
        ),
    )

    record_ftp(
        db,
        athlete=athlete,
        source=trainer,
        tested_at=datetime(
            2026,
            9,
            18,
            tzinfo=timezone.utc,
        ),
        observed_power_w=242,
        estimated_ftp_w=230,
    )

    with pytest.raises(
        ValueError,
        match="No reviewable FTP change",
    ):
        PerformanceProposalService(
            db
        ).create_ftp_proposal(
            FtpProposalCreate(
                athlete_id=
                    athlete.id,
                power_source_id=
                    trainer.id,
                environment="indoor",
                discipline="road",
                at=datetime(
                    2026,
                    10,
                    5,
                    tzinfo=timezone.utc,
                ),
            )
        )

    rows = list(
        db.scalars(
            select(
                PerformanceChangeProposal
            )
        )
    )

    assert rows == []
