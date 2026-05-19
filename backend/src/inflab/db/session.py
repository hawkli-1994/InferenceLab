"""Database engine and session management."""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from inflab.db.models import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def configure_database(database_url: str) -> Engine:
    global _engine, _session_factory

    connect_args = {}
    poolclass = None
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if database_url.endswith(":memory:"):
            poolclass = StaticPool

    kwargs = {"connect_args": connect_args}
    if poolclass is not None:
        kwargs["poolclass"] = poolclass

    _engine = create_engine(database_url, future=True, **kwargs)
    _session_factory = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database has not been configured.")
    return _engine


def create_schema() -> None:
    Base.metadata.create_all(bind=engine())


def drop_schema() -> None:
    Base.metadata.drop_all(bind=engine())


def get_session() -> Generator[Session, None, None]:
    if _session_factory is None:
        raise RuntimeError("Database has not been configured.")
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()
