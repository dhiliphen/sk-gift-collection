from sqlalchemy.orm import Session


class BaseRepository:
    """Generic CRUD operations shared by all domain repositories."""

    def __init__(self, model, db: Session):
        self.model = model
        self.db = db

    def get_by_id(self, obj_id: int):
        return self.db.query(self.model).filter(self.model.id == obj_id).first()

    def get_all(self):
        return self.db.query(self.model).all()

    def save(self, obj):
        """Add and flush (no commit — let the service control the transaction)."""
        self.db.add(obj)
        self.db.flush()
        return obj

    def delete(self, obj):
        self.db.delete(obj)

    def commit(self):
        self.db.commit()

    def refresh(self, obj):
        self.db.refresh(obj)
        return obj
