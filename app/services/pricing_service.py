from sqlalchemy.orm import Session

from app.models.pricing import Pricing
from app.models.country import Country


class PricingService:

    @staticmethod
    def get_price(
        db: Session,
        service_name: str,
        country_code: str
    ):
        country = (
            db.query(Country)
            .filter(Country.code == country_code)
            .first()
        )

        if not country:
            return None

        pricing = (
            db.query(Pricing)
            .filter(
                Pricing.country_id == country.id,
                Pricing.service_name == service_name,
                Pricing.active == True
            )
            .first()
        )

        if not pricing:
            return None

        subtotal = pricing.amount

        discount = subtotal * (
            pricing.discount_percent / 100
        )

        subtotal -= discount

        tax = subtotal * (
            pricing.tax_percent / 100
        )

        total = subtotal + tax

        return {
            "service": pricing.service_name,
            "country": country.name,
            "currency": pricing.currency,
            "base_price": pricing.amount,
            "discount_percent": pricing.discount_percent,
            "tax_percent": pricing.tax_percent,
            "total": round(total, 2)
        }
