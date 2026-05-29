from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from parental_controls.models.access_override import AccessOverride, OverrideType
from parental_controls.models.child import Child
from parental_controls.services.pin_service import hash_pin


def make_child(session: Session, name: str = "Alice") -> Child:
    child = Child(name=name, pin_hash=hash_pin("1234"))
    session.add(child)
    session.commit()
    session.refresh(child)
    return child


@pytest.mark.asyncio
async def test_create_grant_override(client: AsyncClient, session: Session):
    child = make_child(session)

    response = await client.post(
        f"/api/v1/children/{child.id}/overrides",
        json={"override_type": "grant", "duration": "1h"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["override_type"] == "grant"
    assert data["child_id"] == child.id
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_create_revoke_override_with_reason(client: AsyncClient, session: Session):
    child = make_child(session)

    response = await client.post(
        f"/api/v1/children/{child.id}/overrides",
        json={"override_type": "revoke", "duration": "today", "reason": "Lost screen time"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["override_type"] == "revoke"
    assert data["reason"] == "Lost screen time"


@pytest.mark.asyncio
async def test_create_weekend_override(client: AsyncClient, session: Session):
    child = make_child(session)

    response = await client.post(
        f"/api/v1/children/{child.id}/overrides",
        json={"override_type": "grant", "duration": "weekend"},
    )

    assert response.status_code == 201
    from datetime import datetime
    expires = datetime.fromisoformat(response.json()["expires_at"])
    assert expires.weekday() == 6  # Sunday
    assert expires.hour == 23


@pytest.mark.asyncio
async def test_create_override_invalid_child(client: AsyncClient, session: Session):
    response = await client.post(
        "/api/v1/children/9999/overrides",
        json={"override_type": "grant", "duration": "1h"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_override_invalid_duration(client: AsyncClient, session: Session):
    child = make_child(session)

    response = await client.post(
        f"/api/v1/children/{child.id}/overrides",
        json={"override_type": "grant", "duration": "1d"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_overrides_returns_only_active(client: AsyncClient, session: Session):
    child = make_child(session)
    now = datetime.now()
    session.add(AccessOverride(
        child_id=child.id,
        override_type=OverrideType.GRANT,
        expires_at=now + timedelta(hours=1),
        created_at=now,
    ))
    session.add(AccessOverride(
        child_id=child.id,
        override_type=OverrideType.REVOKE,
        expires_at=now - timedelta(minutes=1),
        created_at=now - timedelta(hours=2),
    ))
    session.commit()

    response = await client.get(f"/api/v1/children/{child.id}/overrides")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["override_type"] == "grant"


@pytest.mark.asyncio
async def test_list_overrides_empty(client: AsyncClient, session: Session):
    child = make_child(session)

    response = await client.get(f"/api/v1/children/{child.id}/overrides")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_delete_override(client: AsyncClient, session: Session):
    child = make_child(session)
    override = AccessOverride(
        child_id=child.id,
        override_type=OverrideType.GRANT,
        expires_at=datetime.now() + timedelta(hours=1),
        created_at=datetime.now(),
    )
    session.add(override)
    session.commit()
    session.refresh(override)

    response = await client.delete(f"/api/v1/overrides/{override.id}")
    assert response.status_code == 204

    response = await client.get(f"/api/v1/children/{child.id}/overrides")
    assert response.json() == []


@pytest.mark.asyncio
async def test_delete_nonexistent_override(client: AsyncClient, session: Session):
    response = await client.delete("/api/v1/overrides/9999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_all_overrides(client: AsyncClient, session: Session):
    child1 = make_child(session, "Alice")
    child2 = make_child(session, "Bob")
    now = datetime.now()
    session.add(AccessOverride(child_id=child1.id, override_type=OverrideType.GRANT, expires_at=now + timedelta(hours=1), created_at=now))
    session.add(AccessOverride(child_id=child2.id, override_type=OverrideType.REVOKE, expires_at=now + timedelta(hours=2), created_at=now))
    session.add(AccessOverride(child_id=child1.id, override_type=OverrideType.GRANT, expires_at=now - timedelta(minutes=1), created_at=now - timedelta(hours=2)))  # expired
    session.commit()

    response = await client.get("/api/v1/overrides")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    child_ids = {d["child_id"] for d in data}
    assert child_ids == {child1.id, child2.id}


@pytest.mark.asyncio
async def test_access_reflects_grant_override(client: AsyncClient, session: Session):
    from unittest.mock import patch
    child = make_child(session)
    # No time windows — would normally be denied
    now = datetime(2026, 5, 11, 10, 0, 0)
    session.add(AccessOverride(
        child_id=child.id,
        override_type=OverrideType.GRANT,
        expires_at=now + timedelta(hours=1),
        created_at=now,
    ))
    session.commit()

    with patch("parental_controls.api.access.datetime") as mock_dt:
        mock_dt.now.return_value = now
        response = await client.get("/api/v1/access")

    assert response.status_code == 200
    child_result = response.json()["children"][0]
    assert child_result["allowed"] is True
    assert child_result["reason"] == "access_granted"
    assert child_result["active_override"] is not None
    assert child_result["active_override"]["override_type"] == "grant"


@pytest.mark.asyncio
async def test_access_reflects_revoke_override(client: AsyncClient, session: Session):
    from unittest.mock import patch
    import json
    from datetime import time
    from parental_controls.models.time_window import TimeWindow

    child = make_child(session)
    # Valid time window — would normally be allowed
    session.add(TimeWindow(
        child_id=child.id,
        days_of_week=json.dumps([0, 1, 2, 3, 4, 5, 6]),
        start_time=time(8, 0),
        end_time=time(18, 0),
    ))
    now = datetime(2026, 5, 11, 10, 0, 0)
    session.add(AccessOverride(
        child_id=child.id,
        override_type=OverrideType.REVOKE,
        expires_at=now + timedelta(hours=1),
        created_at=now,
    ))
    session.commit()

    with patch("parental_controls.api.access.datetime") as mock_dt:
        mock_dt.now.return_value = now
        response = await client.get("/api/v1/access")

    assert response.status_code == 200
    child_result = response.json()["children"][0]
    assert child_result["allowed"] is False
    assert child_result["reason"] == "access_revoked"
