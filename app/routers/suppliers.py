from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.auth import get_current_username
from app.audit import record
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
def create_supplier(
    supplier: schemas.SupplierCreate,
    db: Session = Depends(get_db),
    service: SupplierService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    created = service.create(supplier)
    record(db, username, "CREATE_SUPPLIER", "supplier", created.id,
           new_value=schemas.SupplierResponse.model_validate(created).model_dump(mode="json"))
    return created


@router.put("/{supplier_id}", response_model=schemas.SupplierResponse)
def update_supplier(
    supplier_id: int,
    supplier: schemas.SupplierUpdate,
    db: Session = Depends(get_db),
    service: SupplierService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    old = schemas.SupplierResponse.model_validate(service.get_by_id(supplier_id)).model_dump(mode="json")
    updated = service.update(supplier_id, supplier)
    record(db, username, "UPDATE_SUPPLIER", "supplier", supplier_id,
           old_value=old, new_value=schemas.SupplierResponse.model_validate(updated).model_dump(mode="json"))
    return updated


@router.delete("/{supplier_id}", status_code=204)
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    service: SupplierService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    old = schemas.SupplierResponse.model_validate(service.get_by_id(supplier_id)).model_dump(mode="json")
    service.delete(supplier_id)
    record(db, username, "DELETE_SUPPLIER", "supplier", supplier_id, old_value=old)
