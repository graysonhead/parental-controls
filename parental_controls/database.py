from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlmodel import Session, create_engine

from parental_controls.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations() -> None:
    cfg = Config()
    cfg.set_main_option("script_location", str(_MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")


def get_session():
    with Session(engine) as session:
        yield session
