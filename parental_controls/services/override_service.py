from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from parental_controls.models.access_override import AccessOverride, OverrideType

DURATION_DELTAS = {
    "1h": timedelta(hours=1),
}

_END_OF_DAY = datetime.min.time().replace(hour=23, minute=59, second=59, microsecond=0)


def compute_expires_at(duration: str, now: datetime) -> datetime:
    if duration in DURATION_DELTAS:
        return now + DURATION_DELTAS[duration]
    if duration == "today":
        return datetime.combine(now.date(), _END_OF_DAY)
    if duration == "tomorrow":
        return datetime.combine(now.date() + timedelta(days=1), _END_OF_DAY)
    if duration == "weekend":
        days_until_sunday = (6 - now.weekday()) % 7
        coming_sunday = now.date() + timedelta(days=days_until_sunday)
        return datetime.combine(coming_sunday, _END_OF_DAY)
    raise ValueError(f"Unknown duration: {duration!r}. Valid: 1h, 2h, 3h, 4h, today, tomorrow, weekend")


def get_active_overrides(session: Session, child_id: int, now: datetime) -> list[AccessOverride]:
    return list(session.exec(
        select(AccessOverride)
        .where(AccessOverride.child_id == child_id)
        .where(AccessOverride.expires_at > now)
        .order_by(AccessOverride.created_at.desc())
    ).all())


def get_active_override(session: Session, child_id: int, now: datetime) -> Optional[AccessOverride]:
    overrides = get_active_overrides(session, child_id, now)
    return overrides[0] if overrides else None


def create_override(
    session: Session,
    child_id: int,
    override_type: OverrideType,
    duration: str,
    reason: Optional[str],
    now: datetime,
) -> AccessOverride:
    override = AccessOverride(
        child_id=child_id,
        override_type=override_type,
        reason=reason,
        expires_at=compute_expires_at(duration, now),
        created_at=now,
    )
    session.add(override)
    session.commit()
    session.refresh(override)
    return override


def cancel_override(session: Session, override_id: int) -> bool:
    override = session.get(AccessOverride, override_id)
    if override is None:
        return False
    session.delete(override)
    session.commit()
    return True
