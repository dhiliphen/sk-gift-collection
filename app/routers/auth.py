import os
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.auth import verify_credentials, create_session, delete_session, _sessions
from app.audit import record

router = APIRouter()

_base = os.environ.get(
    'BASE_DIR',
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
templates = Jinja2Templates(directory=os.path.join(_base, "app", "templates"))


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = verify_credentials(db, username, password)
    if user:
        token = create_session(user.id)
        record(db, user.username, "LOGIN_SUCCESS", "user", user.id)
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie("session", token, httponly=True, samesite="lax")
        return response
    record(db, username, "LOGIN_FAILURE", "user", None, new_value={"attempted_username": username})
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid username or password"},
        status_code=401,
    )


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session")
    if token:
        user_id = _sessions.get(token)
        if user_id:
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if user:
                record(db, user.username, "LOGOUT", "user", user.id)
        delete_session(token)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response
