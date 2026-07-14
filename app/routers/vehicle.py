from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.vehicle import Vehicle
from app.models.user import User
from app.schemas.vehicle import VehicleCreate, VehicleResponse
from app.core.auth import get_current_user

from app.services.asset_service import register_asset
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
    new_vehicle = Vehicle(
        owner=vehicle.owner,
        registration_number=vehicle.registration_number,
        vin=vehicle.vin,
        manufacturer=vehicle.manufacturer,
        model=vehicle.model,
        year=vehicle.year,
        engine_number=vehicle.engine_number,
        color=vehicle.color,
        estimated_value=vehicle.estimated_value
    )

    db.add(new_vehicle)
    db.commit()
    db.refresh(new_vehicle)

    # Register the vehicle in the SAL Master Registry
    register_asset(
        db=db,
        asset_type=AssetType.VEHICLE,
        registry_id=new_vehicle.id,
        owner=new_vehicle.owner,
        estimated_value=new_vehicle.estimated_value,
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
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()

    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: int,
    updated: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()

    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    vehicle.owner = updated.owner
    vehicle.registration_number = updated.registration_number
    vehicle.vin = updated.vin
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
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()

    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    db.delete(vehicle)
    db.commit()

    return {"message": "Vehicle deleted successfully"}