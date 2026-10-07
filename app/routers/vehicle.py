from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.vehicle import Vehicle
from app.models.user import User
from app.schemas.vehicle import VehicleCreate, VehicleResponse
from app.core.auth import get_current_user

from app.services.asset_service import (
    create_asset_registry_record,
    generate_asset_artifacts,
)
from app.enums.asset_types import AssetType


router = APIRouter(
    prefix="/vehicles",
    tags=["Vehicles"]
)


@router.post("/", response_model=VehicleResponse)
def create_vehicle(
    vehicle: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a Vehicle and its SAL Master Registry identity
    in one database transaction.

    If either creation fails, neither record is committed.
    """

    new_vehicle = Vehicle(
        owner=vehicle.owner,
        registration_number=vehicle.registration_number,
        vin=vehicle.vin,
        chassis_number=vehicle.chassis_number,
        manufacturer=vehicle.manufacturer,
        model=vehicle.model,
        year=vehicle.year,
        engine_number=vehicle.engine_number,
        color=vehicle.color,
        estimated_value=vehicle.estimated_value,
    )

    try:
        # Add Vehicle to the current transaction.
        db.add(new_vehicle)

        # Flush assigns new_vehicle.id without committing.
        db.flush()

        # Create the SAL identity using the Vehicle's database ID.
        registry = create_asset_registry_record(
            db=db,
            asset_type=AssetType.VEHICLE,
            registry_id=new_vehicle.id,
            owner=new_vehicle.owner,
            estimated_value=new_vehicle.estimated_value,
        )

        # ONE COMMIT:
        # Vehicle + SAL Master Registry are committed together.
        db.commit()

        db.refresh(new_vehicle)
        db.refresh(registry)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "Vehicle could not be registered because a unique "
                "vehicle value already exists."
            )
        )

    except Exception:
        db.rollback()
        raise

    # Generate QR/certificate only after the database transaction
    # has successfully committed.
    try:
        generate_asset_artifacts(
            registry=registry,
            asset_details={
                "registration_number": new_vehicle.registration_number,
                "vin": new_vehicle.vin,
                "chassis_number": new_vehicle.chassis_number,
                "manufacturer": new_vehicle.manufacturer,
                "model": new_vehicle.model,
                "year": new_vehicle.year,
                "engine_number": new_vehicle.engine_number,
                "color": new_vehicle.color,
                "estimated_value": new_vehicle.estimated_value,
            },
        )
    except Exception as artifact_error:
        # The asset itself is already safely registered.
        # Artifact failure must not roll back the database record.
        print(
            "WARNING: Vehicle registered successfully, "
            f"but SAL artifact generation failed: {artifact_error}"
        )

    return new_vehicle


@router.get("/", response_model=list[VehicleResponse])
def get_vehicles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(Vehicle).all()


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == vehicle_id)
        .first()
    )

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found"
        )

    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: int,
    updated: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == vehicle_id)
        .first()
    )

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found"
        )

    vehicle.owner = updated.owner
    vehicle.registration_number = updated.registration_number
    vehicle.vin = updated.vin
    vehicle.chassis_number = updated.chassis_number
    vehicle.manufacturer = updated.manufacturer
    vehicle.model = updated.model
    vehicle.year = updated.year
    vehicle.engine_number = updated.engine_number
    vehicle.color = updated.color
    vehicle.estimated_value = updated.estimated_value

    db.commit()
    db.refresh(vehicle)

    return vehicle


@router.delete("/{vehicle_id}")
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == vehicle_id)
        .first()
    )

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found"
        )

    db.delete(vehicle)
    db.commit()

    return {"message": "Vehicle deleted successfully"}
