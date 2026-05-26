import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

_DATA_DIR      = Path("/var/lib/parental-controls")
_DENIED_DIR    = _DATA_DIR / "denied"
_LIB_DIR       = Path("/usr/local/lib/parental-controls")
_CHECK_SCRIPT  = _LIB_DIR / "logon_check.sh"
_AUTOSTART_DIR = Path("/etc/xdg/autostart")
_AUTOSTART     = _AUTOSTART_DIR / "parental-controls.desktop"

_CHECK_SCRIPT_LINES = [
    "#!/bin/bash",
    "# Parental Controls logon check - auto-generated, do not edit.",
    f'DENIED_DIR="{_DENIED_DIR}"',
    'USERNAME=$(id -un)',
    "",
    '[ -f "$DENIED_DIR/$USERNAME" ] || exit 0',
    '[ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ] || exit 0',
    "",
    'MSG="Your computer time is up or your chores are not done yet.\\n\\nYou will be logged off."',
    'TITLE="Parental Controls"',
    "",
    "if command -v kdialog &>/dev/null; then",
    '    kdialog --title "$TITLE" --sorry "$MSG" &',
    "    sleep 10",
    "    kill %1 2>/dev/null",
    "elif command -v zenity &>/dev/null; then",
    '    zenity --warning --title="$TITLE" --text="$MSG" --timeout=10',
    "elif command -v notify-send &>/dev/null; then",
    '    notify-send -u critical -t 10000 "$TITLE" "$MSG"',
    "    sleep 10",
    "else",
    "    sleep 10",
    "fi",
    "",
    'loginctl terminate-session "$XDG_SESSION_ID"',
]

_AUTOSTART_LINES = [
    "[Desktop Entry]",
    "Type=Application",
    "Name=Parental Controls Check",
    f"Exec={_CHECK_SCRIPT}",
    "X-GNOME-Autostart-enabled=true",
    "NoDisplay=true",
]


def _ensure_dirs() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _DENIED_DIR.mkdir(parents=True, exist_ok=True)
    _LIB_DIR.mkdir(parents=True, exist_ok=True)


def _write_check_script() -> None:
    _ensure_dirs()
    _CHECK_SCRIPT.write_text("\n".join(_CHECK_SCRIPT_LINES) + "\n")
    _CHECK_SCRIPT.chmod(0o755)


def _write_autostart() -> None:
    _AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    _AUTOSTART.write_text("\n".join(_AUTOSTART_LINES) + "\n")


class LinuxBackend:
    def setup_user(self, username: str) -> None:
        _write_check_script()
        _write_autostart()

    def enable_user(self, username: str) -> None:
        log.info("enabling user %s", username)
        marker = _DENIED_DIR / username
        if marker.exists():
            marker.unlink()

    def disable_user(self, username: str) -> None:
        log.info("disabling user %s", username)
        _ensure_dirs()
        (_DENIED_DIR / username).touch()

    def force_logoff(self, username: str) -> None:
        log.info("logging off graphical sessions for %s", username)
        graphical = self._graphical_session_ids(username)
        if not graphical:
            log.info("no graphical sessions found for %s", username)
            return

        session_env = self._find_session_env(username)
        if session_env:
            result = subprocess.run(
                ["runuser", "-u", username, "--", str(_CHECK_SCRIPT)],
                env={**os.environ, **session_env},
            )
            if result.returncode == 0:
                return
            log.warning("check script exited %d for %s, falling back", result.returncode, username)

        for session_id in graphical:
            log.info("terminating session %s for %s", session_id, username)
            subprocess.run(["loginctl", "terminate-session", session_id])

    def _graphical_session_ids(self, username: str) -> list[str]:
        result = subprocess.run(
            ["loginctl", "list-sessions", "--no-legend"],
            capture_output=True, text=True,
        )
        ids = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2] == username:
                session_id = parts[0]
                if self._session_type(session_id) in ("x11", "wayland", "mir"):
                    ids.append(session_id)
        return ids

    def _session_type(self, session_id: str) -> str:
        result = subprocess.run(
            ["loginctl", "show-session", session_id, "--property=Type"],
            capture_output=True, text=True,
        )
        for line in result.stdout.splitlines():
            if line.startswith("Type="):
                return line.split("=", 1)[1].strip()
        return ""

    def _find_session_env(self, username: str) -> dict | None:
        pids = subprocess.run(["pgrep", "-u", username], capture_output=True, text=True)
        env: dict[str, str] = {}
        for pid in pids.stdout.strip().split():
            try:
                with open(f"/proc/{pid}/environ", "rb") as f:
                    raw = f.read().decode("utf-8", errors="replace")
                for entry in raw.split("\0"):
                    for key in (
                        "DISPLAY", "WAYLAND_DISPLAY",
                        "DBUS_SESSION_BUS_ADDRESS",
                        "XDG_SESSION_ID", "XDG_RUNTIME_DIR",
                    ):
                        if entry.startswith(f"{key}=") and key not in env:
                            env[key] = entry.split("=", 1)[1]
            except (PermissionError, FileNotFoundError):
                continue
        if not env.get("DISPLAY") and not env.get("WAYLAND_DISPLAY"):
            return None
        return env
