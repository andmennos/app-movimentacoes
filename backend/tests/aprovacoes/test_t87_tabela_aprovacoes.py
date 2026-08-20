"""T-87 — `/aprovacoes/pendentes` como tabela pesquisável/ordenável
(spec.md RC-51). E2E-12, E2E-13, E2E-14."""

from datetime import datetime

from app.models import EstadoAprovacao, PerfilUsuario
from app.security.jwt import create_access_token
from tests.builders import (
    ColaboradorBuilder,
    DepartamentoBuilder,
    MovimentacaoBuilder,
    UsuarioBuilder,
    criar_aprovacoes_exigidas,
)


def _token(db_session, perfil, colaborador_id=None):
    usuario = UsuarioBuilder(perfil=perfil, colaborador_id=colaborador_id).build(db_session)
    db_session.commit()
    return usuario, create_access_token(usuario.id, usuario.perfil.value)[0]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _criar_transferencia(client, token, colaborador_id, dep_destino_id):
    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": colaborador_id, "departamentoDestinoId": dep_destino_id},
        headers=_headers(token),
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["id"]


def test_e2e12_busca_por_id_e_por_colaborador(client, db_session):
    colaborador1 = ColaboradorBuilder(matricula="M666601", nome="Fabiana Ramos").build(db_session)
    colaborador2 = ColaboradorBuilder(matricula="M666602", nome="Outro Nome").build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _admin, token = _token(db_session, PerfilUsuario.ADMIN)

    mov1 = _criar_transferencia(client, token, colaborador1.id, dep_destino.id)
    _criar_transferencia(client, token, colaborador2.id, dep_destino.id)

    por_id = client.get("/aprovacoes/pendentes", params={"busca": str(mov1)}, headers=_headers(token)).json()
    assert all(item["movimentacaoId"] == mov1 for item in por_id)
    assert len(por_id) > 0

    por_nome = client.get("/aprovacoes/pendentes", params={"busca": "ramos"}, headers=_headers(token)).json()
    assert all(item["movimentacaoId"] == mov1 for item in por_nome)
    assert len(por_nome) > 0

    por_matricula = client.get(
        "/aprovacoes/pendentes", params={"busca": "M666601"}, headers=_headers(token)
    ).json()
    assert all(item["movimentacaoId"] == mov1 for item in por_matricula)


def test_e2e13_ordenacao_padrao_data_desc_e_whitelist(client, db_session):
    """Constrói as movimentações direto via builder (não pela API) para
    controlar `data_solicitacao` com precisão — evita flakiness de duas
    chamadas HTTP sequenciais poderem cair no mesmo microssegundo."""
    mov_antiga = MovimentacaoBuilder(data_solicitacao=datetime(2026, 1, 1, 9, 0, 0)).build(db_session)
    mov_recente = MovimentacaoBuilder(data_solicitacao=datetime(2026, 6, 1, 9, 0, 0)).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov_antiga, estado=EstadoAprovacao.PENDENTE)
    criar_aprovacoes_exigidas(db_session, mov_recente, estado=EstadoAprovacao.PENDENTE)
    db_session.commit()
    _admin, token = _token(db_session, PerfilUsuario.ADMIN)

    padrao = client.get("/aprovacoes/pendentes", headers=_headers(token)).json()
    ids_padrao = [item["movimentacaoId"] for item in padrao]
    assert ids_padrao.index(mov_recente.id) < ids_padrao.index(mov_antiga.id)

    asc = client.get(
        "/aprovacoes/pendentes", params={"ordenarPor": "id", "direcao": "asc"}, headers=_headers(token)
    ).json()
    ids_asc = [item["movimentacaoId"] for item in asc]
    assert ids_asc.index(mov_antiga.id) < ids_asc.index(mov_recente.id)

    invalida = client.get(
        "/aprovacoes/pendentes", params={"ordenarPor": "campoLixo"}, headers=_headers(token)
    )
    assert invalida.status_code == 400
    assert invalida.json()["erro"]["codigo"] == "PARAMETRO_INVALIDO"


def test_e2e14_resposta_traz_solicitante_origem_destino_setor(client, db_session):
    dep_origem = DepartamentoBuilder(nome="Setor Origem T87").build(db_session)
    dep_destino = DepartamentoBuilder(nome="Setor Destino T87").build(db_session)
    colaborador = ColaboradorBuilder(departamento_id=dep_origem.id).build(db_session)
    db_session.commit()
    usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    mov_id = _criar_transferencia(client, token, colaborador.id, dep_destino.id)

    resposta = client.get("/aprovacoes/pendentes", headers=_headers(token)).json()
    item = next(i for i in resposta if i["movimentacaoId"] == mov_id)

    assert item["solicitante"]["username"] == usuario.username
    assert item["origem"] == dep_origem.nome
    assert item["destino"] == dep_destino.nome
    assert item["setor"] == dep_origem.nome
