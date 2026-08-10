from sqlalchemy.orm import Session

from app.models.country import Country
from app.models.pricing import Pricing


def seed_initial_data(db: Session):

    ghana = (
        db.query(Country)
        .filter(Country.code == "GH")
        .first()
    )

    if not ghana:
        ghana = Country(
            code="GH",
            name="Ghana",
            currency="GHS",
            is_active=True
        )

        db.add(ghana)
        db.commit()
        db.refresh(ghana)

    services = [

        {
            "service_name": "asset_registration",
            "amount": 0,
            "billing_type": "ONE_TIME"
        },

        {
            "service_name": "asset_verification_api",
            "amount": 50,
            "billing_type": "PER_REQUEST"
        },

        {
            "service_name": "enterprise_subscription",
            "amount": 1000,
            "billing_type": "MONTHLY"
        }
    ]

    for service in services:

        exists = (
            db.query(Pricing)
            .filter(
                Pricing.country_id == ghana.id,
                Pricing.service_name == service["service_name"]
            )
            .first()
        )

        if exists:
            continue

        db.add(
            Pricing(
                country_id=ghana.id,
                currency="GHS",
                service_name=service["service_name"],
                amount=service["amount"],
                billing_type=service["billing_type"]
            )
        )

    db.commit()
