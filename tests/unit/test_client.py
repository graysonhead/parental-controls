from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

from parental_controls_agent.client import fetch_access


def make_mock_response(data: dict):
    mock = MagicMock()
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    return mock


SAMPLE_RESPONSE = {
    "checked_at": "2026-05-11T10:00:00",
    "children": [
        {"child_id": 1, "child_name": "Alice", "allowed": True, "reason": "allowed"},
        {"child_id": 2, "child_name": "Bob", "allowed": False, "reason": "chores_incomplete"},
    ],
}


def test_fetch_parses_response():
    with patch("parental_controls_agent.client.httpx.get") as mock_get:
        mock_get.return_value = make_mock_response(SAMPLE_RESPONSE)
        result = fetch_access("http://localhost:8000")

    assert result.checked_at == datetime(2026, 5, 11, 10, 0, 0)
    assert len(result.children) == 2
    assert result.children[0].child_id == 1
    assert result.children[0].child_name == "Alice"
    assert result.children[0].allowed is True
    assert result.children[1].allowed is False
    assert result.children[1].reason == "chores_incomplete"


def test_fetch_hits_correct_url():
    with patch("parental_controls_agent.client.httpx.get") as mock_get:
        mock_get.return_value = make_mock_response(SAMPLE_RESPONSE)
        fetch_access("http://192.168.1.10:8000")

    mock_get.assert_called_once_with(
        "http://192.168.1.10:8000/api/v1/access", timeout=10.0
    )


def test_fetch_raises_on_http_error():
    with patch("parental_controls_agent.client.httpx.get") as mock_get:
        mock_get.return_value.raise_for_status.side_effect = Exception("500")
        with pytest.raises(Exception, match="500"):
            fetch_access("http://localhost:8000")


def test_fetch_handles_empty_children():
    with patch("parental_controls_agent.client.httpx.get") as mock_get:
        mock_get.return_value = make_mock_response(
            {"checked_at": "2026-05-11T10:00:00", "children": []}
        )
        result = fetch_access("http://localhost:8000")

    assert result.children == []
