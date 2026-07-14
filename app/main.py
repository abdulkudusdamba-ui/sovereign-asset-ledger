from app.routers import certificate
from app.routers import verification
from app.routers.dashboard import router as dashboard_router
from app.models.asset_registry import AssetRegistry
from app.routers import asset_registry
from app.models.farm import Farm
from app.routers import farm
from app.models.crypto_wallet import CryptoWallet
from app.routers import crypto_wallet
from app.models.intellectual_property import IntellectualProperty
from app.routers import intellectual_property
from app.models.business import Business
from app.routers import business
from app.routers import insurance
from app.models.bond import Bond
from app.routers import bond
from app.models.stock import Stock
from app.routers import stock
from app.models.company import Company
from app.routers import company
from app.models.bank_account import BankAccount
from app.routers import bank_account
from app.models.diamond import Diamond
from app.routers import diamond
from app.models.gold import Gold
from app.routers import gold
from app.models.vehicle import Vehicle
from app.routers import vehicle
from app.routers import land
from fastapi import FastAPI
from app.models.land import Land
from app.database.database import Base, engine
from app.models.asset import Asset
from app.models.user import User
from app.routers import asset
from app.routers.user import router as user_router

app = FastAPI(
    title="Sovereign Asset Ledger",
    version="0.1.0"
)

# Create all database tables
Base.metadata.create_all(bind=engine)

# Register routers
app.include_router(certificate.router)
app.include_router(verification.router)
app.include_router(dashboard_router)
app.include_router(asset.router)
app.include_router(user_router)
app.include_router(land.router)
app.include_router(vehicle.router)
app.include_router(gold.router)
app.include_router(diamond.router)
app.include_router(bank_account.router) 
app.include_router(company.router)
app.include_router(stock.router)
app.include_router(bond.router)
app.include_router(insurance.router)
app.include_router(business.router)
app.include_router(intellectual_property.router)
app.include_router(crypto_wallet.router)
app.include_router(farm.router)
app.include_router(asset_registry.router)
@app.get("/")
def home():
    return {
        "message": "Sovereign Asset Ledger Online"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }