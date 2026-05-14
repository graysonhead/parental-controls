from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from parental_controls.database import get_session
from parental_controls.models.child import Child
from parental_controls.models.chore import Chore
from parental_controls.models.chore_completion import DailyChoreCompletion
from parental_controls.services.chore_service import all_chores_complete, upsert_completion

router = APIRouter(tags=["child-ui"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _require_child_session(request: Request, child_id: int) -> bool:
    return request.session.get("child_id") == child_id


@router.get("/child/{child_id}", response_class=HTMLResponse)
def chore_list(child_id: int, request: Request, session: Session = Depends(get_session)):
    if not _require_child_session(request, child_id):
        return RedirectResponse("/", status_code=303)
    child = session.get(Child, child_id)
    if not child:
        return RedirectResponse("/", status_code=303)

    today = date.today()
    chores = session.exec(
        select(Chore).where(Chore.child_id == child_id).order_by(Chore.sort_order)
    ).all()
    completions = {
        c.chore_id: c
        for c in session.exec(
            select(DailyChoreCompletion).where(
                DailyChoreCompletion.chore_id.in_([c.id for c in chores]),
                DailyChoreCompletion.date == today,
            )
        ).all()
    }
    chore_items = [
        {"chore": c, "completed": completions.get(c.id) is not None and completions[c.id].completed}
        for c in chores
    ]
    completed_count = sum(1 for item in chore_items if item["completed"])
    return templates.TemplateResponse(
        request, "child/chore_list.html",
        {
            "child": child,
            "chore_items": chore_items,
            "completed_count": completed_count,
            "total_count": len(chores),
        },
    )


@router.get("/child/{child_id}/done", response_class=HTMLResponse)
def all_done(child_id: int, request: Request, session: Session = Depends(get_session)):
    if not _require_child_session(request, child_id):
        return RedirectResponse("/", status_code=303)
    child = session.get(Child, child_id)
    if not child:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "child/all_done.html", {"child": child})


@router.post("/web/chores/{chore_id}/complete", response_class=HTMLResponse)
def toggle_chore(chore_id: int, request: Request, session: Session = Depends(get_session)):
    chore = session.get(Chore, chore_id)
    if not chore:
        return HTMLResponse("", status_code=404)
    if not _require_child_session(request, chore.child_id):
        return HTMLResponse("", status_code=403)

    today = date.today()
    existing = session.exec(
        select(DailyChoreCompletion).where(
            DailyChoreCompletion.chore_id == chore_id,
            DailyChoreCompletion.date == today,
        )
    ).first()
    # Toggle: if currently complete, mark incomplete; otherwise mark complete
    new_state = not (existing and existing.completed)
    upsert_completion(session, chore_id, today, new_state)

    child_id = chore.child_id
    if new_state and all_chores_complete(session, child_id, today):
        return HTMLResponse(
            "",
            status_code=200,
            headers={"HX-Redirect": f"/child/{child_id}/done"},
        )

    # Count progress for the OOB footer update
    all_chores = session.exec(select(Chore).where(Chore.child_id == child_id)).all()
    completed_ids = {
        c.chore_id
        for c in session.exec(
            select(DailyChoreCompletion).where(
                DailyChoreCompletion.chore_id.in_([c.id for c in all_chores]),
                DailyChoreCompletion.date == today,
                DailyChoreCompletion.completed == True,
            )
        ).all()
    }
    completed_count = sum(1 for c in all_chores if c.id in completed_ids)

    card_html = templates.get_template("child/_chore_card.html").render(
        {"request": request, "chore": chore, "completed": new_state}
    )
    footer_html = templates.get_template("child/_chore_footer.html").render(
        {"request": request, "completed_count": completed_count, "total_count": len(all_chores)}
    )
    return HTMLResponse(card_html + footer_html)
