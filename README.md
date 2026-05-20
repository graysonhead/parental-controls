# parental-controls

A self-hosted parental control system. A web server tracks children, time windows, and chores. Agents run on the kids' machines and enforce access by enabling/disabling local OS accounts based on the server's decisions.

## How it works

- **Server** — FastAPI web app. Parents log in with a PIN to manage time windows and mark chores complete.
- **Agent** — Polls the server every 30 seconds. If a child's access is revoked it disables their OS account and forces a logoff; when access is restored it re-enables it.

## Server

### NixOS (self-hosting)

Add the flake input and enable the module:

```nix
inputs.parental-controls.url = "github:graysonhead/parental-controls";

services.parental-controls = {
  enable = true;
  host = "0.0.0.0";
  port = 8000;
  databasePath = "/var/lib/parental-controls/db.sqlite";
  # Set secrets via environmentFile in production:
  # environmentFile = "/run/secrets/parental-controls.env";
  # SECRET_KEY=<random string>
  # ADMIN_PIN=<your PIN>
};
```

## Agent — Windows install

**Requirements:** Windows 10/11, administrator account, internet access for the first run.

1. Clone or download this repo to the machine.
2. Open **PowerShell as Administrator**.
3. Run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& "C:\path\to\parental-controls\install-windows.ps1"
```

The script will:
- Install **Python 3.13** system-wide via `winget` (skipped if already present)
- Install the `parental-controls-agent` package
- Prompt for the server URL and each child's details (web UI display name → Windows username)
- Write the config to `C:\ProgramData\ParentalControls\agent.toml`
- Register a **Task Scheduler** task (`ParentalControlsAgent`) that runs at every boot under the `SYSTEM` account

### Config file

`C:\ProgramData\ParentalControls\agent.toml`:

```toml
server_url = "https://parental-controls.graysonhead.net"
poll_interval = 30

[children]
"Alice" = "alice_windows_username"
"Bob"   = "bob_windows_username"
```

Display names must match exactly what is shown in the web UI. To add or remove children after install, edit this file and restart the task:

```powershell
schtasks /end /tn ParentalControlsAgent
schtasks /run /tn ParentalControlsAgent
```

### Logs

`C:\ProgramData\ParentalControls\agent.log`

### Uninstall

```powershell
schtasks /delete /tn ParentalControlsAgent /f
Remove-Item -Recurse "C:\ProgramData\ParentalControls"
```

## Agent — NixOS install

```nix
inputs.parental-controls.url = "github:graysonhead/parental-controls";

services.parental-controls-agent = {
  enable = true;
  serverUrl = "https://parental-controls.graysonhead.net";
  children = {
    "Alice" = "alice";
    "Bob"   = "bob";
  };
};
```

The agent runs as root (required for `usermod`/`loginctl`).
