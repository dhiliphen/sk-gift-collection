from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.repositories.category import CategoryRepository
from app.services.category import CategoryService

router = APIRouter(prefix="/api/categories", tags=["categories"])


def get_service(db: Session = Depends(get_db)) -> CategoryService:
    return CategoryService(CategoryRepository(db))


@router.get("", response_model=list[schemas.CategoryResponse])
def get_all_categories(service: CategoryService = Depends(get_service)):
    return service.get_all()


@router.get("/{category_id}", response_model=schemas.CategoryResponse)
def get_category(category_id: int, service: CategoryService = Depends(get_service)):
    return service.get_by_id(category_id)


@router.post("", response_model=schemas.CategoryResponse, status_code=201)
def create_category(category: schemas.CategoryCreate, service: CategoryService = Depends(get_service)):
    return service.create(category)


@router.put("/{category_id}", response_model=schemas.CategoryResponse)
def update_category(category_id: int, category: schemas.CategoryUpdate, service: CategoryService = Depends(get_service)):
    return service.update(category_id, category)


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, service: CategoryService = Depends(get_service)):
    service.delete(category_id)
