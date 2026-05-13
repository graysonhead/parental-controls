import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AgentConfig:
    server_url: str
    poll_interval: int
    children: dict[str, str]  # child_name -> OS username


_SEARCH_PATHS = [
    Path("agent.toml"),
    Path.home() / ".config" / "parental-controls" / "agent.toml",
    Path("/etc/parental-controls/agent.toml"),
]


def load_config(path: Path | None = None) -> AgentConfig:
    if path is not None:
        candidates = [path]
    else:
        candidates = _SEARCH_PATHS

    for candidate in candidates:
        if candidate.exists():
            data = tomllib.loads(candidate.read_text())
            return AgentConfig(
                server_url=data["server_url"].rstrip("/"),
                poll_interval=int(data.get("poll_interval", 30)),
                children={k: v for k, v in data.get("children", {}).items()},
            )

    raise FileNotFoundError(
        "No agent.toml found. Searched: " + ", ".join(str(p) for p in _SEARCH_PATHS)
    )
