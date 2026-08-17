import pytest
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registra todas as entidades em Base.metadata
from app.database import Base, criar_engine


@pytest.fixture()
def engine():
    eng = criar_engine("sqlite:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(eng)
    yield eng
    # descarta o banco em memória inteiro; drop_all não é necessário aqui e,
    # com FKs circulares entre colaborador/departamento/centro_custo, exigiria
    # ordenação especial que o SQLite não suporta via ALTER.
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
