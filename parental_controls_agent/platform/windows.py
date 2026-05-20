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
        try:
            result = subprocess.run(
                ["quser", username],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines()[1:]:  # skip header row
                    # Session ID is the first bare integer in the line.
                    # (SESSIONNAME can be blank for disconnected sessions, which shifts
                    # whitespace-split columns — scanning for the first integer is robust.)
                    parts = line.split()
                    session_id = next((p for p in parts if p.isdigit()), None)
                    if session_id:
                        subprocess.run(["logoff", session_id], check=False)
                return
        except FileNotFoundError:
            log.debug("quser not found, falling back to taskkill")

        # taskkill is available on all Windows editions and terminates all
        # processes owned by the user, which forces their session to end.
        subprocess.run(
            ["taskkill", "/F", "/FI", f"USERNAME eq {username}"],
            capture_output=True,
            check=False,
        )
