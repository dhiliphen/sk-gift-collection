from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.repositories.bill import BillRepository
from app.repositories.purchase import PurchaseRepository
from app.repositories.item import ItemRepository
from app.repositories.payment import PaymentRepository
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/api", tags=["dashboard"])


def get_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(
        BillRepository(db), PurchaseRepository(db), ItemRepository(db), PaymentRepository(db)
    )


@router.get("/dashboard", response_model=schemas.DashboardResponse)
def get_dashboard(service: DashboardService = Depends(get_service)):
    return service.get_dashboard()
