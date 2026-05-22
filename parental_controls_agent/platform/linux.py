import logging
import subprocess

log = logging.getLogger(__name__)


class LinuxBackend:
    def setup_user(self, username: str) -> None:
        pass  # no extra setup needed on Linux

    def enable_user(self, username: str) -> None:
        log.info("enabling user %s", username)
        result = subprocess.run(["usermod", "-U", username], capture_output=True, text=True)
        if result.returncode != 0:
            # Passwordless accounts have nothing to unlock; log and move on
            log.warning("usermod -U failed for %s (rc=%d): %s", username, result.returncode, result.stderr.strip())

    def disable_user(self, username: str) -> None:
        log.info("disabling user %s", username)
        result = subprocess.run(["usermod", "-L", username], capture_output=True, text=True)
        if result.returncode != 0:
            log.warning("usermod -L failed for %s (rc=%d): %s", username, result.returncode, result.stderr.strip())

    def force_logoff(self, username: str) -> None:
        log.info("terminating sessions for %s", username)
        if self._kde_logout(username):
            return
        self._loginctl_terminate_sessions(username)

    def _loginctl_terminate_sessions(self, username: str) -> None:
        result = subprocess.run(
            ["loginctl", "list-sessions", "--no-legend"],
            capture_output=True,
            text=True,
        )
        sessions = [
            line.split()[0]
            for line in result.stdout.splitlines()
            if len(line.split()) >= 3 and line.split()[2] == username
        ]
        if not sessions:
            log.info("no loginctl sessions found for %s", username)
            return
        for session_id in sessions:
            log.info("terminating session %s for %s", session_id, username)
            subprocess.run(["loginctl", "terminate-session", session_id])

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
