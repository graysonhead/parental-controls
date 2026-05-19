from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlmodel import Session, create_engine

from parental_controls.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

_ALEMBIC_INI = Path(__file__).parent.parent / "alembic.ini"


def run_migrations() -> None:
    cfg = Config(str(_ALEMBIC_INI))
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")


def get_session():
    with Session(engine) as session:
        yield session
