from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, SQLModel, select

from parental_controls.database import get_session
from parental_controls.models.access_override import AccessOverride, OverrideType
from parental_controls.models.child import Child
from parental_controls.services.override_service import cancel_override, create_override, get_active_override

router = APIRouter(prefix="/api/v1", tags=["overrides"])

VALID_DURATIONS = {"1h", "today", "tomorrow", "weekend"}


class CreateOverrideRequest(SQLModel):
    override_type: OverrideType
    duration: str
    reason: Optional[str] = None


class OverrideResponse(SQLModel):
    id: int
    child_id: int
    override_type: OverrideType
    reason: Optional[str]
    expires_at: datetime
    created_at: datetime


@router.post("/children/{child_id}/overrides", response_model=OverrideResponse, status_code=201)
def create_child_override(
    child_id: int,
    body: CreateOverrideRequest,
    session: Session = Depends(get_session),
):
    if not session.get(Child, child_id):
        raise HTTPException(status_code=404, detail="Child not found")
    if body.duration not in VALID_DURATIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid duration {body.duration!r}. Valid values: {sorted(VALID_DURATIONS)}",
        )
    override = create_override(
        session=session,
        child_id=child_id,
        override_type=body.override_type,
        duration=body.duration,
        reason=body.reason,
        now=datetime.now(),
    )
    return override


@router.get("/children/{child_id}/overrides", response_model=List[OverrideResponse])
def list_child_overrides(
    child_id: int,
    session: Session = Depends(get_session),
):
    if not session.get(Child, child_id):
        raise HTTPException(status_code=404, detail="Child not found")
    now = datetime.now()
    overrides = session.exec(
        select(AccessOverride)
        .where(AccessOverride.child_id == child_id)
        .where(AccessOverride.expires_at > now)
        .order_by(AccessOverride.created_at.desc())
    ).all()
    return overrides


@router.get("/overrides", response_model=List[OverrideResponse])
def list_all_overrides(session: Session = Depends(get_session)):
    now = datetime.now()
    overrides = session.exec(
        select(AccessOverride)
        .where(AccessOverride.expires_at > now)
        .order_by(AccessOverride.created_at.desc())
    ).all()
    return overrides


@router.delete("/overrides/{override_id}", status_code=204)
def delete_override(
    override_id: int,
    session: Session = Depends(get_session),
):
    if not cancel_override(session, override_id):
        raise HTTPException(status_code=404, detail="Override not found")
