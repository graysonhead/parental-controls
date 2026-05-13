import json
from datetime import time
from enum import IntEnum
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from parental_controls.models.child import Child


class DayOfWeek(IntEnum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class TimeWindow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: int = Field(foreign_key="child.id", index=True)
    # JSON-encoded list of DayOfWeek ints, e.g. "[0,1,2,3,4]"
    days_of_week: str = Field(default="[0,1,2,3,4,5,6]")
    start_time: time
    end_time: time
    label: Optional[str] = Field(default=None, max_length=100)

    child: "Child" = Relationship(back_populates="time_windows")

    @property
    def days(self) -> List[DayOfWeek]:
        return [DayOfWeek(d) for d in json.loads(self.days_of_week)]

    def is_active_at(self, dt_time: time, weekday: int) -> bool:
        return weekday in [d.value for d in self.days] and self.start_time <= dt_time < self.end_time
