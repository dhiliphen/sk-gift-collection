from typing import Optional
from fastapi import HTTPException
from app import models, schemas
from app.repositories.customer import CustomerRepository


class CustomerService:
    def __init__(self, repo: CustomerRepository):
        self.repo = repo

    def get_all(self, customer_type: Optional[str] = None) -> list[models.Customer]:
        return self.repo.get_all_filtered(customer_type=customer_type)

    def get_by_id(self, customer_id: int) -> models.Customer:
        customer = self.repo.get_by_id(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return customer

    def create(self, data: schemas.CustomerCreate) -> models.Customer:
        if self.repo.find_duplicate(data.name, data.phone, data.address):
            raise HTTPException(
                status_code=400,
                detail=(
                    "A customer with this name, phone number and address already exists. "
                    "If this is a different customer, please provide a different phone number or address."
                ),
            )
        customer = models.Customer(**data.model_dump())
        self.repo.save(customer)
        self.repo.commit()
        return self.repo.refresh(customer)

    def update(self, customer_id: int, data: schemas.CustomerUpdate) -> models.Customer:
        customer = self.get_by_id(customer_id)
        # Compute what the record will look like after the update
        updated = data.model_dump(exclude_unset=True)
        new_name = updated.get("name", customer.name)
        new_phone = updated.get("phone", customer.phone)
        new_address = updated.get("address", customer.address)
        if self.repo.find_duplicate(new_name, new_phone, new_address, exclude_id=customer_id):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Another customer with this name, phone number and address already exists. "
                    "Please use a different phone number or address."
                ),
            )
        for field, value in updated.items():
            setattr(customer, field, value)
        self.repo.commit()
        return self.repo.refresh(customer)

    def delete(self, customer_id: int) -> None:
        customer = self.get_by_id(customer_id)
        self.repo.delete(customer)
        self.repo.commit()
