from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.repositories.unit import UnitRepository
from app.services.unit import UnitService

router = APIRouter(prefix="/api/units", tags=["units"])


def get_service(db: Session = Depends(get_db)) -> UnitService:
    return UnitService(UnitRepository(db))


@router.get("", response_model=list[schemas.UnitResponse])
def get_all_units(service: UnitService = Depends(get_service)):
    return service.get_all()


@router.get("/{unit_id}", response_model=schemas.UnitResponse)
def get_unit(unit_id: int, service: UnitService = Depends(get_service)):
    return service.get_by_id(unit_id)


@router.post("", response_model=schemas.UnitResponse, status_code=201)
def create_unit(unit: schemas.UnitCreate, service: UnitService = Depends(get_service)):
    return service.create(unit)


@router.put("/{unit_id}", response_model=schemas.UnitResponse)
def update_unit(unit_id: int, unit: schemas.UnitUpdate, service: UnitService = Depends(get_service)):
    return service.update(unit_id, unit)


@router.delete("/{unit_id}", status_code=204)
def delete_unit(unit_id: int, service: UnitService = Depends(get_service)):
    service.delete(unit_id)
