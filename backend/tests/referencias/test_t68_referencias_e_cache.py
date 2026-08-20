"""T-68 — endpoints de referência, BOLA em colaboradores, cache TTL local."""

from app.models import PerfilUsuario
from app.security.jwt import create_access_token
from tests.builders import CargoBuilder, CentroCustoBuilder, ColaboradorBuilder, DepartamentoBuilder, UsuarioBuilder


def _token(db_session, perfil, colaborador_id=None):
    usuario = UsuarioBuilder(perfil=perfil, colaborador_id=colaborador_id).build(db_session)
    db_session.commit()
    return usuario, create_access_token(usuario.id, usuario.perfil.value)[0]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_referencias_cargos_requer_auth(client):
    assert client.get("/referencias/cargos").status_code == 401


def test_referencias_cargos_lista(client, db_session):
    CargoBuilder(nome="Analista Júnior").build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.get("/referencias/cargos", headers=_headers(token))
    assert resposta.status_code == 200
    assert any(c["nome"] == "Analista Júnior" for c in resposta.json())


def test_referencias_departamentos_lista(client, db_session):
    DepartamentoBuilder(nome="Operações Centrais").build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.get("/referencias/departamentos", headers=_headers(token))
    assert resposta.status_code == 200
    assert any(d["nome"] == "Operações Centrais" for d in resposta.json())


def test_referencias_centros_custo_lista(client, db_session):
    CentroCustoBuilder(nome="CC Testes").build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.get("/referencias/centros-custo", headers=_headers(token))
    assert resposta.status_code == 200
    assert any(c["nome"] == "CC Testes" for c in resposta.json())


def test_e2e09_referencias_estruturas_lista(client, db_session):
    """spec.md RC-48/T-86 — catálogo de estruturas para o seletor de destino
    de ALTERACAO_ESTRUTURA na Nova solicitação."""
    from app.models import EstruturaOrganizacional

    db_session.add(EstruturaOrganizacional(codigo="EST-T86", nome="Estrutura de Teste T86", ativo=True, nivel=1))
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.get("/referencias/estruturas", headers=_headers(token))
    assert resposta.status_code == 200
    assert any(e["nome"] == "Estrutura de Teste T86" for e in resposta.json())


def test_cache_evita_segunda_consulta_dentro_do_ttl(client, db_session, monkeypatch):
    from app.repositories import referencia_repository

    CargoBuilder(nome="Cargo Cacheável").build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    chamadas = {"n": 0}
    original = referencia_repository.listar_cargos

    def _contar(session):
        chamadas["n"] += 1
        return original(session)

    monkeypatch.setattr(referencia_repository, "listar_cargos", _contar)

    client.get("/referencias/cargos", headers=_headers(token))
    client.get("/referencias/cargos", headers=_headers(token))
    client.get("/referencias/cargos", headers=_headers(token))

    assert chamadas["n"] == 1


def test_cache_nao_serve_dado_de_outra_tabela_apos_invalidar(db_session):
    from app.config import settings
    from app.services import reference_cache

    valor = reference_cache.obter_ou_calcular("teste_ttl", settings.reference_cache_ttl_seconds, lambda: "primeiro")
    assert valor == "primeiro"

    reference_cache.invalidar("teste_ttl")
    valor2 = reference_cache.obter_ou_calcular("teste_ttl", settings.reference_cache_ttl_seconds, lambda: "segundo")
    assert valor2 == "segundo"


def test_colaboradores_lideranca_ve_so_subarvore(client, db_session):
    diretor = ColaboradorBuilder(gestor_id=None).build(db_session)
    subordinado = ColaboradorBuilder(gestor_id=diretor.id).build(db_session)
    outsider = ColaboradorBuilder(gestor_id=None).build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.LIDERANCA, colaborador_id=diretor.id)

    resposta = client.get("/colaboradores", headers=_headers(token))
    ids = {c["id"] for c in resposta.json()}
    assert subordinado.id in ids
    assert diretor.id in ids
    assert outsider.id not in ids


def test_colaboradores_admin_ve_todos(client, db_session):
    ColaboradorBuilder().build(db_session)
    ColaboradorBuilder().build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.get("/colaboradores", headers=_headers(token))
    assert len(resposta.json()) >= 2


def test_e2e10_colaboradores_busca_por_nome_ou_matricula(client, db_session):
    """spec.md RC-49/T-86 — autocomplete da Nova solicitação: o backend
    filtra por nome/matrícula, sempre depois do BOLA (RC-16)."""
    ColaboradorBuilder(matricula="M888888", nome="Priscila Tanaka").build(db_session)
    ColaboradorBuilder(matricula="M888889", nome="Outro Qualquer").build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    por_nome = client.get("/colaboradores", params={"busca": "tanaka"}, headers=_headers(token))
    assert por_nome.status_code == 200
    nomes = {c["nome"] for c in por_nome.json()}
    assert nomes == {"Priscila Tanaka"}

    por_matricula = client.get("/colaboradores", params={"busca": "M888888"}, headers=_headers(token))
    assert {c["nome"] for c in por_matricula.json()} == {"Priscila Tanaka"}


def test_colaboradores_busca_respeita_bola_de_lideranca(client, db_session):
    diretor = ColaboradorBuilder(gestor_id=None, nome="Diretor Busca").build(db_session)
    subordinado = ColaboradorBuilder(gestor_id=diretor.id, nome="Busca Subordinado").build(db_session)
    outsider = ColaboradorBuilder(gestor_id=None, nome="Busca Outsider").build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.LIDERANCA, colaborador_id=diretor.id)

    resposta = client.get("/colaboradores", params={"busca": "Busca"}, headers=_headers(token))
    nomes = {c["nome"] for c in resposta.json()}
    assert nomes == {"Diretor Busca", "Busca Subordinado"}
    assert "Busca Outsider" not in nomes
