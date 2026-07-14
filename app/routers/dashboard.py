from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.core.auth import get_current_user
from app.models.user import User

# Import all asset models
from app.models.land import Land
from app.models.vehicle import Vehicle
from app.models.gold import Gold
from app.models.diamond import Diamond
from app.models.bank_account import BankAccount
from app.models.company import Company
from app.models.stock import Stock
from app.models.bond import Bond
from app.models.insurance import Insurance
from app.models.business import Business
from app.models.intellectual_property import IntellectualProperty
from app.models.crypto_wallet import CryptoWallet
from app.models.farm import Farm

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)
@router.get("/")
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    data = {
        "lands": db.query(Land).count(),
        "vehicles": db.query(Vehicle).count(),
        "gold": db.query(Gold).count(),
        "diamonds": db.query(Diamond).count(),
        "bank_accounts": db.query(BankAccount).count(),
        "companies": db.query(Company).count(),
        "stocks": db.query(Stock).count(),
        "bonds": db.query(Bond).count(),
        "insurance": db.query(Insurance).count(),
        "businesses": db.query(Business).count(),
        "intellectual_properties": db.query(IntellectualProperty).count(),
        "crypto_wallets": db.query(CryptoWallet).count(),
        "farms": db.query(Farm).count(),
    }

    data["total_assets"] = sum(data.values())

    return data