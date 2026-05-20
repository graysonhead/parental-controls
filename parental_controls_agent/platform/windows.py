import logging
import os
import re
import subprocess

log = logging.getLogger(__name__)

_DENY_RIGHT = "SeDenyInteractiveLogonRight"
_TMP = os.environ.get("TEMP", r"C:\Windows\Temp")
_CFG = os.path.join(_TMP, "parental_controls_secedit.cfg")
_DB  = os.path.join(_TMP, "parental_controls_secedit.sdb")


def _get_sid(username: str) -> str:
    result = subprocess.run(
        [
            "powershell", "-NoProfile", "-Command",
            f'(New-Object Security.Principal.NTAccount("{username}")).Translate([Security.Principal.SecurityIdentifier]).Value',
        ],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _set_deny_logon(username: str, deny: bool) -> None:
    """Add or remove SeDenyInteractiveLogonRight for username via secedit.

    This keeps the account active and visible on the Windows login screen
    but prevents interactive login when deny=True.
    """
    sid = _get_sid(username)
    sid_entry = f"*{sid}"  # secedit uses *S-1-x-... format

    # Export current effective policy
    subprocess.run(
        ["secedit", "/export", "/cfg", _CFG, "/quiet"],
        check=True, capture_output=True,
    )

    # secedit exports UTF-16 LE with BOM
    with open(_CFG, encoding="utf-16") as fh:
        content = fh.read()

    pattern = re.compile(
        rf"^({re.escape(_DENY_RIGHT)}\s*=\s*)(.*)$", re.MULTILINE
    )
    match = pattern.search(content)

    if deny:
        if match:
            entries = [e.strip() for e in match.group(2).split(",") if e.strip()]
            if sid_entry not in entries:
                entries.append(sid_entry)
            content = pattern.sub(
                lambda _: f"{_DENY_RIGHT} = {','.join(entries)}", content
            )
        else:
            # Right not present at all — insert into [Privilege Rights]
            content = content.replace(
                "[Privilege Rights]",
                f"[Privilege Rights]\n{_DENY_RIGHT} = {sid_entry}",
            )
    else:
        if match:
            entries = [
                e.strip() for e in match.group(2).split(",")
                if e.strip() and sid not in e
            ]
            content = pattern.sub(
                lambda _: f"{_DENY_RIGHT} = {','.join(entries)}", content
            )
        # If right isn't present, user already has logon access — nothing to do

    with open(_CFG, "w", encoding="utf-16") as fh:
        fh.write(content)

    subprocess.run(
        [
            "secedit", "/configure",
            "/db", _DB,
            "/cfg", _CFG,
            "/areas", "USER_RIGHTS",
            "/quiet",
        ],
        check=True, capture_output=True,
    )


class WindowsBackend:
    def enable_user(self, username: str) -> None:
        log.info("enabling user %s (removing deny-logon right)", username)
        # Ensure account is active in case it was previously disabled the old way
        subprocess.run(["net", "user", username, "/active:yes"], check=True, capture_output=True)
        _set_deny_logon(username, deny=False)

    def disable_user(self, username: str) -> None:
        log.info("disabling user %s (adding deny-logon right)", username)
        # Keep account active so it stays visible on the login screen;
        # SeDenyInteractiveLogonRight blocks actual login.
        subprocess.run(["net", "user", username, "/active:yes"], check=True, capture_output=True)
        _set_deny_logon(username, deny=True)

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
