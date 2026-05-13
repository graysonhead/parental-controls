import pytest
from httpx import AsyncClient
from sqlmodel import Session

from parental_controls.models.child import Child
from parental_controls.services.pin_service import hash_pin


def make_child(session: Session, pin: str = "1234") -> Child:
    child = Child(name="Alice", icon="🧒", display_color="#4A90D9", pin_hash=hash_pin(pin))
    session.add(child)
    session.commit()
    session.refresh(child)
    return child


@pytest.mark.asyncio
async def test_home_page_loads(client: AsyncClient, session: Session):
    make_child(session)
    response = await client.get("/")
    assert response.status_code == 200
    assert "Alice" in response.text


@pytest.mark.asyncio
async def test_pin_entry_page_loads(client: AsyncClient, session: Session):
    child = make_child(session)
    response = await client.get(f"/pin/{child.id}")
    assert response.status_code == 200
    assert "Alice" in response.text


@pytest.mark.asyncio
async def test_correct_child_pin_redirects_to_chore_list(client: AsyncClient, session: Session):
    child = make_child(session, pin="1234")
    response = await client.post(
        f"/pin/{child.id}",
        data={"pin": "1234"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/child/{child.id}"


@pytest.mark.asyncio
async def test_wrong_child_pin_stays_on_pin_page(client: AsyncClient, session: Session):
    child = make_child(session, pin="1234")
    response = await client.post(
        f"/pin/{child.id}",
        data={"pin": "9999"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "Wrong PIN" in response.text


@pytest.mark.asyncio
async def test_parent_pin_page_loads(client: AsyncClient):
    response = await client.get("/pin/parent")
    assert response.status_code == 200
    assert "Parent" in response.text


@pytest.mark.asyncio
async def test_child_page_requires_session(client: AsyncClient, session: Session):
    child = make_child(session)
    response = await client.get(f"/child/{child.id}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"


@pytest.mark.asyncio
async def test_admin_page_requires_session(client: AsyncClient):
    response = await client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
