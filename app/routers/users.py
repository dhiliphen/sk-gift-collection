from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.auth import require_role, get_current_username, get_current_user
from app.audit import record
from app.repositories.user import UserRepository
from app.services.user import UserService

router = APIRouter(prefix="/api/users", tags=["users"])


def get_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(UserRepository(db))


@router.get("/me", response_model=schemas.UserResponse)
def get_me(user=Depends(get_current_user)):
    """Lets the frontend know who's logged in and their role, so it can
    show/hide admin-only sections (Users, Audit Log)."""
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user


@router.get("", response_model=list[schemas.UserResponse], dependencies=[Depends(require_role("ADMIN"))])
def get_all_users(service: UserService = Depends(get_service)):
    return service.get_all()


@router.post("", response_model=schemas.UserResponse, status_code=201, dependencies=[Depends(require_role("ADMIN"))])
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    service: UserService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    created = service.create(user)
    record(db, username, "CREATE_USER", "user", created.id,
           new_value=schemas.UserResponse.model_validate(created).model_dump(mode="json"))
    return created


@router.put("/{user_id}", response_model=schemas.UserResponse, dependencies=[Depends(require_role("ADMIN"))])
def update_user(
    user_id: int,
    user: schemas.UserUpdate,
    db: Session = Depends(get_db),
    service: UserService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    old = schemas.UserResponse.model_validate(service.get_by_id(user_id)).model_dump(mode="json")
    updated = service.update(user_id, user)
    record(db, username, "UPDATE_USER", "user", user_id,
           old_value=old, new_value=schemas.UserResponse.model_validate(updated).model_dump(mode="json"))
    return updated
