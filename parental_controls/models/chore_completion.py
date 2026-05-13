from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from parental_controls.models.chore import Chore


class DailyChoreCompletion(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("chore_id", "date"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    chore_id: int = Field(foreign_key="chore.id", index=True)
    date: date
    completed: bool = Field(default=False)
    completed_at: Optional[datetime] = Field(default=None)

    chore: "Chore" = Relationship(back_populates="completions")
