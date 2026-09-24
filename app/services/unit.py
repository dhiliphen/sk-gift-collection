from fastapi import HTTPException
from app import models, schemas
from app.repositories.unit import UnitRepository


class UnitService:
    def __init__(self, repo: UnitRepository):
        self.repo = repo

    def get_all(self) -> list[models.Unit]:
        return self.repo.get_all_ordered()

    def get_by_id(self, unit_id: int) -> models.Unit:
        unit = self.repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
        return unit

    def create(self, data: schemas.UnitCreate) -> models.Unit:
        if self.repo.get_by_name(data.name):
            raise HTTPException(status_code=400, detail="Unit already exists")
        unit = models.Unit(**data.model_dump())
        self.repo.save(unit)
        self.repo.commit()
        return self.repo.refresh(unit)

    def update(self, unit_id: int, data: schemas.UnitUpdate) -> models.Unit:
        unit = self.get_by_id(unit_id)
        unit.name = data.name
        self.repo.commit()
        return self.repo.refresh(unit)

    def delete(self, unit_id: int) -> None:
        unit = self.get_by_id(unit_id)
        self.repo.delete(unit)
        self.repo.commit()
