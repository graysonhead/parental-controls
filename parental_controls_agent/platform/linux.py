import logging
import subprocess

log = logging.getLogger(__name__)


class LinuxBackend:
    def setup_user(self, username: str) -> None:
        pass  # no extra setup needed on Linux

    def enable_user(self, username: str) -> None:
        log.info("enabling user %s", username)
        subprocess.run(["usermod", "-U", username], check=True)

    def disable_user(self, username: str) -> None:
        log.info("disabling user %s", username)
        subprocess.run(["usermod", "-L", username], check=True)

    def force_logoff(self, username: str) -> None:
        log.info("terminating sessions for %s", username)
        if self._kde_logout(username):
            return
        # No check=True — loginctl exits non-zero if the user has no sessions
        subprocess.run(["loginctl", "terminate-user", username])

    def _kde_logout(self, username: str) -> bool:
        dbus_addr = self._find_dbus_address(username)
        if not dbus_addr:
            return False

        log.info("attempting KDE graceful logout for %s", username)
        result = subprocess.run(
            [
                "runuser", "-u", username, "--",
                "qdbus", "org.kde.ksmserver", "/KSMServer",
                "logout", "0", "0", "2",
            ],
            env={"DBUS_SESSION_BUS_ADDRESS": dbus_addr},
            timeout=10,
        )
        if result.returncode == 0:
            log.info("KDE logout succeeded for %s", username)
            return True
        log.warning("qdbus logout returned %d for %s", result.returncode, username)
        return False

    def _find_dbus_address(self, username: str) -> str | None:
        pids = subprocess.run(
            ["pgrep", "-u", username],
            capture_output=True,
            text=True,
        )
        for pid in pids.stdout.strip().split():
            try:
                with open(f"/proc/{pid}/environ", "rb") as f:
                    raw = f.read().decode("utf-8", errors="replace")
                for entry in raw.split("\0"):
                    if entry.startswith("DBUS_SESSION_BUS_ADDRESS="):
                        return entry.split("=", 1)[1]
            except (PermissionError, FileNotFoundError):
                continue
        return None
