from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from parental_controls.database import get_session
from parental_controls.models.child import Child
from parental_controls.models.chore import Chore
from parental_controls.models.chore_completion import DailyChoreCompletion
from parental_controls.services.pin_service import hash_pin

router = APIRouter(prefix="/api/v1/children", tags=["children"])


class ChildCreate(BaseModel):
    name: str
    display_color: str = "#4A90D9"
    icon: str = "🧒"
    pin: str


class ChildUpdate(BaseModel):
    name: Optional[str] = None
    display_color: Optional[str] = None
    icon: Optional[str] = None
    pin: Optional[str] = None


class ChildRead(BaseModel):
    id: int
    name: str
    display_color: str
    icon: str


class ChoreStatusItem(BaseModel):
    chore_id: int
    chore_name: str
    chore_icon: str
    completed: bool


class ChildStatus(BaseModel):
    child_id: int
    child_name: str
    total_chores: int
    completed_chores: int
    chores: list[ChoreStatusItem]


@router.get("", response_model=list[ChildRead])
def list_children(session: Session = Depends(get_session)):
    return session.exec(select(Child)).all()


@router.post("", response_model=ChildRead, status_code=201)
def create_child(body: ChildCreate, session: Session = Depends(get_session)):
    child = Child(
        name=body.name,
        display_color=body.display_color,
        icon=body.icon,
        pin_hash=hash_pin(body.pin),
    )
    session.add(child)
    session.commit()
    session.refresh(child)
    return child


@router.get("/{child_id}", response_model=ChildRead)
def get_child(child_id: int, session: Session = Depends(get_session)):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    return child


@router.put("/{child_id}", response_model=ChildRead)
def update_child(child_id: int, body: ChildUpdate, session: Session = Depends(get_session)):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    if body.name is not None:
        child.name = body.name
    if body.display_color is not None:
        child.display_color = body.display_color
    if body.icon is not None:
        child.icon = body.icon
    if body.pin is not None:
        child.pin_hash = hash_pin(body.pin)
    session.add(child)
    session.commit()
    session.refresh(child)
    return child


@router.delete("/{child_id}", status_code=204)
def delete_child(child_id: int, session: Session = Depends(get_session)):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    session.delete(child)
    session.commit()


@router.get("/{child_id}/status", response_model=ChildStatus)
def get_child_status(
    child_id: int,
    query_date: Optional[date] = None,
    session: Session = Depends(get_session),
):
    child = session.get(Child, child_id)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    today = query_date or date.today()
    chores = session.exec(select(Chore).where(Chore.child_id == child_id)).all()
    if not chores:
        return ChildStatus(child_id=child_id, child_name=child.name, total_chores=0, completed_chores=0, chores=[])

    completions = {
        c.chore_id: c
        for c in session.exec(
            select(DailyChoreCompletion).where(
                DailyChoreCompletion.chore_id.in_([c.id for c in chores]),
                DailyChoreCompletion.date == today,
            )
        ).all()
    }
    items = [
        ChoreStatusItem(
            chore_id=c.id,
            chore_name=c.name,
            chore_icon=c.icon,
            completed=completions.get(c.id, None) is not None and completions[c.id].completed,
        )
        for c in sorted(chores, key=lambda x: x.sort_order)
    ]
    completed_count = sum(1 for i in items if i.completed)
    return ChildStatus(
        child_id=child_id,
        child_name=child.name,
        total_chores=len(chores),
        completed_chores=completed_count,
        chores=items,
    )
