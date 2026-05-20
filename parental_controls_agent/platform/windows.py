import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_DATA_DIR     = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "ParentalControls"
_DENIED_DIR   = _DATA_DIR / "denied"
_CHECK_SCRIPT = _DATA_DIR / "logon_check.py"

# Build the logon-check script content from plain lines to avoid any encoding
# issues with multi-line string literals in the source file.
_CHECK_LINES = [
    '"""Parental Controls logon check - auto-generated, do not edit."""',
    "import ctypes, os",
    "from pathlib import Path",
    "",
    r'denied = Path(r"C:\ProgramData\ParentalControls\denied") / os.environ.get("USERNAME", "")',
    "if denied.exists():",
    "    ctypes.windll.user32.MessageBoxTimeoutW(",
    "        None,",
    '        "Your computer time is up or your chores are not done yet.\\n\\nYou will be logged off.",',
    '        "Parental Controls",',
    "        0x30,",
    "        0,",
    "        5000,",
    "    )",
    "    # EWX_LOGOFF | EWX_FORCE",
    "    ctypes.windll.user32.ExitWindowsEx(0x00000004, 0)",
]


def _ensure_dirs() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _DENIED_DIR.mkdir(parents=True, exist_ok=True)


def _write_check_script() -> None:
    _ensure_dirs()
    _CHECK_SCRIPT.write_text("\n".join(_CHECK_LINES) + "\n", encoding="utf-8")


def _logon_task_name(username: str) -> str:
    return f"ParentalControlsLogon_{username}"


def _create_logon_task(username: str) -> None:
    task_name = _logon_task_name(username)

    probe = subprocess.run(
        ["schtasks", "/query", "/tn", task_name],
        capture_output=True,
    )
    if probe.returncode == 0:
        log.debug("logon task already exists for %s", username)
        return

    computer   = os.environ.get("COMPUTERNAME", "localhost")
    python_exe = sys.executable

    task_xml = "\n".join([
        '<?xml version="1.0" encoding="UTF-16"?>',
        '<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">',
        "  <Triggers>",
        "    <LogonTrigger>",
        "      <Enabled>true</Enabled>",
        f"      <UserId>{computer}\\{username}</UserId>",
        "    </LogonTrigger>",
        "  </Triggers>",
        "  <Principals>",
        '    <Principal id="Author">',
        f"      <UserId>{computer}\\{username}</UserId>",
        "      <LogonType>InteractiveToken</LogonType>",
        "      <RunLevel>LeastPrivilege</RunLevel>",
        "    </Principal>",
        "  </Principals>",
        "  <Settings>",
        "    <ExecutionTimeLimit>PT1M</ExecutionTimeLimit>",
        "    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>",
        "    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>",
        "    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>",
        "  </Settings>",
        '  <Actions Context="Author">',
        "    <Exec>",
        f"      <Command>{python_exe}</Command>",
        f'      <Arguments>"{_CHECK_SCRIPT}"</Arguments>',
        "    </Exec>",
        "  </Actions>",
        "</Task>",
    ])

    tmp      = os.environ.get("TEMP", r"C:\Windows\Temp")
    xml_path = os.path.join(tmp, f"parental_logon_{username}.xml")
    with open(xml_path, "w", encoding="utf-16") as fh:
        fh.write(task_xml)

    subprocess.run(
        ["schtasks", "/create", "/tn", task_name, "/xml", xml_path, "/f"],
        check=True, capture_output=True,
    )
    log.info("created logon enforcement task for %s", username)


class WindowsBackend:
    def setup_user(self, username: str) -> None:
        _write_check_script()
        _create_logon_task(username)

    def enable_user(self, username: str) -> None:
        log.info("enabling user %s", username)
        subprocess.run(["net", "user", username, "/active:yes"], check=True, capture_output=True)
        denied_marker = _DENIED_DIR / username
        if denied_marker.exists():
            denied_marker.unlink()

    def disable_user(self, username: str) -> None:
        log.info("disabling user %s", username)
        subprocess.run(["net", "user", username, "/active:yes"], check=True, capture_output=True)
        _ensure_dirs()
        (_DENIED_DIR / username).touch()

    def force_logoff(self, username: str) -> None:
        log.info("logging off sessions for %s", username)

        # Trigger the per-user logon task which runs logon_check.py inside the
        # user's own interactive session: shows the timed message then calls
        # ExitWindowsEx. Same path as logon-time enforcement.
        task_name = _logon_task_name(username)
        result = subprocess.run(
            ["schtasks", "/run", "/tn", task_name],
            capture_output=True,
        )
        if result.returncode == 0:
            log.info("triggered logon-check task for %s", username)
            return

        # Fallback if the task trigger fails (user not interactively logged in)
        log.debug("task trigger failed (exit %d), falling back to direct logoff", result.returncode)
        try:
            quser = subprocess.run(["quser", username], capture_output=True, text=True)
            if quser.returncode == 0:
                for line in quser.stdout.splitlines()[1:]:
                    parts = line.split()
                    session_id = next((p for p in parts if p.isdigit()), None)
                    if session_id:
                        subprocess.run(["logoff", session_id], check=False, capture_output=True)
                return
        except FileNotFoundError:
            log.debug("quser not found, falling back to taskkill")

        subprocess.run(
            ["taskkill", "/F", "/FI", f"USERNAME eq {username}"],
            capture_output=True, check=False,
        )
