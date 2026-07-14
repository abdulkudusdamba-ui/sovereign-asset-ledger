from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.asset_registry import AssetRegistry

router = APIRouter(
    prefix="/certificate",
    tags=["Certificate"]
)


@router.get("/{sal_id}")
def get_certificate(sal_id: str, db: Session = Depends(get_db)):
    asset = (
        db.query(AssetRegistry)
        .filter(AssetRegistry.sal_id == sal_id)
        .first()
    )

    if not asset:
        raise HTTPException(status_code=404, detail="Certificate not found")

    return {
        "certificate": "Sovereign Asset Ledger",
        "sal_id": asset.sal_id,
        "owner": asset.owner,
        "asset_type": asset.asset_type,
        "registry_id": asset.registry_id,
        "estimated_value": asset.estimated_value,
        "status": asset.status,
        "verified": True
    }