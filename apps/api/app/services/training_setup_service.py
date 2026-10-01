from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.cycling_equipment import (
    normalize_training_environment,
    normalize_training_setup_role,
    validate_training_setup_role_category,
)
from app.models.entities import (
    Athlete,
    Bike,
    BikeDeviceAssignment,
    Device,
    TrainingSetup,
    TrainingSetupDevice,
)
from app.schemas.training_setup import (
    TrainingSetupCreate,
)


POWER_ROLES = {
    "primary_power_source",
    "secondary_power_source",
}


class TrainingSetupService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def create(
        self,
        payload: TrainingSetupCreate,
    ) -> dict:
        athlete = self.db.get(
            Athlete,
            payload.athlete_id,
        )

        if athlete is None:
            raise LookupError(
                "Athlete not found"
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

        if not bike.active:
            raise ValueError(
                "Bike is inactive"
            )

        name = payload.name.strip()

        existing = self.db.scalar(
            select(TrainingSetup).where(
                TrainingSetup.athlete_id
                == payload.athlete_id,
                TrainingSetup.name
                == name,
            )
        )

        if existing is not None:
            raise ValueError(
                "Training setup name already exists"
            )

        environment = (
            normalize_training_environment(
                payload.environment
            )
        )

        devices_by_role: dict[
            str,
            Device,
        ] = {}

        for raw_role, device_id in (
            payload.device_roles.items()
        ):
            role = (
                normalize_training_setup_role(
                    raw_role
                )
            )

            if role in devices_by_role:
                raise ValueError(
                    (
                        "Training setup contains "
                        "duplicate normalized role"
                    )
                )

            device = self.db.get(
                Device,
                device_id,
            )

            if (
                device is None
                or device.athlete_id
                != payload.athlete_id
            ):
                raise LookupError(
                    (
                        f"Device for role "
                        f"{role} not found"
                    )
                )

            if not device.active:
                raise ValueError(
                    (
                        f"Device for role "
                        f"{role} is inactive"
                    )
                )

            validate_training_setup_role_category(
                role=role,
                category=device.category,
            )

            devices_by_role[
                role
            ] = device

        self._validate_configuration(
            athlete_id=payload.athlete_id,
            bike=bike,
            environment=environment,
            devices_by_role=
                devices_by_role,
        )

        setup = TrainingSetup(
            athlete_id=payload.athlete_id,
            name=name,
            sport="cycling",
            discipline=bike.discipline,
            environment=environment,
            bike_id=bike.id,
            notes=payload.notes,
            active=True,
        )

        self.db.add(setup)
        self.db.flush()

        for role, device in (
            devices_by_role.items()
        ):
            self.db.add(
                TrainingSetupDevice(
                    athlete_id=
                        payload.athlete_id,
                    training_setup_id=
                        setup.id,
                    device_id=device.id,
                    role=role,
                )
            )

        self.db.commit()
        self.db.refresh(setup)

        return self._serialize(
            setup
        )

    def list(
        self,
        athlete_id: uuid.UUID,
    ) -> list[dict]:
        athlete = self.db.get(
            Athlete,
            athlete_id,
        )

        if athlete is None:
            raise LookupError(
                "Athlete not found"
            )

        setups = self.db.scalars(
            select(TrainingSetup)
            .where(
                TrainingSetup.athlete_id
                == athlete_id
            )
            .order_by(
                TrainingSetup.name
            )
        ).all()

        return [
            self._serialize(setup)
            for setup in setups
        ]

    def get(
        self,
        athlete_id: uuid.UUID,
        setup_id: uuid.UUID,
    ) -> dict:
        setup = self.db.scalar(
            select(TrainingSetup).where(
                TrainingSetup.id
                == setup_id,
                TrainingSetup.athlete_id
                == athlete_id,
            )
        )

        if setup is None:
            raise LookupError(
                "Training setup not found"
            )

        return self._serialize(
            setup
        )

    def _validate_configuration(
        self,
        *,
        athlete_id: uuid.UUID,
        bike: Bike,
        environment: str,
        devices_by_role:
            dict[str, Device],
    ) -> None:
        trainer = devices_by_role.get(
            "trainer"
        )

        if (
            environment == "outdoor"
            and trainer is not None
        ):
            raise ValueError(
                (
                    "Outdoor setup cannot "
                    "contain a trainer"
                )
            )

        primary = devices_by_role.get(
            "primary_power_source"
        )

        secondary = devices_by_role.get(
            "secondary_power_source"
        )

        if (
            secondary is not None
            and primary is None
        ):
            raise ValueError(
                (
                    "Secondary power source "
                    "requires primary power source"
                )
            )

        if (
            primary is not None
            and secondary is not None
            and primary.id == secondary.id
        ):
            raise ValueError(
                (
                    "Primary and secondary "
                    "power sources must differ"
                )
            )

        for role in POWER_ROLES:
            device = devices_by_role.get(
                role
            )

            if device is None:
                continue

            if device.category == "trainer":
                if environment != "indoor":
                    raise ValueError(
                        (
                            "Trainer power source "
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
                            "Trainer cannot be used "
                            "as power source without "
                            "power_measurement capability"
                        )
                    )

                if (
                    trainer is None
                    or trainer.id
                    != device.id
                ):
                    raise ValueError(
                        (
                            "Trainer used as a power "
                            "source must also be the "
                            "trainer in this setup"
                        )
                    )

            elif (
                device.category
                == "power_meter"
            ):
                assignment = self.db.scalar(
                    select(
                        BikeDeviceAssignment
                    ).where(
                        BikeDeviceAssignment.athlete_id
                        == athlete_id,
                        BikeDeviceAssignment.bike_id
                        == bike.id,
                        BikeDeviceAssignment.device_id
                        == device.id,
                        BikeDeviceAssignment.role
                        == "power_source",
                    )
                )

                if assignment is None:
                    raise ValueError(
                        (
                            "Power meter is not "
                            "assigned to this bike"
                        )
                    )

    def _serialize(
        self,
        setup: TrainingSetup,
    ) -> dict:
        bike = self.db.get(
            Bike,
            setup.bike_id,
        )

        rows = self.db.scalars(
            select(TrainingSetupDevice)
            .where(
                TrainingSetupDevice.training_setup_id
                == setup.id
            )
            .order_by(
                TrainingSetupDevice.role
            )
        ).all()

        device_roles = {}

        for row in rows:
            device = self.db.get(
                Device,
                row.device_id,
            )

            device_roles[
                row.role
            ] = {
                "id": device.id,
                "name": device.name,
                "category":
                    device.category,
                "capabilities":
                    device.capabilities,
            }

        return {
            "id": setup.id,
            "athlete_id":
                setup.athlete_id,
            "name": setup.name,
            "sport": setup.sport,
            "discipline":
                setup.discipline,
            "environment":
                setup.environment,
            "bike": {
                "id": bike.id,
                "name": bike.name,
                "discipline":
                    bike.discipline,
            },
            "device_roles":
                device_roles,
            "notes": setup.notes,
            "active": setup.active,
        }
