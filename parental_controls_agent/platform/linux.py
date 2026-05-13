import logging
import subprocess

log = logging.getLogger(__name__)


class LinuxBackend:
    def enable_user(self, username: str) -> None:
        log.info("enabling user %s", username)
        subprocess.run(["usermod", "-U", username], check=True)

    def disable_user(self, username: str) -> None:
        log.info("disabling user %s", username)
        subprocess.run(["usermod", "-L", username], check=True)

    def force_logoff(self, username: str) -> None:
        log.info("terminating sessions for %s", username)
        # No check=True — loginctl exits non-zero if the user has no sessions
        subprocess.run(["loginctl", "terminate-user", username])
