import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.performance_proposals import (
    FtpProposalApproval,
    FtpProposalCreate,
    PerformanceProposalDecision,
)
from app.services.performance_proposal_service import (
    PerformanceProposalService,
    ProposalConflictError,
)


router = APIRouter(
    prefix="/v1/performance-proposals",
    tags=["performance-proposals"],
)


def _handle_error(
    exc: Exception,
):
    if isinstance(
        exc,
        ProposalConflictError,
    ):
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    if isinstance(
        exc,
        LookupError,
    ):
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    raise HTTPException(
        status_code=400,
        detail=str(exc),
    ) from exc


@router.post(
    "/ftp",
    status_code=201,
)
def create_ftp_proposal(
    payload: FtpProposalCreate,
    db: Session = Depends(get_db),
):
    try:
        return PerformanceProposalService(
            db
        ).create_ftp_proposal(
            payload
        )

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.get("")
def list_performance_proposals(
    athlete_id: uuid.UUID,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        return {
            "items":
                PerformanceProposalService(
                    db
                ).list(
                    athlete_id=
                        athlete_id,
                    status=status,
                )
        }

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.post(
    "/{proposal_id}/approve",
)
def approve_ftp_proposal(
    proposal_id: uuid.UUID,
    payload: FtpProposalApproval,
    db: Session = Depends(get_db),
):
    try:
        return PerformanceProposalService(
            db
        ).approve_ftp_proposal(
            proposal_id=proposal_id,
            payload=payload,
        )

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.post(
    "/{proposal_id}/reject",
)
def reject_performance_proposal(
    proposal_id: uuid.UUID,
    payload:
        PerformanceProposalDecision,
    db: Session = Depends(get_db),
):
    try:
        return PerformanceProposalService(
            db
        ).reject_proposal(
            proposal_id=proposal_id,
            payload=payload,
        )

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.get("/{proposal_id}")
def get_performance_proposal(
    proposal_id: uuid.UUID,
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        return PerformanceProposalService(
            db
        ).get(
            athlete_id=athlete_id,
            proposal_id=proposal_id,
        )

    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)
