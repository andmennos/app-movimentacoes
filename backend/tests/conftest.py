import os

# T-77/RC-39 — JWT_SECRET não tem mais fallback funcional hardcoded em
# app.config.Settings(); a suíte injeta o próprio segredo de teste ANTES de
# qualquer import de app.*, para não depender de um backend/.env local (que
# não existe, por exemplo, num checkout novo/CI). setdefault() permite que
# um .env real (dev local) continue prevalecendo se já estiver no ambiente.
os.environ.setdefault("JWT_SECRET", "segredo-de-teste-nao-usar-em-producao-" + "x" * 32)

import pytest
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registra todas as entidades em Base.metadata
from app.database import Base, criar_engine


@pytest.fixture(autouse=True)
def _rate_limit_limpo():
    """T-67 — o rate limiter geral é estado de módulo (em memória, por
    processo — spec §14.2); sem isso, testes vazariam contagem entre si."""
    from app.security import rate_limit

    rate_limit.resetar()
    yield
    rate_limit.resetar()


@pytest.fixture(autouse=True)
def _reference_cache_limpo():
    from app.services import reference_cache

    reference_cache.invalidar()
    yield
    reference_cache.invalidar()


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


@pytest.fixture()
def admin_headers(client, db_session) -> str:
    """T-59 — a maioria dos testes de API pré-existentes (T-47–T-56) não
    tinha autenticação para se preocupar; em vez de adicionar headers em
    cada chamada, os módulos que precisam de um ator autenticado padrão
    aplicam `pytestmark = pytest.mark.usefixtures("admin_headers")`, que
    autentica um `ADMIN` e injeta o Bearer em todo request do `client`
    compartilhado por aquele módulo."""
    from app.models import PerfilUsuario
    from app.security.jwt import create_access_token
    from tests.builders import UsuarioBuilder

    usuario = UsuarioBuilder(perfil=PerfilUsuario.ADMIN).build(db_session)
    db_session.commit()
    token, _ = create_access_token(usuario.id, usuario.perfil.value)
    client.headers["Authorization"] = f"Bearer {token}"
    return client.headers["Authorization"]
