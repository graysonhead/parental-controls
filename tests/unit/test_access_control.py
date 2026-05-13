import json
from datetime import datetime, time

import pytest
from sqlmodel import Session

from parental_controls.models.child import Child
from parental_controls.models.chore import Chore
from parental_controls.models.chore_completion import DailyChoreCompletion
from parental_controls.models.time_window import TimeWindow
from parental_controls.services.access_control import check_child_access, get_all_access


WEEKDAY_WINDOW = json.dumps([0, 1, 2, 3, 4])
ALL_DAYS_WINDOW = json.dumps([0, 1, 2, 3, 4, 5, 6])

NOW = datetime(2026, 5, 11, 10, 0, 0)  # Monday 10am
TODAY = NOW.date()


def make_child(session: Session, name: str = "Alice") -> Child:
    child = Child(name=name, pin_hash="x")
    session.add(child)
    session.commit()
    session.refresh(child)
    return child


def add_window(session: Session, child: Child, days: str, start: time, end: time) -> TimeWindow:
    w = TimeWindow(child_id=child.id, days_of_week=days, start_time=start, end_time=end)
    session.add(w)
    session.commit()
    return w


def add_chore(session: Session, child: Child, name: str = "Chore") -> Chore:
    c = Chore(child_id=child.id, name=name, icon="✅")
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def complete_chore(session: Session, chore: Chore) -> None:
    session.add(DailyChoreCompletion(chore_id=chore.id, date=TODAY, completed=True))
    session.commit()


class TestCheckChildAccess:
    def test_allowed_when_in_window_and_all_chores_complete(self, session: Session):
        child = make_child(session)
        add_window(session, child, WEEKDAY_WINDOW, time(8, 0), time(18, 0))
        complete_chore(session, add_chore(session, child))

        result = check_child_access(session, child, NOW)

        assert result.allowed is True
        assert result.reason == "allowed"

    def test_denied_outside_time_window(self, session: Session):
        child = make_child(session)
        add_window(session, child, WEEKDAY_WINDOW, time(8, 0), time(9, 0))

        result = check_child_access(session, child, NOW)  # NOW is 10am

        assert result.allowed is False
        assert result.reason == "outside_time_window"

    def test_denied_on_weekend_when_weekday_only_window(self, session: Session):
        child = make_child(session)
        add_window(session, child, WEEKDAY_WINDOW, time(8, 0), time(18, 0))

        result = check_child_access(session, child, datetime(2026, 5, 9, 10, 0, 0))  # Saturday

        assert result.allowed is False
        assert result.reason == "outside_time_window"

    def test_denied_when_chores_incomplete(self, session: Session):
        child = make_child(session)
        add_window(session, child, WEEKDAY_WINDOW, time(8, 0), time(18, 0))
        add_chore(session, child)

        result = check_child_access(session, child, NOW)

        assert result.allowed is False
        assert result.reason == "chores_incomplete"

    def test_denied_when_only_some_chores_complete(self, session: Session):
        child = make_child(session)
        add_window(session, child, WEEKDAY_WINDOW, time(8, 0), time(18, 0))
        complete_chore(session, add_chore(session, child, "Chore 1"))
        add_chore(session, child, "Chore 2")

        result = check_child_access(session, child, NOW)

        assert result.allowed is False
        assert result.reason == "chores_incomplete"

    def test_allowed_when_no_chores_assigned(self, session: Session):
        child = make_child(session)
        add_window(session, child, WEEKDAY_WINDOW, time(8, 0), time(18, 0))

        result = check_child_access(session, child, NOW)

        assert result.allowed is True

    def test_denied_when_no_time_windows(self, session: Session):
        child = make_child(session)

        result = check_child_access(session, child, NOW)

        assert result.allowed is False
        assert result.reason == "outside_time_window"

    def test_allowed_at_exact_start_time_boundary(self, session: Session):
        child = make_child(session)
        add_window(session, child, ALL_DAYS_WINDOW, time(10, 0), time(18, 0))

        result = check_child_access(session, child, datetime(2026, 5, 11, 10, 0, 0))

        assert result.allowed is True

    def test_denied_at_exact_end_time_boundary(self, session: Session):
        child = make_child(session)
        add_window(session, child, ALL_DAYS_WINDOW, time(8, 0), time(10, 0))

        result = check_child_access(session, child, datetime(2026, 5, 11, 10, 0, 0))

        assert result.allowed is False
        assert result.reason == "outside_time_window"

    def test_multiple_windows_or_logic(self, session: Session):
        child = make_child(session)
        add_window(session, child, ALL_DAYS_WINDOW, time(8, 0), time(12, 0))
        add_window(session, child, ALL_DAYS_WINDOW, time(14, 0), time(18, 0))

        assert check_child_access(session, child, datetime(2026, 5, 11, 10, 0)).allowed is True
        assert check_child_access(session, child, datetime(2026, 5, 11, 15, 0)).allowed is True
        assert check_child_access(session, child, datetime(2026, 5, 11, 13, 0)).allowed is False

    def test_yesterdays_completions_do_not_count(self, session: Session):
        child = make_child(session)
        add_window(session, child, WEEKDAY_WINDOW, time(8, 0), time(18, 0))
        chore = add_chore(session, child)
        session.add(DailyChoreCompletion(chore_id=chore.id, date=TODAY.replace(day=TODAY.day - 1), completed=True))
        session.commit()

        result = check_child_access(session, child, NOW)

        assert result.allowed is False
        assert result.reason == "chores_incomplete"


class TestGetAllAccess:
    def test_returns_all_children(self, session: Session):
        make_child(session, "Alice")
        make_child(session, "Bob")

        result = get_all_access(session, NOW)

        assert len(result.children) == 2
        assert {r.child_name for r in result.children} == {"Alice", "Bob"}

    def test_returns_empty_when_no_children(self, session: Session):
        result = get_all_access(session, NOW)
        assert result.children == []
