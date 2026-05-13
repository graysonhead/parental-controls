import json
from datetime import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from parental_controls.database import get_session
from parental_controls.models.time_window import TimeWindow

router = APIRouter(prefix="/api/v1/children", tags=["time-windows"])


class TimeWindowCreate(BaseModel):
    days_of_week: list[int]
    start_time: time
    end_time: time
    label: Optional[str] = None


class TimeWindowUpdate(BaseModel):
    days_of_week: Optional[list[int]] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    label: Optional[str] = None


class TimeWindowRead(BaseModel):
    id: int
    child_id: int
    days_of_week: list[int]
    start_time: time
    end_time: time
    label: Optional[str]


def _to_read(w: TimeWindow) -> TimeWindowRead:
    return TimeWindowRead(
        id=w.id,
        child_id=w.child_id,
        days_of_week=json.loads(w.days_of_week),
        start_time=w.start_time,
        end_time=w.end_time,
        label=w.label,
    )


@router.get("/{child_id}/time-windows", response_model=list[TimeWindowRead])
def list_time_windows(child_id: int, session: Session = Depends(get_session)):
    windows = session.exec(select(TimeWindow).where(TimeWindow.child_id == child_id)).all()
    return [_to_read(w) for w in windows]


@router.post("/{child_id}/time-windows", response_model=TimeWindowRead, status_code=201)
def create_time_window(child_id: int, body: TimeWindowCreate, session: Session = Depends(get_session)):
    w = TimeWindow(
        child_id=child_id,
        days_of_week=json.dumps(body.days_of_week),
        start_time=body.start_time,
        end_time=body.end_time,
        label=body.label,
    )
    session.add(w)
    session.commit()
    session.refresh(w)
    return _to_read(w)


@router.put("/time-windows/{window_id}", response_model=TimeWindowRead)
def update_time_window(window_id: int, body: TimeWindowUpdate, session: Session = Depends(get_session)):
    w = session.get(TimeWindow, window_id)
    if not w:
        raise HTTPException(status_code=404, detail="Time window not found")
    if body.days_of_week is not None:
        w.days_of_week = json.dumps(body.days_of_week)
    if body.start_time is not None:
        w.start_time = body.start_time
    if body.end_time is not None:
        w.end_time = body.end_time
    if body.label is not None:
        w.label = body.label
    session.add(w)
    session.commit()
    session.refresh(w)
    return _to_read(w)


@router.delete("/time-windows/{window_id}", status_code=204)
def delete_time_window(window_id: int, session: Session = Depends(get_session)):
    w = session.get(TimeWindow, window_id)
    if not w:
        raise HTTPException(status_code=404, detail="Time window not found")
    session.delete(w)
    session.commit()
