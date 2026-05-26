import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

_DATA_DIR     = Path("/var/lib/parental-controls")
_DENIED_DIR   = _DATA_DIR / "denied"
_CHECK_SCRIPT = _DATA_DIR / "logon_check.sh"

_LOG_FILE = _DATA_DIR / "logon_check.log"

_CHECK_SCRIPT_LINES = [
    "#!/bin/bash",
    "# Parental Controls logon check - auto-generated, do not edit.",
    f'exec >>{_LOG_FILE} 2>&1',
    "echo \"$(date): logon_check started user=$(id -un) DISPLAY=$DISPLAY WAYLAND=$WAYLAND_DISPLAY\"",
    "PATH=/run/current-system/sw/bin:/usr/bin:/bin:$PATH",
    f'DENIED_DIR="{_DENIED_DIR}"',
    'USERNAME=$(id -un)',
    "",
    '[ -f "$DENIED_DIR/$USERNAME" ] || { echo "$(date): no denied marker, exiting"; exit 0; }',
    '[ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ] || { echo "$(date): no display, exiting"; exit 0; }',
    "",
    'MSG="Your computer time is up or your chores are not done yet.\\n\\nYou will be logged off."',
    'TITLE="Parental Controls"',
    "",
    "echo \"$(date): sending notification\"",
    "gdbus call --session \\",
    "    --dest org.freedesktop.Notifications \\",
    "    --object-path /org/freedesktop/Notifications \\",
    "    --method org.freedesktop.Notifications.Notify \\",
    '    "Parental Controls" 0 "dialog-warning" "$TITLE" "$MSG" \'[]\' \'{}\' 10000',
    "echo \"$(date): notification sent (rc=$?), sleeping 10s\"",
    "sleep 10",
    "",
    "echo \"$(date): calling qdbus logout\"",
    "qdbus org.kde.Shutdown /Shutdown logout",
    "echo \"$(date): qdbus logout returned rc=$?\"",
]

def _ensure_dirs() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _DENIED_DIR.mkdir(parents=True, exist_ok=True)


def _write_check_script() -> None:
    _ensure_dirs()
    _CHECK_SCRIPT.write_text("\n".join(_CHECK_SCRIPT_LINES) + "\n")
    _CHECK_SCRIPT.chmod(0o755)


def _autostart_file(username: str) -> Path:
    import pwd
    home = Path(pwd.getpwnam(username).pw_dir)
    return home / ".config" / "autostart" / "parental-controls.desktop"


def _write_autostart(username: str) -> None:
    autostart = _autostart_file(username)
    autostart.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        "Name=Parental Controls Check",
        f"Exec={_CHECK_SCRIPT}",
        "X-GNOME-Autostart-enabled=true",
        "NoDisplay=true",
    ]
    autostart.write_text("\n".join(lines) + "\n")
    autostart.chmod(0o444)  # root-owned, read-only so the user can't remove it


class LinuxBackend:
    def setup_user(self, username: str) -> None:
        _write_check_script()
        _write_autostart(username)

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
        log.info("logging off graphical session for %s", username)
        session_env = self._find_session_env(username)
        if not session_env:
            log.info("no graphical session found for %s", username)
            return
        result = subprocess.run(
            ["runuser", "-u", username, "--", str(_CHECK_SCRIPT)],
            env={**os.environ, **session_env},
        )
        if result.returncode != 0:
            log.warning("check script exited %d for %s", result.returncode, username)

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
