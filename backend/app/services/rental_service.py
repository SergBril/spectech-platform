from sqlalchemy.orm import Session
from app.models.rental import Rental, RentalItem, RentalStatus
from app.schemas.rental import RentalCreate
from datetime import datetime
from decimal import Decimal
from fastapi import HTTPException

class RentalService:
    @staticmethod
    def create_rental(db: Session, rental_in: RentalCreate) -> Rental:
        # 1. Расчет базовой стоимости
        base_price = Decimal("0.0")
        rental_items = []
        
        for item_in in rental_in.items:
            # TODO: Здесь можно добавить проверку, что оборудование свободно в эти даты
            item_total = item_in.unit_price * item_in.quantity
            base_price += item_total
            
            rental_items.append(
                RentalItem(
                    equipment_id=item_in.equipment_id,
                    quantity=item_in.quantity,
                    unit_price=item_in.unit_price
                )
            )
            
        # 2. Учет скидки
        discount = rental_in.discount or Decimal("0.0")
        total_amount = max(base_price - discount, Decimal("0.0"))
        
        # 3. Создание объекта аренды
        db_rental = Rental(
            client_id=rental_in.client_id,
            start_date=rental_in.start_date,
            end_date=rental_in.end_date,
            base_price=base_price,
            discount=discount,
            total_amount=total_amount,
            status=RentalStatus.DRAFT,
            items=rental_items
        )
        
        db.add(db_rental)
        db.commit()
        db.refresh(db_rental)
        return db_rental

    @staticmethod
    def close_rental(db: Session, rental_id: int) -> Rental:
        rental = db.query(Rental).filter(Rental.id == rental_id).first()
        if not rental:
            raise HTTPException(status_code=404, detail="Аренда не найдена")
            
        rental.actual_return_date = datetime.utcnow()
        rental.status = RentalStatus.COMPLETED
        
        # TODO: В будущем здесь будет логика пересчета (штрафы за просрочку или возврат за досрочное возвращение)
        
        db.commit()
        db.refresh(rental)
        return rental