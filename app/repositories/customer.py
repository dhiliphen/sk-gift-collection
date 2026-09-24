from typing import Optional
from sqlalchemy.orm import Session
from app import models
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.Customer, db)

    def get_all_filtered(self, customer_type: Optional[str] = None) -> list[models.Customer]:
        q = self.db.query(models.Customer)
        if customer_type:
            q = q.filter(models.Customer.customer_type == customer_type)
        return q.order_by(models.Customer.name).all()

    def find_duplicate(
        self,
        name: str,
        phone: Optional[str],
        address: Optional[str],
        exclude_id: Optional[int] = None,
    ) -> Optional[models.Customer]:
        """
        Returns an existing customer that has the same name, phone and address.
        Null/empty values are treated as equivalent for the purpose of this check —
        if all three fields match, the record is considered a duplicate.
        """
        q = self.db.query(models.Customer).filter(models.Customer.name == name)

        # Normalise: treat None and "" as the same
        norm_phone = phone or ""
        norm_address = address or ""

        # SQLite-compatible null-safe comparison
        from sqlalchemy import func, case
        q = q.filter(
            func.coalesce(models.Customer.phone, "") == norm_phone
        ).filter(
            func.coalesce(models.Customer.address, "") == norm_address
        )

        if exclude_id is not None:
            q = q.filter(models.Customer.id != exclude_id)

        return q.first()
