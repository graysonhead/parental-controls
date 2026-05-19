from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from parental_controls.models.child import Child
    from parental_controls.models.chore_completion import DailyChoreCompletion


class Chore(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: int = Field(foreign_key="child.id", index=True)
    name: str = Field(max_length=200)
    icon: str = Field(default="✅", max_length=10)
    sort_order: int = Field(default=0)

    child: "Child" = Relationship(back_populates="chores")
    completions: List["DailyChoreCompletion"] = Relationship(back_populates="chore", cascade_delete=True)
