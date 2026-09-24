from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.repositories.supplier import SupplierRepository
from app.services.supplier import SupplierService

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


def get_service(db: Session = Depends(get_db)) -> SupplierService:
    return SupplierService(SupplierRepository(db))


@router.get("", response_model=list[schemas.SupplierResponse])
def get_all_suppliers(service: SupplierService = Depends(get_service)):
    return service.get_all()


@router.get("/{supplier_id}", response_model=schemas.SupplierResponse)
def get_supplier(supplier_id: int, service: SupplierService = Depends(get_service)):
    return service.get_by_id(supplier_id)


@router.post("", response_model=schemas.SupplierResponse, status_code=201)
def create_supplier(supplier: schemas.SupplierCreate, service: SupplierService = Depends(get_service)):
    return service.create(supplier)


@router.put("/{supplier_id}", response_model=schemas.SupplierResponse)
def update_supplier(supplier_id: int, supplier: schemas.SupplierUpdate, service: SupplierService = Depends(get_service)):
    return service.update(supplier_id, supplier)


@router.delete("/{supplier_id}", status_code=204)
def delete_supplier(supplier_id: int, service: SupplierService = Depends(get_service)):
    service.delete(supplier_id)
