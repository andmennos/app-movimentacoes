"""T-62 — API de aprovações + correção do bug de histórico intermitente
(spec.md §6/§7.4). APR-06, APR-09, APR-10, APR-11."""

import pytest

from app.models import (
    Aprovacao,
    EstadoAprovacao,
    HistoricoProcessamento,
    PerfilUsuario,
    StatusMovimentacao,
    TipoEventoProcessamento,
)
from app.security.jwt import create_access_token
from app.services import aprovacao_service
from app.services.exceptions import AprovacaoForaDeOrdem, AprovacaoJaDecidida
from tests.builders import CargoBuilder, ColaboradorBuilder, DepartamentoBuilder, UsuarioBuilder


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


def test_apr09_decisao_persiste_aprovacao_e_historico_no_mesmo_fluxo(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _criador, token_criador = _token(db_session, PerfilUsuario.ADMIN)
    mov_id = _criar_transferencia(client, token_criador, colaborador.id, dep_destino.id)

    resposta = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/GESTOR_ORIGEM/decidir",
        json={"decisao": "APROVADA", "justificativa": "ok"},
        headers=_headers(token_criador),
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["estado"] == "APROVADA"

    aprovacao = (
        db_session.query(Aprovacao).filter_by(movimentacao_id=mov_id, tipo="GESTOR_ORIGEM").one()
    )
    assert aprovacao.estado == EstadoAprovacao.APROVADA
    assert aprovacao.data_decisao is not None

    eventos = (
        db_session.query(HistoricoProcessamento)
        .filter_by(movimentacao_id=mov_id, tipo_evento=TipoEventoProcessamento.APROVACAO_CONCLUIDA)
        .all()
    )
    assert len(eventos) == 1
    assert eventos[0].ator_usuario_id == _criador.id


def test_apr10_dupla_decisao_e_rejeitada(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _criador, token = _token(db_session, PerfilUsuario.ADMIN)
    mov_id = _criar_transferencia(client, token, colaborador.id, dep_destino.id)

    primeira = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/GESTOR_ORIGEM/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(token),
    )
    assert primeira.status_code == 200

    segunda = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/GESTOR_ORIGEM/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(token),
    )
    assert segunda.status_code == 409
    assert segunda.json()["erro"]["codigo"] == "APROVACAO_JA_DECIDIDA"


def test_reproduzir_bug_historico_ausente_apos_falha_faz_rollback(db_session, monkeypatch):
    """spec.md §7.4 — reproduz exatamente o cenário relatado: força uma
    falha ao gravar o histórico e prova que a Aprovacao NÃO fica alterada
    (rollback completo, não commit parcial)."""
    from app.repositories import historico_processamento_repository as historico_repo
    from app.models import TipoAprovacao
    from tests.builders import MovimentacaoBuilder, criar_aprovacoes_exigidas

    mov = MovimentacaoBuilder().build(db_session)
    criar_aprovacoes_exigidas(db_session, mov, estado=EstadoAprovacao.PENDENTE)
    db_session.commit()

    usuario = UsuarioBuilder(perfil=PerfilUsuario.ADMIN).build(db_session)
    db_session.commit()

    def _falha(*args, **kwargs):
        raise RuntimeError("falha simulada ao gravar histórico")

    monkeypatch.setattr(historico_repo, "registrar", _falha)

    with pytest.raises(RuntimeError):
        aprovacao_service.decidir(db_session, mov.id, TipoAprovacao.GESTOR_ORIGEM, usuario, "APROVADA", None)
    db_session.rollback()

    aprovacao = (
        db_session.query(Aprovacao).filter_by(movimentacao_id=mov.id, tipo=TipoAprovacao.GESTOR_ORIGEM).one()
    )
    assert aprovacao.estado == EstadoAprovacao.PENDENTE
    assert aprovacao.data_decisao is None

    eventos = db_session.query(HistoricoProcessamento).filter_by(movimentacao_id=mov.id).all()
    assert eventos == []


def test_apr06_promocao_nao_permite_rh_antes_da_hierarquica(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    cargo_destino = CargoBuilder(ordem_progressao=999).build(db_session)
    db_session.commit()
    _criador, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "PROMOCAO", "colaboradorId": colaborador.id, "cargoDestinoId": cargo_destino.id},
        headers=_headers(token),
    )
    mov_id = resposta.json()["id"]

    fora_de_ordem = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/RH/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(token),
    )

    assert fora_de_ordem.status_code == 409
    assert fora_de_ordem.json()["erro"]["codigo"] == "APROVACAO_FORA_DE_ORDEM"


