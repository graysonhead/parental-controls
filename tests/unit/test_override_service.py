from datetime import datetime, time, timedelta

import pytest
from sqlmodel import Session

from parental_controls.models.access_override import AccessOverride, OverrideType
from parental_controls.models.child import Child
from parental_controls.models.time_window import TimeWindow
from parental_controls.services.access_control import check_child_access
from parental_controls.services.override_service import (
    cancel_override,
    compute_expires_at,
    create_override,
    get_active_override,
)

import json

ALL_DAYS = json.dumps([0, 1, 2, 3, 4, 5, 6])
NOW = datetime(2026, 5, 11, 10, 0, 0)  # Monday 10am


def make_child(session: Session, name: str = "Alice") -> Child:
    child = Child(name=name, pin_hash="x")
    session.add(child)
    session.commit()
    session.refresh(child)
    return child


class TestComputeExpiresAt:
    def test_1h(self):
        result = compute_expires_at("1h", NOW)
        assert result == NOW + timedelta(hours=1)

    def test_today(self):
        result = compute_expires_at("today", NOW)
        assert result.date() == NOW.date()
        assert result.hour == 23 and result.minute == 59

    def test_tomorrow(self):
        result = compute_expires_at("tomorrow", NOW)
        assert result.date() == NOW.date() + timedelta(days=1)
        assert result.hour == 23 and result.minute == 59

    def test_weekend_from_monday(self):
        monday = datetime(2026, 5, 11, 10, 0, 0)  # Monday
        result = compute_expires_at("weekend", monday)
        assert result.weekday() == 6  # Sunday
        assert result.hour == 23
        assert result.minute == 59

    def test_weekend_from_saturday(self):
        saturday = datetime(2026, 5, 9, 10, 0, 0)  # Saturday
        result = compute_expires_at("weekend", saturday)
        assert result.weekday() == 6  # Sunday
        assert result.hour == 23

    def test_weekend_from_sunday(self):
        sunday = datetime(2026, 5, 10, 10, 0, 0)  # Sunday
        result = compute_expires_at("weekend", sunday)
        assert result.weekday() == 6  # Still this Sunday
        assert result.hour == 23

    def test_invalid_duration_raises(self):
        with pytest.raises(ValueError):
            compute_expires_at("1d", NOW)


class TestGetActiveOverride:
    def test_returns_none_when_no_overrides(self, session: Session):
        child = make_child(session)
        assert get_active_override(session, child.id, NOW) is None

    def test_returns_active_override(self, session: Session):
        child = make_child(session)
        override = AccessOverride(
            child_id=child.id,
            override_type=OverrideType.GRANT,
            expires_at=NOW + timedelta(hours=1),
            created_at=NOW,
        )
        session.add(override)
        session.commit()

        result = get_active_override(session, child.id, NOW)
        assert result is not None
        assert result.override_type == OverrideType.GRANT

    def test_ignores_expired_override(self, session: Session):
        child = make_child(session)
        override = AccessOverride(
            child_id=child.id,
            override_type=OverrideType.GRANT,
            expires_at=NOW - timedelta(minutes=1),
            created_at=NOW - timedelta(hours=2),
        )
        session.add(override)
        session.commit()

        assert get_active_override(session, child.id, NOW) is None

    def test_returns_most_recent_when_multiple(self, session: Session):
        child = make_child(session)
        older = AccessOverride(
            child_id=child.id,
            override_type=OverrideType.GRANT,
            expires_at=NOW + timedelta(hours=2),
            created_at=NOW - timedelta(minutes=10),
        )
        newer = AccessOverride(
            child_id=child.id,
            override_type=OverrideType.REVOKE,
            expires_at=NOW + timedelta(hours=1),
            created_at=NOW,
        )
        session.add(older)
        session.add(newer)
        session.commit()

        result = get_active_override(session, child.id, NOW)
        assert result.override_type == OverrideType.REVOKE


class TestCancelOverride:
    def test_cancel_existing(self, session: Session):
        child = make_child(session)
        override = AccessOverride(
            child_id=child.id,
            override_type=OverrideType.GRANT,
            expires_at=NOW + timedelta(hours=1),
            created_at=NOW,
        )
        session.add(override)
        session.commit()
        session.refresh(override)

        assert cancel_override(session, override.id) is True
        assert session.get(AccessOverride, override.id) is None

    def test_cancel_nonexistent_returns_false(self, session: Session):
        assert cancel_override(session, 9999) is False


class TestCheckChildAccessWithOverrides:
    def test_grant_override_bypasses_schedule(self, session: Session):
        child = make_child(session)
        # No time windows — normally denied
        override = AccessOverride(
            child_id=child.id,
            override_type=OverrideType.GRANT,
            expires_at=NOW + timedelta(hours=1),
            created_at=NOW,
        )
        session.add(override)
        session.commit()

        result = check_child_access(session, child, NOW)
        assert result.allowed is True
        assert result.reason == "access_granted"

    def test_grant_override_bypasses_incomplete_chores(self, session: Session):
        from parental_controls.models.chore import Chore
        child = make_child(session)
        session.add(TimeWindow(child_id=child.id, days_of_week=ALL_DAYS, start_time=time(8, 0), end_time=time(18, 0)))
        session.add(Chore(child_id=child.id, name="Make bed", icon="🛏️"))
        session.add(AccessOverride(
            child_id=child.id,
            override_type=OverrideType.GRANT,
            expires_at=NOW + timedelta(hours=1),
            created_at=NOW,
        ))
        session.commit()

        result = check_child_access(session, child, NOW)
        assert result.allowed is True
        assert result.reason == "access_granted"

    def test_revoke_override_denies_during_valid_window(self, session: Session):
        child = make_child(session)
        session.add(TimeWindow(child_id=child.id, days_of_week=ALL_DAYS, start_time=time(8, 0), end_time=time(18, 0)))
        session.add(AccessOverride(
            child_id=child.id,
            override_type=OverrideType.REVOKE,
            expires_at=NOW + timedelta(hours=1),
            created_at=NOW,
        ))
        session.commit()

        result = check_child_access(session, child, NOW)
        assert result.allowed is False
        assert result.reason == "access_revoked"

    def test_expired_override_falls_through_to_normal_logic(self, session: Session):
        child = make_child(session)
        session.add(TimeWindow(child_id=child.id, days_of_week=ALL_DAYS, start_time=time(8, 0), end_time=time(18, 0)))
        session.add(AccessOverride(
            child_id=child.id,
            override_type=OverrideType.REVOKE,
            expires_at=NOW - timedelta(minutes=1),
            created_at=NOW - timedelta(hours=2),
        ))
        session.commit()

        result = check_child_access(session, child, NOW)
        assert result.allowed is True
        assert result.reason == "allowed"
