from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
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
def create_customer(customer: schemas.CustomerCreate, service: CustomerService = Depends(get_service)):
    return service.create(customer)


@router.put("/{customer_id}", response_model=schemas.CustomerResponse)
def update_customer(customer_id: int, customer: schemas.CustomerUpdate, service: CustomerService = Depends(get_service)):
    return service.update(customer_id, customer)


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: int, service: CustomerService = Depends(get_service)):
    service.delete(customer_id)
