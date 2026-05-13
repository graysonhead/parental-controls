import pytest
from httpx import AsyncClient
from sqlmodel import Session

from parental_controls.models.child import Child
from parental_controls.models.chore import Chore
from parental_controls.models.chore_completion import DailyChoreCompletion
from parental_controls.services.pin_service import hash_pin
from datetime import date


@pytest.mark.asyncio
async def test_create_and_get_child(client: AsyncClient, session: Session):
    response = await client.post("/api/v1/children", json={"name": "Alice", "pin": "1234"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alice"
    child_id = data["id"]

    get_resp = await client.get(f"/api/v1/children/{child_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Alice"


@pytest.mark.asyncio
async def test_list_children(client: AsyncClient, session: Session):
    session.add(Child(name="Alice", pin_hash=hash_pin("1234")))
    session.add(Child(name="Bob", pin_hash=hash_pin("5678")))
    session.commit()

    response = await client.get("/api/v1/children")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_update_child(client: AsyncClient, session: Session):
    child = Child(name="Alice", pin_hash=hash_pin("1234"))
    session.add(child)
    session.commit()
    session.refresh(child)

    response = await client.put(f"/api/v1/children/{child.id}", json={"name": "Alicia"})
    assert response.status_code == 200
    assert response.json()["name"] == "Alicia"


@pytest.mark.asyncio
async def test_delete_child(client: AsyncClient, session: Session):
    child = Child(name="Alice", pin_hash=hash_pin("1234"))
    session.add(child)
    session.commit()
    session.refresh(child)

    response = await client.delete(f"/api/v1/children/{child.id}")
    assert response.status_code == 204

    get_resp = await client.get(f"/api/v1/children/{child.id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_child_status(client: AsyncClient, session: Session):
    child = Child(name="Alice", pin_hash=hash_pin("1234"))
    session.add(child)
    session.commit()
    session.refresh(child)

    chore = Chore(child_id=child.id, name="Make bed", icon="🛏️")
    session.add(chore)
    session.commit()
    session.refresh(chore)

    today = date.today()
    session.add(DailyChoreCompletion(chore_id=chore.id, date=today, completed=True))
    session.commit()

    response = await client.get(f"/api/v1/children/{child.id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["total_chores"] == 1
    assert data["completed_chores"] == 1
    assert data["chores"][0]["completed"] is True
