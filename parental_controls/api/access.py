from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from parental_controls.database import get_session
from parental_controls.services.access_control import get_all_access

router = APIRouter(prefix="/api/v1", tags=["access"])


class ChildAccessItem(BaseModel):
    child_id: int
    child_name: str
    allowed: bool
    reason: str


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
            )
            for c in result.children
        ],
    )
