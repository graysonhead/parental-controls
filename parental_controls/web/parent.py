import json
from datetime import date, datetime, time
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from parental_controls.database import get_session
from parental_controls.models.access_override import AccessOverride, OverrideType
from parental_controls.models.child import Child
from parental_controls.models.chore import Chore
from parental_controls.models.time_window import TimeWindow
from parental_controls.services.chore_service import all_chores_complete
from parental_controls.services.override_service import cancel_override, create_override, get_active_override, get_active_overrides
from parental_controls.services.pin_service import get_admin_pin_hash, hash_pin, set_admin_pin_hash, verify_pin

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _require_parent(request: Request):
    return bool(request.session.get("is_parent"))


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    children = session.exec(select(Child)).all()
    today = date.today()
    now = datetime.now()
    child_data = [
        {
            "child": child,
            "chores_done": all_chores_complete(session, child.id, today),
            "chore_count": len(session.exec(select(Chore).where(Chore.child_id == child.id)).all()),
            "active_overrides": get_active_overrides(session, child.id, now),
        }
        for child in children
    ]
    return templates.TemplateResponse(request, "parent/dashboard.html", {"child_data": child_data})


@router.get("/children/new", response_class=HTMLResponse)
def new_child_form(request: Request):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    return templates.TemplateResponse(request, "parent/child_form.html", {"child": None})


@router.post("/children/new")
def create_child(
    request: Request,
    name: str = Form(...),
    display_color: str = Form("#4A90D9"),
    icon: str = Form("🧒"),
    pin: str = Form(...),
    session: Session = Depends(get_session),
):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    child = Child(name=name, display_color=display_color, icon=icon, pin_hash=hash_pin(pin))
    session.add(child)
    session.commit()
    return RedirectResponse("/admin", status_code=303)


@router.get("/children/{child_id}/edit", response_class=HTMLResponse)
def edit_child_form(child_id: int, request: Request, session: Session = Depends(get_session)):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    child = session.get(Child, child_id)
    if not child:
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request, "parent/child_form.html", {"child": child})


@router.post("/children/{child_id}/edit")
def update_child(
    child_id: int,
    request: Request,
    name: str = Form(...),
    display_color: str = Form("#4A90D9"),
    icon: str = Form("🧒"),
    pin: str = Form(default=""),
    session: Session = Depends(get_session),
):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    child = session.get(Child, child_id)
    if not child:
        return RedirectResponse("/admin", status_code=303)
    child.name = name
    child.display_color = display_color
    child.icon = icon
    if pin:
        child.pin_hash = hash_pin(pin)
    session.add(child)
    session.commit()
    return RedirectResponse("/admin", status_code=303)


@router.post("/children/{child_id}/delete")
def delete_child(child_id: int, request: Request, session: Session = Depends(get_session)):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    child = session.get(Child, child_id)
    if child:
        session.delete(child)
        session.commit()
    return RedirectResponse("/admin", status_code=303)


@router.get("/children/{child_id}/chores", response_class=HTMLResponse)
def chores_page(child_id: int, request: Request, session: Session = Depends(get_session)):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    child = session.get(Child, child_id)
    if not child:
        return RedirectResponse("/admin", status_code=303)
    chores = session.exec(select(Chore).where(Chore.child_id == child_id).order_by(Chore.sort_order)).all()
    return templates.TemplateResponse(request, "parent/chore_form.html", {"child": child, "chores": chores})


@router.post("/children/{child_id}/chores/add")
def add_chore(
    child_id: int,
    request: Request,
    name: str = Form(...),
    icon: str = Form("✅"),
    sort_order: int = Form(0),
    session: Session = Depends(get_session),
):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    session.add(Chore(child_id=child_id, name=name, icon=icon, sort_order=sort_order))
    session.commit()
    return RedirectResponse(f"/admin/children/{child_id}/chores", status_code=303)


@router.post("/chores/{chore_id}/delete")
def delete_chore(chore_id: int, request: Request, session: Session = Depends(get_session)):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    chore = session.get(Chore, chore_id)
    if chore:
        child_id = chore.child_id
        session.delete(chore)
        session.commit()
        return RedirectResponse(f"/admin/children/{child_id}/chores", status_code=303)
    return RedirectResponse("/admin", status_code=303)


@router.get("/children/{child_id}/time-windows", response_class=HTMLResponse)
def time_windows_page(child_id: int, request: Request, session: Session = Depends(get_session)):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    child = session.get(Child, child_id)
    if not child:
        return RedirectResponse("/admin", status_code=303)
    windows = session.exec(select(TimeWindow).where(TimeWindow.child_id == child_id)).all()
    return templates.TemplateResponse(
        request, "parent/time_window_form.html",
        {"child": child, "windows": windows, "json": json},
    )


