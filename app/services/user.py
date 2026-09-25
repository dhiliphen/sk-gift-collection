from fastapi import HTTPException
from app import models, schemas
from app.repositories.user import UserRepository
from app.security import hash_password


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def get_all(self) -> list[models.User]:
        return self.repo.get_all_ordered()

    def get_by_id(self, user_id: int) -> models.User:
        user = self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    def create(self, data: schemas.UserCreate) -> models.User:
        if self.repo.get_by_username(data.username):
            raise HTTPException(status_code=400, detail="A user with this username already exists")
        user = models.User(
            username=data.username,
            password_hash=hash_password(data.password),
            role=data.role,
        )
        self.repo.save(user)
        self.repo.commit()
        return self.repo.refresh(user)

    def update(self, user_id: int, data: schemas.UserUpdate) -> models.User:
        user = self.get_by_id(user_id)
        updates = data.model_dump(exclude_unset=True)
        password = updates.pop("password", None)
        for field, value in updates.items():
            setattr(user, field, value)
        if password:
            user.password_hash = hash_password(password)
        self.repo.commit()
        return self.repo.refresh(user)
