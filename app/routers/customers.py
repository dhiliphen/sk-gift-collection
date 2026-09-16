from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[schemas.CustomerResponse])
def get_all_customers(customer_type: str = None, db: Session = Depends(get_db)):
    q = db.query(models.Customer)
    if customer_type:
        q = q.filter(models.Customer.customer_type == customer_type)
    return q.order_by(models.Customer.name).all()


@router.get("/{customer_id}", response_model=schemas.CustomerResponse)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c


@router.post("", response_model=schemas.CustomerResponse, status_code=201)
def create_customer(customer: schemas.CustomerCreate, db: Session = Depends(get_db)):
    db_c = models.Customer(**customer.dict())
    db.add(db_c)
    db.commit()
    db.refresh(db_c)
    return db_c


@router.put("/{customer_id}", response_model=schemas.CustomerResponse)
def update_customer(customer_id: int, customer: schemas.CustomerUpdate, db: Session = Depends(get_db)):
    db_c = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_c:
        raise HTTPException(status_code=404, detail="Customer not found")
    for field, value in customer.dict(exclude_unset=True).items():
        setattr(db_c, field, value)
    db.commit()
    db.refresh(db_c)
    return db_c


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    db_c = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not db_c:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.delete(db_c)
    db.commit()
