import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AgentConfig:
    server_url: str
    poll_interval: int
    children: dict[str, str]  # child_name -> OS username


def _default_search_paths() -> list[Path]:
    paths = [Path("agent.toml")]
    if sys.platform == "win32":
        programdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        appdata = os.environ.get("APPDATA", "")
        paths.append(Path(programdata) / "ParentalControls" / "agent.toml")
        if appdata:
            paths.append(Path(appdata) / "ParentalControls" / "agent.toml")
    else:
        paths.append(Path.home() / ".config" / "parental-controls" / "agent.toml")
        paths.append(Path("/etc/parental-controls/agent.toml"))
    return paths


def load_config(path: Path | None = None) -> AgentConfig:
    search_paths = _default_search_paths()
    candidates = [path] if path is not None else search_paths

    for candidate in candidates:
        if candidate.exists():
            data = tomllib.loads(candidate.read_text(encoding="utf-8-sig"))
            return AgentConfig(
                server_url=data["server_url"].rstrip("/"),
                poll_interval=int(data.get("poll_interval", 30)),
                children={k: v for k, v in data.get("children", {}).items()},
            )

    raise FileNotFoundError(
        "No agent.toml found. Searched: " + ", ".join(str(p) for p in candidates)
    )
