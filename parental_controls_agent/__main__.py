import argparse
import logging
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Parental controls polling agent")
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to agent.toml (default: search ./agent.toml, ~/.config/parental-controls/agent.toml, /etc/parental-controls/agent.toml)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    backend = get_backend()
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
