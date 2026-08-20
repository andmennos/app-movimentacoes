"""T-67 — hardening e rate limiting (spec.md §12.4/§12.5)."""

from app.config import settings


def test_burst_acima_de_100_leituras_recebe_429(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_read_per_minute", 5)

    respostas = [client.get("/movimentacoes") for _ in range(6)]

    codigos = [r.status_code for r in respostas]
    assert codigos[:5] == [401, 401, 401, 401, 401]  # sem token, mas contam para o limite
    assert codigos[5] == 429
    assert "retry-after" in respostas[5].headers
    assert respostas[5].json()["erro"]["codigo"] == "RATE_LIMIT_EXCEDIDO"


def test_burst_acima_de_30_escritas_recebe_429(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_write_per_minute", 3)

    respostas = [
        client.post("/movimentacoes", json={"tipo": "TRANSFERENCIA", "colaboradorId": 1, "departamentoDestinoId": 1})
        for _ in range(4)
    ]

    codigos = [r.status_code for r in respostas]
    assert codigos[:3] == [401, 401, 401]
    assert codigos[3] == 429


def test_rota_normal_dentro_do_limite_passa(client):
    for _ in range(5):
        resposta = client.get("/movimentacoes")
        assert resposta.status_code == 401  # sem token, mas não é 429


def test_login_nao_conta_no_rate_limiter_geral(client, monkeypatch):
    """/auth/login tem seu próprio lockout (spec §12.3), separado do rate
    limiter geral — um limite geral de escrita artificialmente baixo (1)
    não deve bloquear a 2ª tentativa de login. Só duas tentativas: a
    partir da 3ª, o lockout de força bruta (T-58) já bloquearia por conta
    própria, o que testaria outra coisa."""
    monkeypatch.setattr(settings, "rate_limit_write_per_minute", 1)

    respostas = [
        client.post("/auth/login", json={"username": "inexistente", "password": "x"}) for _ in range(2)
    ]
    assert all(r.status_code == 401 for r in respostas)
    assert all(r.json()["erro"]["codigo"] == "CREDENCIAIS_INVALIDAS" for r in respostas)


def test_payload_extra_e_rejeitado_422(client, db_session):
    """T-78/SEC-02 — com JWT válido, um campo extra deve reprovar com
    EXATAMENTE 422 (RC-40, `extra="forbid"`). `401 ou 422` não prova nada
    sobre validação do payload — por isso o teste autentica de verdade."""
    from app.models import PerfilUsuario
    from app.security.jwt import create_access_token
    from tests.builders import UsuarioBuilder

    usuario = UsuarioBuilder(perfil=PerfilUsuario.ADMIN).build(db_session)
    db_session.commit()
    token, _ = create_access_token(usuario.id, usuario.perfil.value)

    resposta = client.post(
        "/movimentacoes",
        json={
            "tipo": "TRANSFERENCIA",
            "colaboradorId": 1,
            "departamentoDestinoId": 1,
            "campoNaoEsperado": "x",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resposta.status_code == 422


def test_sec02_validar_com_campo_extra_autenticado_recebe_exatamente_422(client, db_session):
    """T-78/SEC-02/RC-40 — mesmo requisito, especificamente em `POST
    /validar` (o schema historicamente mais simples, sem `extra="forbid"`
    até esta correção)."""
    from app.models import PerfilUsuario
    from app.security.jwt import create_access_token
    from tests.builders import UsuarioBuilder

    usuario = UsuarioBuilder(perfil=PerfilUsuario.ADMIN).build(db_session)
    db_session.commit()
    token, _ = create_access_token(usuario.id, usuario.perfil.value)

    resposta = client.post(
        "/validar",
        json={"movimentacaoId": 1, "campoNaoEsperado": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resposta.status_code == 422


def test_sec02_validar_sem_campo_extra_nao_recebe_422_por_isso(client, db_session):
    """Contraprova: o mesmo payload sem o campo extra não deve ser
    rejeitado por validação (pode dar 404 se a movimentação não existir —
    o que confirma que o 422 do teste anterior era mesmo por causa do
    campo extra, não de outro motivo)."""
    from app.models import PerfilUsuario
    from app.security.jwt import create_access_token
    from tests.builders import UsuarioBuilder

    usuario = UsuarioBuilder(perfil=PerfilUsuario.ADMIN).build(db_session)
    db_session.commit()
    token, _ = create_access_token(usuario.id, usuario.perfil.value)

    resposta = client.post(
        "/validar",
        json={"movimentacaoId": 999999},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resposta.status_code != 422


def test_corpo_muito_grande_recebe_413(client, monkeypatch):
    monkeypatch.setattr(settings, "max_body_bytes", 10)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": 1, "departamentoDestinoId": 1},
    )
    assert resposta.status_code == 413
    assert resposta.json()["erro"]["codigo"] == "PAYLOAD_MUITO_GRANDE"


def test_sec03_corpo_muito_grande_e_rejeitado_mesmo_sem_content_length_confiavel(client, monkeypatch):
    """T-78/SEC-03/RC-40 — `Content-Length` pode ser só um fast-fail; a
    defesa real precisa contar os bytes efetivamente recebidos. Envia o
    corpo via um gerador (transferência sem `Content-Length` — confirmado
    abaixo que o header realmente não vai) para provar que o limite ainda
    é aplicado sem depender dele."""
    monkeypatch.setattr(settings, "max_body_bytes", 10)

    def _corpo_sem_content_length():
        yield b"x" * 1000

    resposta = client.post("/movimentacoes", content=_corpo_sem_content_length())

    assert resposta.status_code == 413
    assert resposta.json()["erro"]["codigo"] == "PAYLOAD_MUITO_GRANDE"


def test_sec03_content_length_baixo_nao_basta_para_escapar_do_limite(client, monkeypatch):
    """Reforço do mesmo requisito: mesmo se um cliente mal-intencionado
    anunciasse um `Content-Length` pequeno (abaixo do fast-fail) mas depois
    enviasse mais bytes que isso, o corpo real ainda seria contado e
    rejeitado — não só o valor anunciado no header."""
    monkeypatch.setattr(settings, "max_body_bytes", 10)

    resposta = client.post(
        "/movimentacoes",
        content=b"x" * 1000,
        headers={"content-length": "5"},
    )

    assert resposta.status_code == 413
    assert resposta.json()["erro"]["codigo"] == "PAYLOAD_MUITO_GRANDE"


def test_headers_de_seguranca_presentes(client):
    resposta = client.get("/movimentacoes")
    assert resposta.headers["x-content-type-options"] == "nosniff"
    assert resposta.headers["x-frame-options"] == "DENY"
    assert resposta.headers["cache-control"] == "no-store"


def test_500_generico_sem_stack_trace(db_session, monkeypatch):
    """Usa um TestClient próprio com `raise_server_exceptions=False`: o
    fixture `client` compartilhado re-levanta exceções não tratadas por
    conveniência de debug (comportamento só do TestClient) — em produção,
    `ServerErrorMiddleware` já converte isso em 500 genérico normalmente;
    este teste observa exatamente essa resposta HTTP real."""
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app
    from app.models import PerfilUsuario
    from app.security.jwt import create_access_token
    from tests.builders import UsuarioBuilder

    usuario = UsuarioBuilder(perfil=PerfilUsuario.ADMIN).build(db_session)
    db_session.commit()
    token, _ = create_access_token(usuario.id, usuario.perfil.value)

    def _explode(*args, **kwargs):
        raise RuntimeError("detalhe interno sensível que não deve vazar")

    import app.repositories.movimentacao_repository as repo

    monkeypatch.setattr(repo, "listar", _explode)

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app, raise_server_exceptions=False) as isolado:
            resposta = isolado.get("/movimentacoes", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.clear()

    assert resposta.status_code == 500
    corpo = resposta.json()
    assert corpo["erro"]["codigo"] == "ERRO_INTERNO"
    assert "detalhe interno sensível" not in resposta.text
    assert "RuntimeError" not in resposta.text
