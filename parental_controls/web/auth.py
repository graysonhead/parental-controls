from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from parental_controls.config import settings
from parental_controls.database import get_session
from parental_controls.models.child import Child
from parental_controls.services.pin_service import verify_pin

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="parental_controls/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_session)):
    children = session.exec(select(Child)).all()
    return templates.TemplateResponse(request, "home.html", {"children": children})


@router.get("/pin/parent", response_class=HTMLResponse)
def pin_parent_get(request: Request):
    return templates.TemplateResponse(
        request, "pin_entry.html",
        {"target_name": "Parent", "target_icon": "🔒", "post_url": "/pin/parent", "error": False},
    )


@router.post("/pin/parent", response_class=HTMLResponse)
def pin_parent_post(request: Request, pin: str = Form(...)):
    if verify_pin(pin, settings.admin_pin_hash):
        request.session["is_parent"] = True
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request, "pin_entry.html",
        {"target_name": "Parent", "target_icon": "🔒", "post_url": "/pin/parent", "error": True},
    )


@router.get("/pin/{child_id}", response_class=HTMLResponse)
def pin_child_get(child_id: int, request: Request, session: Session = Depends(get_session)):
    child = session.get(Child, child_id)
    if not child:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request, "pin_entry.html",
        {
            "target_name": child.name,
            "target_icon": child.icon,
            "target_color": child.display_color,
            "post_url": f"/pin/{child_id}",
            "error": False,
        },
    )


@router.post("/pin/{child_id}", response_class=HTMLResponse)
def pin_child_post(child_id: int, request: Request, pin: str = Form(...), session: Session = Depends(get_session)):
    child = session.get(Child, child_id)
    if not child:
        return RedirectResponse("/", status_code=303)
    if verify_pin(pin, child.pin_hash):
        request.session["child_id"] = child_id
        return RedirectResponse(f"/child/{child_id}", status_code=303)
    return templates.TemplateResponse(
        request, "pin_entry.html",
        {
            "target_name": child.name,
            "target_icon": child.icon,
            "target_color": child.display_color,
            "post_url": f"/pin/{child_id}",
            "error": True,
        },
    )


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
