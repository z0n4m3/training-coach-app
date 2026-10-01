import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cycling_equipment import (
    BikeCreate,
    BikeDeviceAssignmentCreate,
    DeviceCreate,
)
from app.services.cycling_equipment_service import (
    CyclingEquipmentService,
)


router = APIRouter(
    prefix="/v1/cycling/equipment",
    tags=["cycling-equipment"],
)


def _handle_error(
    exc: Exception,
):
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


@router.get("/catalog")
def get_catalog():
    return (
        CyclingEquipmentService
        .catalog()
    )


@router.post(
    "/bikes",
    status_code=201,
)
def create_bike(
    payload: BikeCreate,
    db: Session = Depends(get_db),
):
    try:
        return CyclingEquipmentService(
            db
        ).create_bike(payload)
    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.post(
    "/devices",
    status_code=201,
)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
):
    try:
        return CyclingEquipmentService(
            db
        ).create_device(payload)
    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.post(
    "/assignments",
    status_code=201,
)
def create_assignment(
    payload:
        BikeDeviceAssignmentCreate,
    db: Session = Depends(get_db),
):
    try:
        return CyclingEquipmentService(
            db
        ).assign_device_to_bike(
            payload
        )
    except (
        LookupError,
        ValueError,
    ) as exc:
        _handle_error(exc)


@router.get("/inventory")
def get_inventory(
    athlete_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        return CyclingEquipmentService(
            db
        ).inventory(
            athlete_id
        )
    except LookupError as exc:
        _handle_error(exc)
