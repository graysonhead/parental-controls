import logging
import subprocess
import winreg

log = logging.getLogger(__name__)

# Setting a username to 1 here forces it to always appear on the login screen,
# even when the account is disabled. Setting it to 0 hides it always.
_SPECIAL_ACCOUNTS_KEY = (
    r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\SpecialAccounts\UserList"
)


def _pin_to_login_screen(username: str) -> None:
    """Ensure the account tile is always visible on the Windows login screen."""
    with winreg.CreateKeyEx(
        winreg.HKEY_LOCAL_MACHINE,
        _SPECIAL_ACCOUNTS_KEY,
        access=winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, username, 0, winreg.REG_DWORD, 1)


class WindowsBackend:
    def enable_user(self, username: str) -> None:
        log.info("enabling user %s", username)
        _pin_to_login_screen(username)
        subprocess.run(["net", "user", username, "/active:yes"], check=True, capture_output=True)

    def disable_user(self, username: str) -> None:
        log.info("disabling user %s", username)
        # Pin to login screen BEFORE disabling so the tile stays visible.
        # The account being disabled prevents actual login.
        _pin_to_login_screen(username)
        subprocess.run(["net", "user", username, "/active:no"], check=True, capture_output=True)

    def force_logoff(self, username: str) -> None:
        log.info("logging off sessions for %s", username)
        try:
            result = subprocess.run(
                ["quser", username],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines()[1:]:  # skip header
                    parts = line.split()
                    session_id = next((p for p in parts if p.isdigit()), None)
                    if session_id:
                        subprocess.run(["logoff", session_id], check=False, capture_output=True)
                return
        except FileNotFoundError:
            log.debug("quser not found, falling back to taskkill")

        # taskkill is available on all Windows editions
        subprocess.run(
            ["taskkill", "/F", "/FI", f"USERNAME eq {username}"],
            capture_output=True, check=False,
        )
