from datetime import date

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from parental_controls.models.child import Child
from parental_controls.models.chore import Chore
from parental_controls.services.pin_service import hash_pin


def make_child(session: Session) -> Child:
    child = Child(name="Alice", pin_hash=hash_pin("1234"))
    session.add(child)
    session.commit()
    session.refresh(child)
    return child


@pytest.mark.asyncio
async def test_create_and_list_chores(client: AsyncClient, session: Session):
    child = make_child(session)
    response = await client.post(
        f"/api/v1/children/{child.id}/chores",
        json={"name": "Make bed", "icon": "🛏️", "sort_order": 0},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Make bed"
    assert data["icon"] == "🛏️"

    list_resp = await client.get(f"/api/v1/children/{child.id}/chores")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


@pytest.mark.asyncio
async def test_mark_chore_complete_and_incomplete(client: AsyncClient, session: Session):
    child = make_child(session)
    chore = Chore(child_id=child.id, name="Feed dog", icon="🐕")
    session.add(chore)
    session.commit()
    session.refresh(chore)

    today = str(date.today())
    complete_resp = await client.post(
        f"/api/v1/chores/{chore.id}/complete",
        params={"chore_date": today},
    )
    assert complete_resp.status_code == 201
    assert complete_resp.json()["completed"] is True

    # Marking complete again is idempotent
    again = await client.post(f"/api/v1/chores/{chore.id}/complete", params={"chore_date": today})
    assert again.status_code == 201

    # Mark incomplete
    incomplete_resp = await client.delete(f"/api/v1/chores/{chore.id}/complete", params={"chore_date": today})
    assert incomplete_resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_chore(client: AsyncClient, session: Session):
    child = make_child(session)
    chore = Chore(child_id=child.id, name="Sweep", icon="🧹")
    session.add(chore)
    session.commit()
    session.refresh(chore)

    resp = await client.delete(f"/api/v1/children/chores/{chore.id}")
    assert resp.status_code == 204
