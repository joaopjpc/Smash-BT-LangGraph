"""Inicializa o banco criando tabelas."""
from __future__ import annotations

from app.tools.database import Base, get_engine


def main() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    main()
