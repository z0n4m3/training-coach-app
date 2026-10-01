from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.cycling_equipment import (
    BIKE_DEVICE_ROLES,
    CYCLING_DISCIPLINES,
    DEVICE_CATEGORIES,
    DEVICE_MOBILITY,
    normalize_bike_device_role,
    normalize_cycling_discipline,
    normalize_device_category,
    normalize_device_mobility,
    validate_role_category,
)
from app.models.entities import (
    Athlete,
    Bike,
    BikeDeviceAssignment,
    Device,
)
from app.schemas.cycling_equipment import (
    BikeCreate,
    BikeDeviceAssignmentCreate,
    DeviceCreate,
)


class CyclingEquipmentService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    @staticmethod
    def catalog() -> dict:
        return {
            "disciplines":
                list(CYCLING_DISCIPLINES),
            "device_categories":
                list(DEVICE_CATEGORIES),
            "device_mobility":
                list(DEVICE_MOBILITY),
            "bike_device_roles": {
                role: sorted(categories)
                for role, categories
                in BIKE_DEVICE_ROLES.items()
            },
        }

    def create_bike(
        self,
        payload: BikeCreate,
    ) -> dict:
        self._athlete(
            payload.athlete_id
        )

        name = payload.name.strip()

        existing = self.db.scalar(
            select(Bike).where(
                Bike.athlete_id
                == payload.athlete_id,
                Bike.name == name,
            )
        )

        if existing is not None:
            raise ValueError(
                "Bike name already exists"
            )

        bike = Bike(
            athlete_id=payload.athlete_id,
            name=name,
            discipline=(
                normalize_cycling_discipline(
                    payload.discipline
                )
            ),
            details=payload.details,
            active=True,
        )

        self.db.add(bike)
        self.db.commit()
        self.db.refresh(bike)

        return self._bike(bike)

    def create_device(
        self,
        payload: DeviceCreate,
    ) -> dict:
        self._athlete(
            payload.athlete_id
        )

        name = payload.name.strip()

        existing = self.db.scalar(
            select(Device).where(
                Device.athlete_id
                == payload.athlete_id,
                Device.name == name,
            )
        )

        if existing is not None:
            raise ValueError(
                "Device name already exists"
            )

        device = Device(
            athlete_id=payload.athlete_id,
            name=name,
            category=(
                normalize_device_category(
                    payload.category
                )
            ),
            mobility=(
                normalize_device_mobility(
                    payload.mobility
                )
            ),
            capabilities=payload.capabilities,
            details=payload.details,
            active=True,
        )

        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)

        return self._device(device)

    def assign_device_to_bike(
        self,
        payload:
            BikeDeviceAssignmentCreate,
    ) -> dict:
        self._athlete(
            payload.athlete_id
        )

        bike = self.db.get(
            Bike,
            payload.bike_id,
        )

        if (
            bike is None
            or bike.athlete_id
            != payload.athlete_id
        ):
            raise LookupError(
                "Bike not found"
            )

        device = self.db.get(
            Device,
            payload.device_id,
        )

        if (
            device is None
            or device.athlete_id
            != payload.athlete_id
        ):
            raise LookupError(
                "Device not found"
            )

        role = normalize_bike_device_role(
            payload.role
        )

        validate_role_category(
            role=role,
            category=device.category,
        )

        existing = self.db.scalar(
            select(
                BikeDeviceAssignment
            ).where(
                BikeDeviceAssignment.bike_id
                == bike.id,
                BikeDeviceAssignment.device_id
                == device.id,
                BikeDeviceAssignment.role
                == role,
            )
        )

        if existing is not None:
            raise ValueError(
                "Assignment already exists"
            )

        if device.mobility == "fixed":
            other_bike = self.db.scalar(
                select(
                    BikeDeviceAssignment
                ).where(
                    BikeDeviceAssignment.device_id
                    == device.id,
                    BikeDeviceAssignment.bike_id
                    != bike.id,
                )
            )

            if other_bike is not None:
                raise ValueError(
                    (
                        "Fixed device is already "
                        "assigned to another bike"
                    )
                )

        assignment = BikeDeviceAssignment(
            athlete_id=payload.athlete_id,
            bike_id=bike.id,
            device_id=device.id,
            role=role,
            notes=payload.notes,
        )

        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)

        return {
            "id": assignment.id,
            "bike_id": bike.id,
            "device_id": device.id,
            "role": assignment.role,
        }

    def inventory(
        self,
        athlete_id: uuid.UUID,
    ) -> dict:
        self._athlete(athlete_id)

        bikes = self.db.scalars(
            select(Bike)
            .where(
                Bike.athlete_id
                == athlete_id
            )
            .order_by(Bike.name)
        ).all()

        devices = self.db.scalars(
            select(Device)
            .where(
                Device.athlete_id
                == athlete_id
            )
            .order_by(
                Device.category,
                Device.name,
            )
        ).all()

        assignments = self.db.scalars(
            select(
                BikeDeviceAssignment
            ).where(
                BikeDeviceAssignment.athlete_id
                == athlete_id
            )
        ).all()

        device_by_id = {
            item.id: item
            for item in devices
        }

        bike_rows = []

        for bike in bikes:
            row = self._bike(bike)

            row["device_assignments"] = [
                {
                    "role":
                        assignment.role,
                    "device":
                        self._device(
                            device_by_id[
                                assignment.device_id
                            ]
                        ),
                }
                for assignment in assignments
                if assignment.bike_id
                == bike.id
            ]

            bike_rows.append(row)

        shared = [
            self._device(device)
            for device in devices
            if device.mobility == "shared"
        ]

        trainers = [
            self._device(device)
            for device in devices
            if device.category == "trainer"
        ]

        return {
            "bikes": bike_rows,
            "devices": [
                self._device(device)
                for device in devices
            ],
            "shared_devices": shared,
            "trainers": trainers,
        }

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
    def _bike(
        bike: Bike,
    ) -> dict:
        return {
            "id": bike.id,
            "athlete_id": bike.athlete_id,
            "name": bike.name,
            "discipline": bike.discipline,
            "details": bike.details,
            "active": bike.active,
        }

    @staticmethod
    def _device(
        device: Device,
    ) -> dict:
        return {
            "id": device.id,
            "athlete_id": device.athlete_id,
            "name": device.name,
            "category": device.category,
            "mobility": device.mobility,
            "capabilities":
                device.capabilities,
            "details": device.details,
            "active": device.active,
        }
