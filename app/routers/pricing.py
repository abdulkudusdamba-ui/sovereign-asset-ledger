from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.pricing import Pricing
from app.schemas.pricing import PricingCreate, PricingResponse
from app.services.pricing_service import PricingService

router = APIRouter(
    prefix="/pricing",
    tags=["Pricing"]
)


@router.post("/", response_model=PricingResponse)
def create_pricing(
    pricing: PricingCreate,
    db: Session = Depends(get_db)
):
    new_pricing = Pricing(
        service_name=pricing.service_name,
        country_id=pricing.country_id,
        currency=pricing.currency,
        amount=pricing.amount,
        billing_type=pricing.billing_type,
        tax_percent=pricing.tax_percent,
        discount_percent=pricing.discount_percent,
    )

    db.add(new_pricing)
    db.commit()
    db.refresh(new_pricing)

    return new_pricing


@router.get("/", response_model=list[PricingResponse])
def get_pricing(
    db: Session = Depends(get_db)
):
    return db.query(Pricing).all()


@router.get("/{pricing_id}", response_model=PricingResponse)
def get_pricing_by_id(
    pricing_id: int,
    db: Session = Depends(get_db)
):
    pricing = (
        db.query(Pricing)
        .filter(Pricing.id == pricing_id)
        .first()
    )

    if not pricing:
        raise HTTPException(
            status_code=404,
            detail="Pricing record not found"
        )

    return pricing


@router.get("/calculate/{country_code}/{service_name}")
def calculate_price(
    country_code: str,
    service_name: str,
    db: Session = Depends(get_db)
):
    result = PricingService.get_price(
        db,
        service_name,
        country_code
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Pricing not found"
        )

    return result
