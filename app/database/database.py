import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

Base = declarative_base()

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.resolved_database_url
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=_get_engine()
        )
    return _SessionLocal


# Provide module-level `engine` and `SessionLocal` as lazy properties
# so that tests can override the engine before first use.
class _EngineProxy:
    def __getattr__(self, name):
        return getattr(_get_engine(), name)

    def __call__(self, *args, **kwargs):
        return _get_engine()(*args, **kwargs)


engine = _get_engine  # callable, used in create_all

SessionLocal = _get_session_factory


def get_db():
    db = _get_session_factory()()
    try:
        yield db
    finally:
        db.close()
