from __future__ import annotations

import uuid
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    Athlete,
    Device,
    PerformanceChangeProposal,
    PerformanceTest,
)
from app.schemas.performance import (
    ZoneSetCreate,
)
from app.schemas.performance_proposals import (
    FtpProposalApproval,
    FtpProposalCreate,
    PerformanceProposalDecision,
)
from app.services.performance_profile_service import (
    PerformanceProfileService,
)
from app.services.performance_test_analysis_service import (
    PerformanceTestAnalysisService,
)


ALLOWED_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "superseded",
}


class ProposalConflictError(ValueError):
    pass


class PerformanceProposalService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def create_ftp_proposal(
        self,
        payload: FtpProposalCreate,
    ) -> dict:
        self._athlete(
            payload.athlete_id
        )

        analysis = (
            PerformanceTestAnalysisService(
                self.db
            ).ftp_proposal(
                athlete_id=
                    payload.athlete_id,
                power_source_id=
                    payload.power_source_id,
                environment=
                    payload.environment,
                discipline=
                    payload.discipline,
                at=payload.at,
            )
        )

        if (
            analysis["status"]
            != "review_required"
        ):
            raise ValueError(
                (
                    "No reviewable FTP change "
                    "is available"
                )
            )

        evidence = analysis.get(
            "evidence"
        )

        if evidence is None:
            raise ValueError(
                "FTP proposal has no evidence"
            )

        test_id = evidence[
            "latest_test_id"
        ]

        test = self.db.scalar(
            select(
                PerformanceTest
            ).where(
                PerformanceTest.id
                == test_id,
                PerformanceTest.athlete_id
                == payload.athlete_id,
            )
        )

        if test is None:
            raise LookupError(
                "Source performance test not found"
            )

        current = analysis[
            "current"
        ]

        existing_query = (
            select(
                PerformanceChangeProposal
            )
            .where(
                PerformanceChangeProposal
                .athlete_id
                == payload.athlete_id,
                PerformanceChangeProposal
                .proposal_type
                == "ftp",
                PerformanceChangeProposal
                .power_source_id
                == payload.power_source_id,
                PerformanceChangeProposal
                .source_performance_test_id
                == test.id,
                PerformanceChangeProposal
                .environment
                == analysis[
                    "environment"
                ],
                PerformanceChangeProposal
                .status
                == "pending",
            )
        )

        if (
            analysis["discipline"]
            is None
        ):
            existing_query = (
                existing_query.where(
                    PerformanceChangeProposal
                    .discipline
                    .is_(None)
                )
            )

        else:
            existing_query = (
                existing_query.where(
                    PerformanceChangeProposal
                    .discipline
                    == analysis[
                        "discipline"
                    ]
                )
            )

        existing = self.db.scalar(
            existing_query.order_by(
                PerformanceChangeProposal
                .created_at.desc()
            )
        )

        if existing is not None:
            same_baseline = (
                existing.baseline_zone_set_id
                == current[
                    "zone_set_id"
                ]
                and existing.baseline_ftp_w
                == current[
                    "ftp_w"
                ]
            )

            same_proposal = (
                existing.proposed_ftp_w
                == analysis[
                    "proposed_ftp_w"
                ]
            )

            if (
                same_baseline
                and same_proposal
            ):
                return self._serialize(
                    existing
                )

            existing.status = (
                "superseded"
            )
            existing.decided_at = (
                datetime.now(
                    timezone.utc
                )
            )
            existing.decision_note = (
                "Baseline changed before review"
            )

        snapshot = {
            "analysis_as_of":
                analysis[
                    "as_of"
                ].isoformat(),
            "latest_test_id":
                str(test.id),
            "latest_tested_at":
                evidence[
                    "latest_tested_at"
                ].isoformat(),
            "protocol":
                evidence[
                    "protocol"
                ],
            "measurement_window_s":
                evidence[
                    "measurement_window_s"
                ],
            "observed_power_w":
                evidence[
                    "observed_power_w"
                ],
            "estimated_ftp_w":
                evidence[
                    "estimated_ftp_w"
                ],
            "estimate_method":
                evidence[
                    "estimate_method"
                ],
            "same_protocol_estimate_count":
                evidence[
                    "same_protocol_estimate_count"
                ],
            "total_source_specific_ftp_estimates":
                evidence[
                    "total_source_specific_ftp_estimates"
                ],
            "delta_w":
                analysis[
                    "delta_w"
                ],
            "delta_pct":
                analysis[
                    "delta_pct"
                ],
            "confidence_basis":
                analysis[
                    "confidence_basis"
                ],
            "conversion_used":
                analysis[
                    "conversion_used"
                ],
        }

        proposal = (
            PerformanceChangeProposal(
                athlete_id=
                    payload.athlete_id,
                proposal_type="ftp",
                sport="cycling",
                discipline=
                    analysis[
                        "discipline"
                    ],
                environment=
                    analysis[
                        "environment"
                    ],
                power_source_id=
                    payload.power_source_id,
                source_performance_test_id=
                    test.id,
                baseline_zone_set_id=
                    current[
                        "zone_set_id"
                    ],
                baseline_ftp_w=
                    current[
                        "ftp_w"
                    ],
                proposed_ftp_w=
                    analysis[
                        "proposed_ftp_w"
                    ],
                confidence=
                    analysis[
                        "confidence"
                    ],
                recommended_effective_from=
                    evidence[
                        "latest_tested_at"
                    ],
                evidence=snapshot,
                status="pending",
            )
        )

        self.db.add(
            proposal
        )
        self.db.commit()
        self.db.refresh(
            proposal
        )

        return self._serialize(
            proposal
        )

    def get(
        self,
        *,
        athlete_id: uuid.UUID,
        proposal_id: uuid.UUID,
    ) -> dict:
        self._athlete(
            athlete_id
        )

        proposal = self.db.scalar(
            select(
                PerformanceChangeProposal
            ).where(
                PerformanceChangeProposal.id
                == proposal_id,
                PerformanceChangeProposal
                .athlete_id
                == athlete_id,
            )
        )

        if proposal is None:
            raise LookupError(
                "Performance proposal not found"
            )

        return self._serialize(
            proposal
        )

    def list(
        self,
        *,
        athlete_id: uuid.UUID,
        status: str | None = None,
    ) -> list[dict]:
        self._athlete(
            athlete_id
        )

        query = select(
            PerformanceChangeProposal
        ).where(
            PerformanceChangeProposal
            .athlete_id
            == athlete_id
        )

        if status is not None:
            normalized_status = (
                status.strip().lower()
            )

            if (
                normalized_status
                not in ALLOWED_STATUSES
            ):
                raise ValueError(
                    "Invalid proposal status"
                )

            query = query.where(
                PerformanceChangeProposal
                .status
                == normalized_status
            )

        rows = self.db.scalars(
            query.order_by(
                PerformanceChangeProposal
                .created_at.desc()
            )
        ).all()

        return [
            self._serialize(row)
            for row in rows
        ]

    def approve_ftp_proposal(
        self,
        *,
        proposal_id: uuid.UUID,
        payload: FtpProposalApproval,
    ) -> dict:
        self._athlete(
            payload.athlete_id
        )

        proposal = self.db.scalar(
            select(
                PerformanceChangeProposal
            )
            .where(
                PerformanceChangeProposal.id
                == proposal_id,
                PerformanceChangeProposal
                .athlete_id
                == payload.athlete_id,
            )
            .with_for_update()
        )

        if proposal is None:
            raise LookupError(
                "Performance proposal not found"
            )

        if proposal.proposal_type != "ftp":
            raise ValueError(
                "Proposal is not an FTP proposal"
            )

        # Repeated approval is idempotent.
        if proposal.status == "approved":
            return self._serialize(
                proposal
            )

        if proposal.status != "pending":
            raise ValueError(
                (
                    "Only a pending proposal "
                    "can be approved"
                )
            )

        decision_at = datetime.now(
            timezone.utc
        )

        profile_service = (
            PerformanceProfileService(
                self.db
            )
        )

        current = (
            profile_service
            .effective_zone_set(
                athlete_id=
                    proposal.athlete_id,
                sport=
                    proposal.sport,
                environment=
                    proposal.environment,
                discipline=
                    proposal.discipline,
                power_source_id=
                    proposal.power_source_id,
                at=decision_at,
            )
        )

        current_zone_set_id = (
            None
            if current is None
            else current["id"]
        )

        current_ftp_w = (
            None
            if current is None
            else current["ftp_w"]
        )

        baseline_is_current = (
            current_zone_set_id
            == proposal.baseline_zone_set_id
            and current_ftp_w
            == proposal.baseline_ftp_w
        )

        if not baseline_is_current:
            proposal.status = (
                "superseded"
            )
            proposal.decided_at = (
                decision_at
            )
            proposal.decision_note = (
                "Baseline changed before approval"
            )

            self.db.commit()

            raise ProposalConflictError(
                (
                    "FTP proposal is stale because "
                    "the baseline profile changed"
                )
            )

        source_test = self.db.get(
            PerformanceTest,
            proposal
            .source_performance_test_id,
        )

        if source_test is None:
            raise LookupError(
                "Source performance test not found"
            )

        effective_from = (
            payload.effective_from
            if payload.effective_from
            is not None
            else proposal
            .recommended_effective_from
        )

        effective_from = self._aware_utc(
            effective_from
        )

        tested_at = self._aware_utc(
            source_test.tested_at
        )

        if (
            effective_from is None
            or tested_at is None
        ):
            raise ValueError(
                "FTP effective date is invalid"
            )

        if effective_from < tested_at:
            raise ValueError(
                (
                    "FTP cannot become effective "
                    "before its source test"
                )
            )

        try:
            zone_set = (
                profile_service
                .create_zone_set(
                    ZoneSetCreate(
                        athlete_id=
                            proposal.athlete_id,
                        sport=
                            proposal.sport,
                        environment=
                            proposal.environment,
                        discipline=
                            proposal.discipline,
                        power_source_id=
                            proposal
                            .power_source_id,
                        effective_from=
                            effective_from,
                        ftp_w=
                            proposal
                            .proposed_ftp_w,
                        source=
                            "athlete_approved",
                        note=(
                            "Approved FTP proposal "
                            f"{proposal.id}"
                        ),
                    ),
                    commit=False,
                )
            )

            proposal.status = (
                "approved"
            )
            proposal.decided_at = (
                decision_at
            )
            proposal.decision_note = (
                payload.note
            )
            proposal.applied_zone_set_id = (
                zone_set["id"]
            )

            self.db.commit()
            self.db.refresh(
                proposal
            )

        except Exception:
            self.db.rollback()
            raise

        return self._serialize(
            proposal
        )

    def reject_proposal(
        self,
        *,
        proposal_id: uuid.UUID,
        payload:
            PerformanceProposalDecision,
    ) -> dict:
        self._athlete(
            payload.athlete_id
        )

        proposal = self.db.scalar(
            select(
                PerformanceChangeProposal
            )
            .where(
                PerformanceChangeProposal.id
                == proposal_id,
                PerformanceChangeProposal
                .athlete_id
                == payload.athlete_id,
            )
            .with_for_update()
        )

        if proposal is None:
            raise LookupError(
                "Performance proposal not found"
            )

        # Repeated rejection is idempotent.
        if proposal.status == "rejected":
            return self._serialize(
                proposal
            )

        if proposal.status != "pending":
            raise ValueError(
                (
                    "Only a pending proposal "
                    "can be rejected"
                )
            )

        proposal.status = "rejected"
        proposal.decided_at = datetime.now(
            timezone.utc
        )
        proposal.decision_note = (
            payload.note
        )

        self.db.commit()
        self.db.refresh(
            proposal
        )

        return self._serialize(
            proposal
        )

    def _athlete(
        self,
        athlete_id: uuid.UUID,
    ) -> Athlete:
        athlete = self.db.get(
            Athlete,
            athlete_id,
        )

        if athlete is None:
            raise LookupError(
                "Athlete not found"
            )

        return athlete

    @staticmethod
    def _aware_utc(
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        )

    def _serialize(
        self,
        proposal:
            PerformanceChangeProposal,
    ) -> dict:
        power_source = self.db.get(
            Device,
            proposal.power_source_id,
        )

        source_test = self.db.get(
            PerformanceTest,
            proposal
            .source_performance_test_id,
        )

        return {
            "id":
                proposal.id,
            "athlete_id":
                proposal.athlete_id,
            "proposal_type":
                proposal.proposal_type,
            "sport":
                proposal.sport,
            "discipline":
                proposal.discipline,
            "environment":
                proposal.environment,
            "power_source": {
                "id":
                    power_source.id,
                "name":
                    power_source.name,
                "category":
                    power_source.category,
            },
            "source_performance_test": {
                "id":
                    source_test.id,
                "tested_at":
                    self._aware_utc(
                        source_test.tested_at
                    ),
                "test_type":
                    source_test.test_type,
                "protocol":
                    source_test.protocol,
            },
            "baseline_zone_set_id":
                proposal
                .baseline_zone_set_id,
            "baseline_ftp_w":
                proposal.baseline_ftp_w,
            "proposed_ftp_w":
                proposal.proposed_ftp_w,
            "confidence":
                proposal.confidence,
            "recommended_effective_from":
                self._aware_utc(
                    proposal
                    .recommended_effective_from
                ),
            "evidence":
                proposal.evidence,
            "status":
                proposal.status,
            "requires_athlete_approval":
                proposal.status
                == "pending",
            "decision_note":
                proposal.decision_note,
            "decided_at":
                self._aware_utc(
                    proposal.decided_at
                ),
            "applied_zone_set_id":
                proposal
                .applied_zone_set_id,
            "created_at":
                self._aware_utc(
                    proposal.created_at
                ),
            "updated_at":
                self._aware_utc(
                    proposal.updated_at
                ),
        }
