import argparse
import logging
import os
import sys
import time
from pathlib import Path

from parental_controls_agent.client import fetch_access
from parental_controls_agent.config import load_config
from parental_controls_agent.enforcer import Enforcer
from parental_controls_agent.platform import get_backend

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

if sys.platform == "win32":
    _log_dir = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "ParentalControls"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _fh = logging.FileHandler(_log_dir / "agent.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(_fh)


def main() -> None:
    parser = argparse.ArgumentParser(description="Parental controls polling agent")
    if sys.platform == "win32":
        default_paths = r".\agent.toml, %PROGRAMDATA%\ParentalControls\agent.toml"
    else:
        default_paths = "./agent.toml, ~/.config/parental-controls/agent.toml, /etc/parental-controls/agent.toml"
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help=f"Path to agent.toml (default: search {default_paths})",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    backend = get_backend()

    for os_username in config.children.values():
        try:
            backend.setup_user(os_username)
        except Exception as e:
            log.warning("setup_user failed for %s: %s", os_username, e)

    enforcer = Enforcer(children=config.children, backend=backend)

    log.info(
        "agent started — server: %s, poll interval: %ds, children: %s",
        config.server_url,
        config.poll_interval,
        config.children,
    )

    while True:
        try:
            response = fetch_access(config.server_url)
            enforcer.apply(response)
        except Exception as e:
            log.warning("poll failed: %s", e)
        time.sleep(config.poll_interval)


if __name__ == "__main__":
    main()
