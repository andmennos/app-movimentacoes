from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _aplicar_pragmas(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def criar_engine(database_url: str, **kwargs) -> Engine:
    engine = create_engine(database_url, connect_args={"check_same_thread": False}, **kwargs)
    event.listen(engine, "connect", _aplicar_pragmas)
    return engine


engine = criar_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        # INV-04: exceção não tratada aborta a transação — nenhuma escrita parcial.
        db.rollback()
        raise
    finally:
        db.close()
