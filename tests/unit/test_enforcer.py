from datetime import datetime
from unittest.mock import MagicMock, call

import pytest

from parental_controls_agent.client import AccessResponse, ChildAccess
from parental_controls_agent.enforcer import Enforcer

NOW = datetime(2026, 5, 11, 10, 0, 0)

CHILDREN = {"Alice": "alice", "Bob": "bob"}


def make_response(*children: tuple[int, str, bool, str]) -> AccessResponse:
    return AccessResponse(
        checked_at=NOW,
        children=[
            ChildAccess(child_id=cid, child_name=name, allowed=allowed, reason=reason)
            for cid, name, allowed, reason in children
        ],
    )


@pytest.fixture
def backend():
    return MagicMock()


@pytest.fixture
def enforcer(backend):
    return Enforcer(children=CHILDREN, backend=backend)


class TestInitialPoll:
    def test_enables_user_when_initially_allowed(self, enforcer, backend):
        enforcer.apply(make_response((1, "Alice", True, "allowed")))
        backend.enable_user.assert_called_once_with("alice")
        backend.disable_user.assert_not_called()

    def test_disables_and_logoffs_when_initially_denied(self, enforcer, backend):
        enforcer.apply(make_response((1, "Alice", False, "outside_time_window")))
        backend.disable_user.assert_called_once_with("alice")
        backend.force_logoff.assert_called_once_with("alice")

    def test_skips_unknown_child_name(self, enforcer, backend):
        enforcer.apply(make_response((99, "Unknown", True, "allowed")))
        backend.enable_user.assert_not_called()


class TestSubsequentPolls:
    def test_enables_on_transition_denied_to_allowed(self, enforcer, backend):
        enforcer.apply(make_response((1, "Alice", False, "outside_time_window")))
        backend.reset_mock()
        enforcer.apply(make_response((1, "Alice", True, "allowed")))
        backend.enable_user.assert_called_once_with("alice")
        backend.disable_user.assert_not_called()
        backend.force_logoff.assert_not_called()

    def test_disables_and_logoffs_on_transition_allowed_to_denied(self, enforcer, backend):
        enforcer.apply(make_response((1, "Alice", True, "allowed")))
        backend.reset_mock()
        enforcer.apply(make_response((1, "Alice", False, "chores_incomplete")))
        backend.disable_user.assert_called_once_with("alice")
        backend.force_logoff.assert_called_once_with("alice")
        backend.enable_user.assert_not_called()

    def test_no_action_when_state_unchanged_allowed(self, enforcer, backend):
        enforcer.apply(make_response((1, "Alice", True, "allowed")))
        backend.reset_mock()
        enforcer.apply(make_response((1, "Alice", True, "allowed")))
        backend.enable_user.assert_not_called()
        backend.disable_user.assert_not_called()

    def test_no_action_when_state_unchanged_denied(self, enforcer, backend):
        enforcer.apply(make_response((1, "Alice", False, "outside_time_window")))
        backend.reset_mock()
        enforcer.apply(make_response((1, "Alice", False, "outside_time_window")))
        backend.disable_user.assert_not_called()
        backend.force_logoff.assert_not_called()

    def test_handles_multiple_children_independently(self, enforcer, backend):
        enforcer.apply(make_response(
            (1, "Alice", True, "allowed"),
            (2, "Bob", True, "allowed"),
        ))
        backend.reset_mock()
        # Alice loses access, Bob keeps it
        enforcer.apply(make_response(
            (1, "Alice", False, "chores_incomplete"),
            (2, "Bob", True, "allowed"),
        ))
        backend.disable_user.assert_called_once_with("alice")
        backend.force_logoff.assert_called_once_with("alice")
        backend.enable_user.assert_not_called()
