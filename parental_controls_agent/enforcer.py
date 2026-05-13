import logging

from parental_controls_agent.client import AccessResponse
from parental_controls_agent.platform.base import PlatformBackend

log = logging.getLogger(__name__)


class Enforcer:
    def __init__(self, children: dict[str, str], backend: PlatformBackend):
        self._children = children        # child_name -> OS username
        self._backend = backend
        self._last_state: dict[str, bool | None] = {}

    def apply(self, response: AccessResponse) -> None:
        for child in response.children:
            username = self._children.get(child.child_name)
            if username is None:
                log.debug("'%s' not in config, skipping", child.child_name)
                continue

            was_allowed = self._last_state.get(child.child_name)
            is_allowed = child.allowed

            if was_allowed is None:
                self._apply_state(username, is_allowed, child.child_name)
            elif is_allowed and not was_allowed:
                log.info("%s (%s): access granted", child.child_name, username)
                self._backend.enable_user(username)
            elif not is_allowed and was_allowed:
                log.info(
                    "%s (%s): access revoked (%s)",
                    child.child_name, username, child.reason,
                )
                self._backend.disable_user(username)
                self._backend.force_logoff(username)
            else:
                log.debug("%s: no change (allowed=%s)", child.child_name, is_allowed)

            self._last_state[child.child_name] = is_allowed

    def _apply_state(self, username: str, allowed: bool, name: str) -> None:
        log.info("%s (%s): initial state allowed=%s", name, username, allowed)
        if allowed:
            self._backend.enable_user(username)
        else:
            self._backend.disable_user(username)
            self._backend.force_logoff(username)
