from datetime import date, datetime
from typing import List

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from parental_controls.models.chore import Chore
from parental_controls.models.chore_completion import DailyChoreCompletion


def get_todays_completions(session: Session, child_id: int, today: date) -> List[DailyChoreCompletion]:
    chores = session.exec(select(Chore).where(Chore.child_id == child_id)).all()
    if not chores:
        return []
    chore_ids = [c.id for c in chores]
    return session.exec(
        select(DailyChoreCompletion).where(
            DailyChoreCompletion.chore_id.in_(chore_ids),
            DailyChoreCompletion.date == today,
        )
    ).all()


def upsert_completion(
    session: Session, chore_id: int, today: date, completed: bool
) -> DailyChoreCompletion:
    existing = session.exec(
        select(DailyChoreCompletion).where(
            DailyChoreCompletion.chore_id == chore_id,
            DailyChoreCompletion.date == today,
        )
    ).first()
    if existing:
        existing.completed = completed
        existing.completed_at = datetime.now() if completed else None
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    else:
        completion = DailyChoreCompletion(
            chore_id=chore_id,
            date=today,
            completed=completed,
            completed_at=datetime.now() if completed else None,
        )
        session.add(completion)
        session.commit()
        session.refresh(completion)
        return completion


def all_chores_complete(session: Session, child_id: int, today: date) -> bool:
    chores = session.exec(select(Chore).where(Chore.child_id == child_id)).all()
    if not chores:
        return True
    completions = get_todays_completions(session, child_id, today)
    completed_ids = {c.chore_id for c in completions if c.completed}
    return all(c.id in completed_ids for c in chores)
