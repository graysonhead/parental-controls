from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from parental_controls.models.child import Child


class OverrideType(str, Enum):
    GRANT = "grant"
    REVOKE = "revoke"


class AccessOverride(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: int = Field(foreign_key="child.id", index=True)
    override_type: OverrideType
    reason: Optional[str] = Field(default=None, max_length=300)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.now)

    child: "Child" = Relationship(back_populates="overrides")
