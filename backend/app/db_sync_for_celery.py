"""Sync database helper for Celery tasks (avoid asyncpg event loop conflicts)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings

_engine = None

def get_engine():
    global _engine
    if _engine is not None:
        return _engine
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    _engine = create_engine(sync_url, echo=False, pool_pre_ping=True)
    return _engine

def get_session():
    return sessionmaker(bind=get_engine())()