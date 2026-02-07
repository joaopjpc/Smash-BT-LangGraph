"""Helpers de banco de dados (SQLAlchemy)."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()

_ENGINE = None


def get_engine():
    """Retorna engine singleton baseada em DATABASE_URL."""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL não definida.")

    _ENGINE = create_engine(database_url, pool_pre_ping=True, future=True)
    return _ENGINE


@contextmanager
def get_session() -> Iterator[Session]:
    """Context manager para sessão do banco. Criação lazy do SessionLocal."""
    engine = get_engine()
    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        future=True,
    )
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
