import logging
import subprocess

log = logging.getLogger(__name__)


class WindowsBackend:
    def enable_user(self, username: str) -> None:
        log.info("enabling user %s", username)
        subprocess.run(["net", "user", username, "/active:yes"], check=True)

    def disable_user(self, username: str) -> None:
        log.info("disabling user %s", username)
        subprocess.run(["net", "user", username, "/active:no"], check=True)

    def force_logoff(self, username: str) -> None:
        log.info("logging off sessions for %s", username)
        result = subprocess.run(
            ["quser", username],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # User has no active sessions — nothing to do
            return
        for line in result.stdout.splitlines()[1:]:  # skip header row
            parts = line.split()
            if len(parts) >= 3:
                session_id = parts[2]
                subprocess.run(["logoff", session_id])
