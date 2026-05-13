from datetime import date

import pytest
from sqlmodel import Session

from parental_controls.models.child import Child
from parental_controls.models.chore import Chore
from parental_controls.models.chore_completion import DailyChoreCompletion
from parental_controls.services.chore_service import (
    all_chores_complete,
    get_todays_completions,
    upsert_completion,
)

TODAY = date(2026, 5, 11)
YESTERDAY = date(2026, 5, 10)


def make_child(session: Session, name: str = "Alice") -> Child:
    child = Child(name=name, pin_hash="x")
    session.add(child)
    session.commit()
    session.refresh(child)
    return child


def make_chore(session: Session, child: Child, name: str = "Chore") -> Chore:
    chore = Chore(child_id=child.id, name=name, icon="✅")
    session.add(chore)
    session.commit()
    session.refresh(chore)
    return chore


class TestGetTodaysCompletions:
    def test_returns_todays_records(self, session: Session):
        child = make_child(session)
        chore = make_chore(session, child)
        session.add(DailyChoreCompletion(chore_id=chore.id, date=TODAY, completed=True))
        session.commit()

        completions = get_todays_completions(session, child.id, TODAY)

        assert len(completions) == 1
        assert completions[0].chore_id == chore.id

    def test_does_not_return_yesterdays_records(self, session: Session):
        child = make_child(session)
        chore = make_chore(session, child)
        session.add(DailyChoreCompletion(chore_id=chore.id, date=YESTERDAY, completed=True))
        session.commit()

        completions = get_todays_completions(session, child.id, TODAY)

        assert len(completions) == 0

    def test_returns_empty_when_no_chores(self, session: Session):
        child = make_child(session)
        completions = get_todays_completions(session, child.id, TODAY)
        assert completions == []


class TestUpsertCompletion:
    def test_creates_new_record(self, session: Session):
        child = make_child(session)
        chore = make_chore(session, child)

        completion = upsert_completion(session, chore.id, TODAY, True)

        assert completion.completed is True
        assert completion.completed_at is not None

    def test_updates_existing_record(self, session: Session):
        child = make_child(session)
        chore = make_chore(session, child)
        upsert_completion(session, chore.id, TODAY, True)

        # Mark incomplete again
        completion = upsert_completion(session, chore.id, TODAY, False)

        assert completion.completed is False
        assert completion.completed_at is None

    def test_upsert_does_not_create_duplicates(self, session: Session):
        child = make_child(session)
        chore = make_chore(session, child)

        upsert_completion(session, chore.id, TODAY, True)
        upsert_completion(session, chore.id, TODAY, True)

        completions = get_todays_completions(session, child.id, TODAY)
        assert len(completions) == 1


class TestAllChoresComplete:
    def test_true_when_all_complete(self, session: Session):
        child = make_child(session)
        chore1 = make_chore(session, child, "Chore 1")
        chore2 = make_chore(session, child, "Chore 2")
        upsert_completion(session, chore1.id, TODAY, True)
        upsert_completion(session, chore2.id, TODAY, True)

        assert all_chores_complete(session, child.id, TODAY) is True

    def test_false_when_some_incomplete(self, session: Session):
        child = make_child(session)
        chore1 = make_chore(session, child, "Chore 1")
        make_chore(session, child, "Chore 2")
        upsert_completion(session, chore1.id, TODAY, True)

        assert all_chores_complete(session, child.id, TODAY) is False

    def test_true_when_no_chores(self, session: Session):
        child = make_child(session)
        assert all_chores_complete(session, child.id, TODAY) is True
