"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from inflab import __version__
from inflab.api.errors import install_exception_handlers
from inflab.api.health import router as health_router
from inflab.api.middleware import RequestIDMiddleware
from inflab.api.v1 import router as v1_router
from inflab.config import AppSettings, get_settings
from inflab.db import configure_database, create_schema
from inflab.db.session import get_session
from inflab.demo_data import seed_demo_data
from inflab.logging import configure_logging


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Create the backend API application."""

    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)
    configure_database(app_settings.database.url)
    if app_settings.database.create_schema_on_startup:
        create_schema()
    if app_settings.seed_demo_data:
        session_generator = get_session()
        session = next(session_generator)
        try:
            seed_demo_data(session)
        finally:
            session_generator.close()

    application = FastAPI(
        title=app_settings.app_name,
        version=__version__,
        summary="InferenceLab / ModelBench Agent backend control plane",
    )
    application.state.settings = app_settings

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestIDMiddleware)
    install_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(v1_router)

    return application


app = create_app()
