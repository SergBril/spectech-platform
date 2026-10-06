from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from app.models.rental import RentalStatus

class RentalItemCreate(BaseModel):
    equipment_id: int
    quantity: int = 1
    unit_price: Decimal = Field(..., gt=0)

class RentalCreate(BaseModel):
    client_id: int
    start_date: datetime
    end_date: datetime
    items: List[RentalItemCreate]
    discount: Optional[Decimal] = 0.0

class RentalRead(BaseModel):
    id: int
    client_id: int
    status: RentalStatus
    start_date: datetime
    end_date: datetime
    total_amount: Decimal
    created_at: datetime

    class Config:
        from_attributes = True