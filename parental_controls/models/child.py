from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from parental_controls.models.chore import Chore
    from parental_controls.models.time_window import TimeWindow


class Child(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=100)
    display_color: str = Field(default="#4A90D9", max_length=7)
    icon: str = Field(default="🧒", max_length=10)
    pin_hash: str = Field(max_length=200)

    time_windows: List["TimeWindow"] = Relationship(back_populates="child")
    chores: List["Chore"] = Relationship(back_populates="child")
