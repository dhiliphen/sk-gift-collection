from fastapi import HTTPException
from app import models, schemas
from app.repositories.category import CategoryRepository


class CategoryService:
    def __init__(self, repo: CategoryRepository):
        self.repo = repo

    def get_all(self) -> list[models.Category]:
        return self.repo.get_all_ordered()

    def get_by_id(self, category_id: int) -> models.Category:
        category = self.repo.get_by_id(category_id)
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")
        return category

    def create(self, data: schemas.CategoryCreate) -> models.Category:
        if self.repo.get_by_name(data.name):
            raise HTTPException(status_code=400, detail="Category already exists")
        category = models.Category(**data.model_dump())
        self.repo.save(category)
        self.repo.commit()
        return self.repo.refresh(category)

    def update(self, category_id: int, data: schemas.CategoryUpdate) -> models.Category:
        category = self.get_by_id(category_id)
        category.name = data.name
        self.repo.commit()
        return self.repo.refresh(category)

    def delete(self, category_id: int) -> None:
        category = self.get_by_id(category_id)
        self.repo.delete(category)
        self.repo.commit()
