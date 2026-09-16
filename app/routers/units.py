from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/units", tags=["units"])


@router.get("", response_model=list[schemas.UnitResponse])
def get_all_units(db: Session = Depends(get_db)):
    return db.query(models.Unit).order_by(models.Unit.name).all()


@router.get("/{unit_id}", response_model=schemas.UnitResponse)
def get_unit(unit_id: int, db: Session = Depends(get_db)):
    unit = db.query(models.Unit).filter(models.Unit.id == unit_id).first()
    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


@router.post("", response_model=schemas.UnitResponse, status_code=201)
def create_unit(unit: schemas.UnitCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Unit).filter(models.Unit.name == unit.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Unit already exists")
    db_unit = models.Unit(**unit.dict())
    db.add(db_unit)
    db.commit()
    db.refresh(db_unit)
    return db_unit


@router.put("/{unit_id}", response_model=schemas.UnitResponse)
def update_unit(unit_id: int, unit: schemas.UnitUpdate, db: Session = Depends(get_db)):
    db_unit = db.query(models.Unit).filter(models.Unit.id == unit_id).first()
    if not db_unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    db_unit.name = unit.name
    db.commit()
    db.refresh(db_unit)
    return db_unit


@router.delete("/{unit_id}", status_code=204)
def delete_unit(unit_id: int, db: Session = Depends(get_db)):
    db_unit = db.query(models.Unit).filter(models.Unit.id == unit_id).first()
    if not db_unit:
        raise HTTPException(status_code=404, detail="Unit not found")
    db.delete(db_unit)
    db.commit()
