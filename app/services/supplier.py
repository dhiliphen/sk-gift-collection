from fastapi import HTTPException
from app import models, schemas
from app.repositories.supplier import SupplierRepository


class SupplierService:
    def __init__(self, repo: SupplierRepository):
        self.repo = repo

    def get_all(self) -> list[models.Supplier]:
        return self.repo.get_all()

    def get_by_id(self, supplier_id: int) -> models.Supplier:
        supplier = self.repo.get_by_id(supplier_id)
        if not supplier:
            raise HTTPException(status_code=404, detail="Supplier not found")
        return supplier

    def create(self, data: schemas.SupplierCreate) -> models.Supplier:
        if self.repo.get_by_name(data.name):
            raise HTTPException(status_code=400, detail="Supplier with this name already exists")
        supplier = models.Supplier(**data.model_dump())
        self.repo.save(supplier)
        self.repo.commit()
        return self.repo.refresh(supplier)

    def update(self, supplier_id: int, data: schemas.SupplierUpdate) -> models.Supplier:
        supplier = self.get_by_id(supplier_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(supplier, field, value)
        self.repo.commit()
        return self.repo.refresh(supplier)

    def delete(self, supplier_id: int) -> None:
        supplier = self.get_by_id(supplier_id)
        self.repo.delete(supplier)
        self.repo.commit()
