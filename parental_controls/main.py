from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from parental_controls.api import access, children, chores, completions, time_windows
from parental_controls.config import settings
from parental_controls.database import create_db_and_tables
from parental_controls.web import auth, child, parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Parental Controls", lifespan=lifespan)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        max_age=settings.session_max_age,
    )

    app.mount("/static", StaticFiles(directory="static"), name="static")

    # API routers
    app.include_router(access.router)
    app.include_router(children.router)
    app.include_router(chores.router)
    app.include_router(completions.router)
    app.include_router(time_windows.router)

    # Web UI routers
    app.include_router(auth.router)
    app.include_router(child.router)
    app.include_router(parent.router)

    return app


app = create_app()


def run_server() -> None:
    import uvicorn
    uvicorn.run(
        "parental_controls.main:app",
        host=settings.host,
        port=settings.port,
    )