def test_promocao_rh_libera_apos_hierarquica_aprovada(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    cargo_destino = CargoBuilder(ordem_progressao=999).build(db_session)
    db_session.commit()
    _criador, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "PROMOCAO", "colaboradorId": colaborador.id, "cargoDestinoId": cargo_destino.id},
        headers=_headers(token),
    )
    mov_id = resposta.json()["id"]

    client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/GESTOR_ORIGEM/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(token),
    )
    depois = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/RH/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(token),
    )

    assert depois.status_code == 200
    assert depois.json()["estado"] == "APROVADA"
    assert depois.json()["movimentacaoStatus"] == "PENDENTE"


def test_apr02_admin_pode_decidir_a_propria_solicitacao(client, db_session):
    colaborador_admin = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder(gestor_id=colaborador_admin.id).build(db_session)
    db_session.commit()
    admin, token = _token(db_session, PerfilUsuario.ADMIN, colaborador_id=colaborador_admin.id)

    mov_id = _criar_transferencia(client, token, colaborador_admin.id, dep_destino.id)

    resposta = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/GESTOR_ORIGEM/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(token),
    )
    assert resposta.status_code == 200


def test_autoaprovacao_estrutural_nunca_disponivel_para_lideranca(client, db_session):
    """A etapa GESTOR_ORIGEM nem chega a existir quando o solicitante é o
    próprio gestor de origem (spec RC-07) — tentar decidi-la retorna 404,
    não 403: não há aprovação desse tipo para decidir."""
    gestor = ColaboradorBuilder(gestor_id=None).build(db_session)
    subordinado = ColaboradorBuilder(gestor_id=gestor.id, departamento_id=None).build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()

    # gestor de origem do subordinado é o próprio `gestor`
    from app.models import Colaborador

    dep_origem = db_session.get(Colaborador, subordinado.id).departamento
    dep_origem.gestor_id = gestor.id
    db_session.commit()

    _usuario, token = _token(db_session, PerfilUsuario.LIDERANCA, colaborador_id=gestor.id)
    mov_id = _criar_transferencia(client, token, subordinado.id, dep_destino.id)

    resposta = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/GESTOR_ORIGEM/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(token),
    )
    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "APROVACAO_NAO_ENCONTRADA"


def test_aprovacoes_pendentes_lista_apenas_o_que_o_usuario_pode_decidir(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _criador, token_criador = _token(db_session, PerfilUsuario.ADMIN)
    mov_id = _criar_transferencia(client, token_criador, colaborador.id, dep_destino.id)

    _outro, token_rh_analista = _token(db_session, PerfilUsuario.RH_ANALISTA)
    negado = client.get("/aprovacoes/pendentes", headers=_headers(token_rh_analista))
    assert negado.status_code == 403

    admin_ve = client.get("/aprovacoes/pendentes", headers=_headers(token_criador))
    assert admin_ve.status_code == 200
    tipos_da_movimentacao = {
        item["tipo"] for item in admin_ve.json() if item["movimentacaoId"] == mov_id
    }
    assert tipos_da_movimentacao == {"GESTOR_ORIGEM", "GESTOR_DESTINO", "RH"}


def test_aprovacoes_pendentes_some_apos_decidida(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _criador, token = _token(db_session, PerfilUsuario.ADMIN)
    mov_id = _criar_transferencia(client, token, colaborador.id, dep_destino.id)

    client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/GESTOR_ORIGEM/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(token),
    )

    pendentes = client.get("/aprovacoes/pendentes", headers=_headers(token)).json()
    tipos = {item["tipo"] for item in pendentes if item["movimentacaoId"] == mov_id}
    assert "GESTOR_ORIGEM" not in tipos
    assert tipos == {"GESTOR_DESTINO", "RH"}


def test_apr11_seed_nunca_tem_aprovacao_decidida_sem_evento(db_session):
    from app.seed.seed import seed

    seed(db_session)

    decididas = (
        db_session.query(Aprovacao).filter(Aprovacao.estado != EstadoAprovacao.PENDENTE).all()
    )
    assert len(decididas) > 0

    eventos_por_movimentacao = {}
    for evento in db_session.query(HistoricoProcessamento).all():
        eventos_por_movimentacao.setdefault(evento.movimentacao_id, []).append(evento.tipo_evento)

    tipos_de_aprovacao = {
        TipoEventoProcessamento.APROVACAO_CONCLUIDA,
        TipoEventoProcessamento.APROVACAO_REPROVADA,
    }
    for aprovacao in decididas:
        tipos_presentes = set(eventos_por_movimentacao.get(aprovacao.movimentacao_id, []))
        assert tipos_presentes & tipos_de_aprovacao, (
            f"movimentacao {aprovacao.movimentacao_id} tem aprovacao {aprovacao.tipo} decidida "
            "sem nenhum evento de aprovação no histórico"
        )
