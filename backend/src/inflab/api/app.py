"""FastAPI application factory."""

from fastapi import FastAPI

from inflab import __version__
from inflab.api.errors import install_exception_handlers
from inflab.api.health import router as health_router
from inflab.api.middleware import RequestIDMiddleware
from inflab.api.v1 import router as v1_router
from inflab.config import AppSettings, get_settings
from inflab.db import configure_database, create_schema
from inflab.logging import configure_logging


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Create the backend API application."""

    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)
    configure_database(app_settings.database.url)
    if app_settings.database.create_schema_on_startup:
        create_schema()

    application = FastAPI(
        title=app_settings.app_name,
        version=__version__,
        summary="InferenceLab / ModelBench Agent backend control plane",
    )
    application.state.settings = app_settings

    application.add_middleware(RequestIDMiddleware)
    install_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(v1_router)

    return application


app = create_app()