@router.post("/children/{child_id}/time-windows/add")
def add_time_window(
    child_id: int,
    request: Request,
    days_of_week: List[int] = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    label: str = Form(default=""),
    session: Session = Depends(get_session),
):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    w = TimeWindow(
        child_id=child_id,
        days_of_week=json.dumps(days_of_week),
        start_time=time.fromisoformat(start_time),
        end_time=time.fromisoformat(end_time),
        label=label or None,
    )
    session.add(w)
    session.commit()
    return RedirectResponse(f"/admin/children/{child_id}/time-windows", status_code=303)


@router.post("/time-windows/{window_id}/delete")
def delete_time_window(window_id: int, request: Request, session: Session = Depends(get_session)):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    w = session.get(TimeWindow, window_id)
    if w:
        child_id = w.child_id
        session.delete(w)
        session.commit()
        return RedirectResponse(f"/admin/children/{child_id}/time-windows", status_code=303)
    return RedirectResponse("/admin", status_code=303)


@router.get("/children/{child_id}/overrides", response_class=HTMLResponse)
def overrides_page(child_id: int, request: Request, session: Session = Depends(get_session)):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    child = session.get(Child, child_id)
    if not child:
        return RedirectResponse("/admin", status_code=303)
    overrides = get_active_overrides(session, child_id, datetime.now())
    return templates.TemplateResponse(
        request, "parent/override_list.html", {"child": child, "overrides": overrides}
    )


@router.post("/children/{child_id}/overrides/full")
def web_create_override_full(
    child_id: int,
    request: Request,
    override_type: str = Form(...),
    duration: str = Form(...),
    reason: str = Form(default=""),
    session: Session = Depends(get_session),
):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    create_override(
        session=session,
        child_id=child_id,
        override_type=OverrideType(override_type),
        duration=duration,
        reason=reason or None,
        now=datetime.now(),
    )
    return RedirectResponse(f"/admin/children/{child_id}/overrides", status_code=303)


@router.post("/children/{child_id}/overrides", response_class=HTMLResponse)
def web_create_override(
    child_id: int,
    request: Request,
    override_type: str = Form(...),
    duration: str = Form(...),
    reason: str = Form(default=""),
    session: Session = Depends(get_session),
):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    create_override(
        session=session,
        child_id=child_id,
        override_type=OverrideType(override_type),
        duration=duration,
        reason=reason or None,
        now=datetime.now(),
    )
    now = datetime.now()
    return templates.TemplateResponse(
        request,
        "parent/_override_status.html",
        {"child_id": child_id, "active_overrides": get_active_overrides(session, child_id, now)},
    )


@router.post("/overrides/{override_id}/cancel", response_class=HTMLResponse)
def web_cancel_override(
    override_id: int,
    request: Request,
    session: Session = Depends(get_session),
):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    override = session.get(AccessOverride, override_id)
    child_id = override.child_id if override else None
    cancel_override(session, override_id)
    if request.headers.get("HX-Request"):
        now = datetime.now()
        active_overrides = get_active_overrides(session, child_id, now) if child_id else []
        return templates.TemplateResponse(
            request,
            "parent/_override_status.html",
            {"child_id": child_id, "active_overrides": active_overrides},
        )
    return RedirectResponse(f"/admin/children/{child_id}/overrides", status_code=303)


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)
    return templates.TemplateResponse(request, "parent/settings.html", {"error": None, "success": False})


@router.post("/settings/pin")
def change_pin(
    request: Request,
    current_pin: str = Form(...),
    new_pin: str = Form(...),
    confirm_pin: str = Form(...),
    session: Session = Depends(get_session),
):
    if not _require_parent(request):
        return RedirectResponse("/pin/parent", status_code=303)

    def render(error: str):
        return templates.TemplateResponse(
            request, "parent/settings.html", {"error": error, "success": False}
        )

    if not verify_pin(current_pin, get_admin_pin_hash(session)):
        return render("Current PIN is incorrect.")
    if new_pin != confirm_pin:
        return render("New PINs do not match.")
    if not new_pin.isdigit():
        return render("PIN must contain digits only.")
    if len(new_pin) < 4:
        return render("PIN must be at least 4 digits.")

    set_admin_pin_hash(session, hash_pin(new_pin))
    return templates.TemplateResponse(request, "parent/settings.html", {"error": None, "success": True})
