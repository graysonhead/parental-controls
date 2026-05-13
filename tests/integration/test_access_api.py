import json
from datetime import datetime, time
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from parental_controls.models.child import Child
from parental_controls.models.chore import Chore
from parental_controls.models.chore_completion import DailyChoreCompletion
from parental_controls.models.time_window import TimeWindow
from parental_controls.services.pin_service import hash_pin

ALL_DAYS = json.dumps([0, 1, 2, 3, 4, 5, 6])
FIXED_NOW = datetime(2026, 5, 11, 10, 0, 0)  # Monday 10am


def make_child(session: Session, name: str = "Alice") -> Child:
    child = Child(name=name, pin_hash=hash_pin("1234"))
    session.add(child)
    session.commit()
    session.refresh(child)
    session.add(TimeWindow(child_id=child.id, days_of_week=ALL_DAYS, start_time=time(8, 0), end_time=time(18, 0)))
    session.commit()
    return child


@pytest.mark.asyncio
async def test_access_allowed_when_all_conditions_met(client: AsyncClient, session: Session):
    child = make_child(session)
    chore = Chore(child_id=child.id, name="Make bed", icon="🛏️")
    session.add(chore)
    session.commit()
    session.refresh(chore)
    session.add(DailyChoreCompletion(chore_id=chore.id, date=FIXED_NOW.date(), completed=True))
    session.commit()

    with patch("parental_controls.api.access.datetime") as mock_dt:
        mock_dt.now.return_value = FIXED_NOW
        response = await client.get("/api/v1/access")

    assert response.status_code == 200
    data = response.json()
    assert len(data["children"]) == 1
    assert data["children"][0]["allowed"] is True
    assert data["children"][0]["reason"] == "allowed"
    assert data["children"][0]["child_name"] == "Alice"


@pytest.mark.asyncio
async def test_access_denied_outside_time_window(client: AsyncClient, session: Session):
    make_child(session)
    night = datetime(2026, 5, 11, 22, 0, 0)

    with patch("parental_controls.api.access.datetime") as mock_dt:
        mock_dt.now.return_value = night
        response = await client.get("/api/v1/access")

    assert response.status_code == 200
    assert response.json()["children"][0]["reason"] == "outside_time_window"


@pytest.mark.asyncio
async def test_access_denied_chores_incomplete(client: AsyncClient, session: Session):
    child = make_child(session)
    session.add(Chore(child_id=child.id, name="Feed dog", icon="🐕"))
    session.commit()

    with patch("parental_controls.api.access.datetime") as mock_dt:
        mock_dt.now.return_value = FIXED_NOW
        response = await client.get("/api/v1/access")

    assert response.status_code == 200
    assert response.json()["children"][0]["reason"] == "chores_incomplete"


@pytest.mark.asyncio
async def test_access_returns_all_children(client: AsyncClient, session: Session):
    make_child(session, "Alice")
    make_child(session, "Bob")

    with patch("parental_controls.api.access.datetime") as mock_dt:
        mock_dt.now.return_value = FIXED_NOW
        response = await client.get("/api/v1/access")

    assert response.status_code == 200
    data = response.json()
    assert len(data["children"]) == 2
    assert {c["child_name"] for c in data["children"]} == {"Alice", "Bob"}


@pytest.mark.asyncio
async def test_access_returns_empty_when_no_children(client: AsyncClient, session: Session):
    with patch("parental_controls.api.access.datetime") as mock_dt:
        mock_dt.now.return_value = FIXED_NOW
        response = await client.get("/api/v1/access")

    assert response.status_code == 200
    assert response.json()["children"] == []


@pytest.mark.asyncio
async def test_access_response_shape(client: AsyncClient, session: Session):
    make_child(session)

    with patch("parental_controls.api.access.datetime") as mock_dt:
        mock_dt.now.return_value = FIXED_NOW
        response = await client.get("/api/v1/access")

    data = response.json()
    assert "checked_at" in data
    assert "children" in data
    child_entry = data["children"][0]
    assert "child_id" in child_entry
    assert "child_name" in child_entry
    assert "allowed" in child_entry
    assert "reason" in child_entry
