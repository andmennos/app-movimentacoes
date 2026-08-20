"""T-58 — autenticação local JWT + login + lockout (spec.md §2.2/§12,
plan.md §6). AUTH-01..07."""

from datetime import datetime, timedelta, timezone

from app.models import PerfilUsuario
from app.security import permissions
from app.security.jwt import create_access_token
from app.security.passwords import hash_password
from tests.builders import UsuarioBuilder


def _criar_usuario(db_session, username="admin", senha="admin", perfil=PerfilUsuario.ADMIN):
    return UsuarioBuilder(username=username, password_hash=hash_password(senha), perfil=perfil).build(db_session)


def test_auth01_login_admin_recebe_jwt_admin(client, db_session):
    _criar_usuario(db_session, "admin", "admin", PerfilUsuario.ADMIN)
    db_session.commit()

    resposta = client.post("/auth/login", json={"username": "admin", "password": "admin"})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tokenType"] == "bearer"
    assert corpo["expiresIn"] == 1800
    assert corpo["usuario"]["perfil"] == "ADMIN"
    assert corpo["accessToken"]
    assert resposta.headers["cache-control"] == "no-store"


def test_sec04_login_devolve_scopes_efetivos_do_backend(client, db_session):
    """T-77/RC-39 — o Angular não mantém SCOPES_POR_PERFIL próprio; os
    scopes vêm de /auth/login, exatamente os de `permissions.scopes_do_perfil`
    (fonte única) — nem mais, nem menos."""
    _criar_usuario(db_session, "admin", "admin", PerfilUsuario.ADMIN)
    db_session.commit()

    resposta = client.post("/auth/login", json={"username": "admin", "password": "admin"})

    assert resposta.status_code == 200
    scopes_recebidos = set(resposta.json()["usuario"]["scopes"])
    assert scopes_recebidos == set(permissions.scopes_do_perfil("ADMIN"))
    assert "movimentacoes:approve" in scopes_recebidos


def test_sec04_auth_me_devolve_scopes_efetivos_do_backend(client, db_session):
    usuario = _criar_usuario(db_session, "analistaRh", "analistaRh", PerfilUsuario.RH_ANALISTA)
    db_session.commit()
    token, _ = create_access_token(usuario.id, usuario.perfil.value)

    resposta = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 200
    scopes_recebidos = set(resposta.json()["scopes"])
    assert scopes_recebidos == set(permissions.scopes_do_perfil("RH_ANALISTA"))
    assert "movimentacoes:approve" not in scopes_recebidos


def test_auth02_login_analista_rh_recebe_jwt_rh_analista(client, db_session):
    _criar_usuario(db_session, "analistaRh", "analistaRh", PerfilUsuario.RH_ANALISTA)
    db_session.commit()

    resposta = client.post("/auth/login", json={"username": "analistaRh", "password": "analistaRh"})

    assert resposta.status_code == 200
    assert resposta.json()["usuario"]["perfil"] == "RH_ANALISTA"


def test_auth03_senha_errada_nao_autentica(client, db_session):
    _criar_usuario(db_session, "admin", "admin")
    db_session.commit()

    resposta = client.post("/auth/login", json={"username": "admin", "password": "errada"})

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"


def test_login_usuario_inexistente_usa_mesma_resposta_generica(client, db_session):
    resposta = client.post("/auth/login", json={"username": "nao_existe", "password": "qualquer"})

    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS"


def test_auth04_e_auth05_terceira_falha_bloqueia_ip_e_retorna_429(client, db_session):
    _criar_usuario(db_session, "admin", "admin")
    db_session.commit()

    for _ in range(3):
        resposta = client.post("/auth/login", json={"username": "admin", "password": "errada"})
        assert resposta.status_code == 401

    bloqueado = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert bloqueado.status_code == 429
    assert bloqueado.json()["erro"]["codigo"] == "LOGIN_BLOQUEADO"
    assert int(bloqueado.headers["retry-after"]) > 0
    assert bloqueado.headers["cache-control"] == "no-store"


def test_auth06_reset_lockouts_remove_bloqueio(client, db_session, engine, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    _criar_usuario(db_session, "admin", "admin")
    db_session.commit()

    for _ in range(3):
        client.post("/auth/login", json={"username": "admin", "password": "errada"})

    ainda_bloqueado = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert ainda_bloqueado.status_code == 429

    import app.security.reset_lockouts as reset_lockouts_module

    SessionFabrica = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(reset_lockouts_module, "SessionLocal", SessionFabrica)
    reset_lockouts_module.main()

    liberado = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert liberado.status_code == 200


def test_reset_lockouts_nao_apaga_usuarios(db_session, engine):
    from sqlalchemy.orm import sessionmaker

    from app.repositories import security_lockout_repository as lockout_repo
    from app.repositories import usuario_repository

    usuario = _criar_usuario(db_session, "admin", "admin")
    db_session.commit()
    lockout_repo.registrar_falha(db_session, "1.2.3.4", datetime(2026, 8, 19, 10, 0, 0))
    db_session.commit()

    total_removidos = lockout_repo.resetar_todos(db_session)

    assert total_removidos == 1
    assert usuario_repository.buscar_por_id(db_session, usuario.id) is not None


def test_auth07_token_expirado_recebe_401(client, db_session):
    usuario = _criar_usuario(db_session, "admin", "admin")
    db_session.commit()

    from app.config import settings

    token, _ = create_access_token(usuario.id, usuario.perfil.value)
    # Token válido não expirado deve funcionar:
    ok = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200

    import jwt as pyjwt

    claims_expirados = {
        "sub": str(usuario.id),
        "perfil": usuario.perfil.value,
        "scopes": [],
        "exp": int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp()),
    }
    token_expirado = pyjwt.encode(claims_expirados, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    resposta = client.get("/auth/me", headers={"Authorization": f"Bearer {token_expirado}"})
    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "TOKEN_INVALIDO"


def test_auth08_rota_protegida_sem_token_recebe_401(client):
    resposta = client.get("/auth/me")
    assert resposta.status_code == 401


def test_token_com_assinatura_invalida_recebe_401(client, db_session):
    usuario = _criar_usuario(db_session, "admin", "admin")
    db_session.commit()

    import jwt as pyjwt

    claims = {
        "sub": str(usuario.id),
        "perfil": usuario.perfil.value,
        "scopes": [],
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
    }
    token_forjado = pyjwt.encode(claims, "segredo-errado", algorithm="HS256")

    resposta = client.get("/auth/me", headers={"Authorization": f"Bearer {token_forjado}"})
    assert resposta.status_code == 401


def test_usuario_inativo_nao_autentica(client, db_session):
    usuario = _criar_usuario(db_session, "inativo", "senha123")
    usuario.ativo = False
    db_session.commit()

    resposta = client.post("/auth/login", json={"username": "inativo", "password": "senha123"})
    assert resposta.status_code == 401


def test_login_rejeita_campos_extras(client, db_session):
    _criar_usuario(db_session, "admin", "admin")
    db_session.commit()

    resposta = client.post(
        "/auth/login", json={"username": "admin", "password": "admin", "perfil": "ADMIN"}
    )
    assert resposta.status_code == 422
