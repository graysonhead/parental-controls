from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from parental_controls.database import get_session
from parental_controls.models.access_override import OverrideType
from parental_controls.services.access_control import get_all_access

router = APIRouter(prefix="/api/v1", tags=["access"])


class ActiveOverrideInfo(BaseModel):
    id: int
    override_type: OverrideType
    reason: Optional[str]
    expires_at: datetime


class ChildAccessItem(BaseModel):
    child_id: int
    child_name: str
    allowed: bool
    reason: str
    active_override: Optional[ActiveOverrideInfo] = None


class AccessResponse(BaseModel):
    checked_at: datetime
    children: list[ChildAccessItem]


@router.get("/access", response_model=AccessResponse)
def check_access(session: Session = Depends(get_session)):
    result = get_all_access(session, datetime.now())
    return AccessResponse(
        checked_at=result.checked_at,
        children=[
            ChildAccessItem(
                child_id=c.child_id,
                child_name=c.child_name,
                allowed=c.allowed,
                reason=c.reason,
                active_override=ActiveOverrideInfo(
                    id=c.active_override.id,
                    override_type=c.active_override.override_type,
                    reason=c.active_override.reason,
                    expires_at=c.active_override.expires_at,
                ) if c.active_override else None,
            )
            for c in result.children
        ],
    )
