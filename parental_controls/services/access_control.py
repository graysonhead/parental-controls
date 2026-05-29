from datetime import datetime
from typing import List

from sqlmodel import Session, select

from parental_controls.models.access_override import OverrideType
from parental_controls.models.child import Child
from parental_controls.models.chore import Chore
from parental_controls.models.chore_completion import DailyChoreCompletion
from parental_controls.models.time_window import TimeWindow
from parental_controls.services.override_service import get_active_override


class ChildAccessResult:
    def __init__(self, child_id: int, child_name: str, allowed: bool, reason: str, active_override=None):
        self.child_id = child_id
        self.child_name = child_name
        self.allowed = allowed
        self.reason = reason
        self.active_override = active_override


class AccessResult:
    def __init__(self, checked_at: datetime, children: List[ChildAccessResult]):
        self.checked_at = checked_at
        self.children = children


def check_child_access(session: Session, child: Child, now: datetime) -> ChildAccessResult:
    active_override = get_active_override(session, child.id, now)
    if active_override:
        if active_override.override_type == OverrideType.REVOKE:
            return ChildAccessResult(child.id, child.name, False, "access_revoked", active_override)
        return ChildAccessResult(child.id, child.name, True, "access_granted", active_override)

    windows = session.exec(
        select(TimeWindow).where(TimeWindow.child_id == child.id)
    ).all()
    current_time = now.time().replace(second=0, microsecond=0)
    if not any(w.is_active_at(current_time, now.weekday()) for w in windows):
        return ChildAccessResult(child.id, child.name, False, "outside_time_window")

    chores = session.exec(select(Chore).where(Chore.child_id == child.id)).all()
    if chores:
        today = now.date()
        completed_ids = set(
            session.exec(
                select(DailyChoreCompletion.chore_id).where(
                    DailyChoreCompletion.chore_id.in_([c.id for c in chores]),
                    DailyChoreCompletion.date == today,
                    DailyChoreCompletion.completed == True,
                )
            ).all()
        )
        if any(c.id not in completed_ids for c in chores):
            return ChildAccessResult(child.id, child.name, False, "chores_incomplete")

    return ChildAccessResult(child.id, child.name, True, "allowed")


def get_all_access(session: Session, now: datetime) -> AccessResult:
    children = session.exec(select(Child)).all()
    return AccessResult(
        checked_at=now,
        children=[check_child_access(session, child, now) for child in children],
    )
