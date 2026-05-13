from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from parental_controls.database import get_session
from parental_controls.models.chore import Chore
from parental_controls.models.chore_completion import DailyChoreCompletion
from parental_controls.services.chore_service import upsert_completion

router = APIRouter(prefix="/api/v1/chores", tags=["completions"])


class CompletionRead(BaseModel):
    id: int
    chore_id: int
    chore_date: date
    completed: bool
    completed_at: Optional[datetime]


@router.post("/{chore_id}/complete", response_model=CompletionRead, status_code=201)
def mark_complete(
    chore_id: int,
    chore_date: Optional[date] = Query(default=None),
    session: Session = Depends(get_session),
):
    chore = session.get(Chore, chore_id)
    if not chore:
        raise HTTPException(status_code=404, detail="Chore not found")
    today = chore_date or date.today()
    completion = upsert_completion(session, chore_id, today, True)
    return CompletionRead(
        id=completion.id,
        chore_id=completion.chore_id,
        chore_date=completion.date,
        completed=completion.completed,
        completed_at=completion.completed_at,
    )


@router.delete("/{chore_id}/complete", status_code=204)
def mark_incomplete(
    chore_id: int,
    chore_date: Optional[date] = Query(default=None),
    session: Session = Depends(get_session),
):
    today = chore_date or date.today()
    existing = session.exec(
        select(DailyChoreCompletion).where(
            DailyChoreCompletion.chore_id == chore_id,
            DailyChoreCompletion.date == today,
        )
    ).first()
    if existing:
        upsert_completion(session, chore_id, today, False)
