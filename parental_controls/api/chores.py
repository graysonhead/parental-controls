from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from parental_controls.database import get_session
from parental_controls.models.chore import Chore

router = APIRouter(prefix="/api/v1/children", tags=["chores"])


class ChoreCreate(BaseModel):
    name: str
    icon: str = "✅"
    sort_order: int = 0


class ChoreUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None


class ChoreRead(BaseModel):
    id: int
    child_id: int
    name: str
    icon: str
    sort_order: int


@router.get("/{child_id}/chores", response_model=list[ChoreRead])
def list_chores(child_id: int, session: Session = Depends(get_session)):
    return session.exec(
        select(Chore).where(Chore.child_id == child_id).order_by(Chore.sort_order)
    ).all()


@router.post("/{child_id}/chores", response_model=ChoreRead, status_code=201)
def create_chore(child_id: int, body: ChoreCreate, session: Session = Depends(get_session)):
    chore = Chore(child_id=child_id, name=body.name, icon=body.icon, sort_order=body.sort_order)
    session.add(chore)
    session.commit()
    session.refresh(chore)
    return chore


@router.put("/chores/{chore_id}", response_model=ChoreRead)
def update_chore(chore_id: int, body: ChoreUpdate, session: Session = Depends(get_session)):
    chore = session.get(Chore, chore_id)
    if not chore:
        raise HTTPException(status_code=404, detail="Chore not found")
    if body.name is not None:
        chore.name = body.name
    if body.icon is not None:
        chore.icon = body.icon
    if body.sort_order is not None:
        chore.sort_order = body.sort_order
    session.add(chore)
    session.commit()
    session.refresh(chore)
    return chore


@router.delete("/chores/{chore_id}", status_code=204)
def delete_chore(chore_id: int, session: Session = Depends(get_session)):
    chore = session.get(Chore, chore_id)
    if not chore:
        raise HTTPException(status_code=404, detail="Chore not found")
    session.delete(chore)
    session.commit()
