from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.stock import Stock
from app.schemas.stock import StockCreate, StockResponse
from app.core.auth import get_current_user

router = APIRouter(
    prefix="/stocks",
    tags=["Stocks"]
)


@router.get("/", response_model=list[StockResponse])
def get_stocks(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return db.query(Stock).all()


@router.post("/", response_model=StockResponse)
def create_stock(
    stock: StockCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    new_stock = Stock(**stock.model_dump())
    db.add(new_stock)
    db.commit()
    db.refresh(new_stock)
    return new_stock


@router.get("/{stock_id}", response_model=StockResponse)
def get_stock(
    stock_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    stock = db.query(Stock).filter(Stock.id == stock_id).first()

    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    return stock


@router.put("/{stock_id}", response_model=StockResponse)
def update_stock(
    stock_id: int,
    updated: StockCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    stock = db.query(Stock).filter(Stock.id == stock_id).first()

    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    for key, value in updated.model_dump().items():
        setattr(stock, key, value)

    db.commit()
    db.refresh(stock)

    return stock


@router.delete("/{stock_id}")
def delete_stock(
    stock_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    stock = db.query(Stock).filter(Stock.id == stock_id).first()

    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    db.delete(stock)
    db.commit()

    return {"message": "Stock deleted successfully"}