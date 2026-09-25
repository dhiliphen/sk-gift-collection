from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.auth import get_current_username
from app.audit import record
from app.repositories.customer import CustomerRepository
from app.services.customer import CustomerService

router = APIRouter(prefix="/api/customers", tags=["customers"])


def get_service(db: Session = Depends(get_db)) -> CustomerService:
    return CustomerService(CustomerRepository(db))


@router.get("", response_model=list[schemas.CustomerResponse])
def get_all_customers(customer_type: str = None, service: CustomerService = Depends(get_service)):
    return service.get_all(customer_type=customer_type)


@router.get("/{customer_id}", response_model=schemas.CustomerResponse)
def get_customer(customer_id: int, service: CustomerService = Depends(get_service)):
    return service.get_by_id(customer_id)


@router.post("", response_model=schemas.CustomerResponse, status_code=201)
def create_customer(
    customer: schemas.CustomerCreate,
    db: Session = Depends(get_db),
    service: CustomerService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    created = service.create(customer)
    record(db, username, "CREATE_CUSTOMER", "customer", created.id,
           new_value=schemas.CustomerResponse.model_validate(created).model_dump(mode="json"))
    return created


@router.put("/{customer_id}", response_model=schemas.CustomerResponse)
def update_customer(
    customer_id: int,
    customer: schemas.CustomerUpdate,
    db: Session = Depends(get_db),
    service: CustomerService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    old = schemas.CustomerResponse.model_validate(service.get_by_id(customer_id)).model_dump(mode="json")
    updated = service.update(customer_id, customer)
    record(db, username, "UPDATE_CUSTOMER", "customer", customer_id,
           old_value=old, new_value=schemas.CustomerResponse.model_validate(updated).model_dump(mode="json"))
    return updated


@router.delete("/{customer_id}", status_code=204)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    service: CustomerService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    old = schemas.CustomerResponse.model_validate(service.get_by_id(customer_id)).model_dump(mode="json")
    service.delete(customer_id)
    record(db, username, "DELETE_CUSTOMER", "customer", customer_id, old_value=old)
