import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.auth import verify_credentials, create_session, delete_session

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
):
    if verify_credentials(username, password):
        token = create_session()
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie("session", token, httponly=True, samesite="lax")
        return response
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid username or password"},
        status_code=401,
    )


@router.post("/logout")
def logout(request: Request):
    token = request.cookies.get("session")
    if token:
        delete_session(token)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response
