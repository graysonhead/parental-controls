from dataclasses import dataclass
from datetime import datetime

import httpx


@dataclass
class ChildAccess:
    child_id: int
    child_name: str
    allowed: bool
    reason: str


@dataclass
class AccessResponse:
    checked_at: datetime
    children: list[ChildAccess]


def fetch_access(server_url: str, timeout: float = 10.0) -> AccessResponse:
    response = httpx.get(f"{server_url}/api/v1/access", timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return AccessResponse(
        checked_at=datetime.fromisoformat(data["checked_at"]),
        children=[
            ChildAccess(
                child_id=c["child_id"],
                child_name=c["child_name"],
                allowed=c["allowed"],
                reason=c["reason"],
            )
            for c in data["children"]
        ],
    )
