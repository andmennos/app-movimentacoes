"""T-66 — solicitante, auditoria e `motivoResumo` (spec.md §7/§8). MOT-01..05."""

from datetime import datetime

from app.models import EstadoAprovacao, PerfilUsuario, StatusMovimentacao, TipoMovimentacao
from app.processing import orchestrator
from app.processing.orchestrator import OrchestratorResultado
from app.repositories import job_validacao_repository as job_repo
from app.security.jwt import create_access_token
from tests.builders import (
    CargoBuilder,
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


def _apto_com_job(db_session, mov, estado=EstadoAprovacao.APROVADA):
    criar_aprovacoes_exigidas(db_session, mov, estado=estado)
    mov.status = StatusMovimentacao.PENDENTE
    db_session.commit()
    job_repo.criar(db_session, mov.id, datetime(2026, 1, 1))
    db_session.commit()
    return mov


def test_mot01_aprovada_usa_movimentacao_efetivada(client, db_session):
    dep_origem = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    dep_destino = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)
    mov = _apto_com_job(db_session, mov)
    from app.models import OrigemExecucao

    orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)
    resposta = client.get(f"/movimentacoes/{mov.id}", headers=_headers(token))
    assert resposta.json()["motivoResumo"] == "Movimentação efetivada."


def test_mot02_reprovada_resume_quantidade_real_de_inconsistencias(client, db_session):
    dep_destino = DepartamentoBuilder(ativo=False).build(db_session)
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.TRANSFERENCIA, departamento_destino_id=dep_destino.id).build(
        db_session
    )
    mov = _apto_com_job(db_session, mov)
    from app.models import OrigemExecucao

    orchestrator.processar(db_session, mov.id, OrigemExecucao.AUTOMATICO)

    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)
    resposta = client.get(f"/movimentacoes/{mov.id}", headers=_headers(token))
    corpo = resposta.json()
    assert corpo["status"] == "REPROVADA"
    assert "Validação encontrou" in corpo["motivoResumo"]
    assert "inconsistência" in corpo["motivoResumo"]


def test_mot03_aguardando_lista_aprovacoes_pendentes_reais(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _criador, token = _token(db_session, PerfilUsuario.ADMIN)

    criado = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": colaborador.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(token),
    )
    mov_id = criado.json()["id"]

    resposta = client.get(f"/movimentacoes/{mov_id}", headers=_headers(token))
    corpo = resposta.json()
    assert corpo["status"] == "AGUARDANDO_APROVACAO"
    assert "Aguardando" in corpo["motivoResumo"]
    assert "GESTOR_ORIGEM" in corpo["motivoResumo"]
    assert "GESTOR_DESTINO" in corpo["motivoResumo"]
    assert "RH" in corpo["motivoResumo"]

    decisao = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/GESTOR_ORIGEM/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(token),
    )
    assert decisao.status_code == 200

    resposta2 = client.get(f"/movimentacoes/{mov_id}", headers=_headers(token))
    corpo2 = resposta2.json()
    assert "GESTOR_ORIGEM" not in corpo2["motivoResumo"]
    assert "Aguardando aprovação" in corpo2["motivoResumo"] or "Aguardando 2 aprovações" in corpo2["motivoResumo"]


def test_mot04_bloqueada_identifica_aprovacao_e_ator_real(client, db_session):
    colaborador_admin = ColaboradorBuilder(nome="Alice Uchoa").build(db_session)
    dep_origem = DepartamentoBuilder(gestor_id=colaborador_admin.id).build(db_session)
    colaborador = ColaboradorBuilder(departamento_id=dep_origem.id).build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _admin, token = _token(db_session, PerfilUsuario.ADMIN, colaborador_id=colaborador_admin.id)

    criado = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": colaborador.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(token),
    )
    mov_id = criado.json()["id"]

    client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/GESTOR_ORIGEM/decidir",
        json={"decisao": "REPROVADA", "justificativa": "não faz sentido"},
        headers=_headers(token),
    )

    resposta = client.get(f"/movimentacoes/{mov_id}", headers=_headers(token))
    corpo = resposta.json()
    assert corpo["status"] == "BLOQUEADA"
    assert corpo["motivoResumo"] == "Bloqueada: GESTOR_ORIGEM reprovada por Alice Uchoa."


def test_mot05_pendente_nao_e_confundido_com_aguardando(client, db_session):
    dep_origem = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    dep_destino = DepartamentoBuilder(gestor_id=ColaboradorBuilder().build(db_session).id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)
    _apto_com_job(db_session, mov)  # status PENDENTE, job criado mas não processado

    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)
    resposta = client.get(f"/movimentacoes/{mov.id}", headers=_headers(token))
    corpo = resposta.json()
    assert corpo["status"] == "PENDENTE"
    assert corpo["motivoResumo"] == "Processamento pendente."
    assert "Aguardando" not in corpo["motivoResumo"]


def test_solicitante_aparece_no_detalhe(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    criado = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": colaborador.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(token),
    )
    mov_id = criado.json()["id"]

    resposta = client.get(f"/movimentacoes/{mov_id}", headers=_headers(token))
    corpo = resposta.json()
    assert corpo["solicitante"]["id"] == usuario.id
    assert corpo["solicitante"]["username"] == usuario.username
    assert corpo["solicitante"]["perfil"] == "ADMIN"


def test_solicitante_e_motivo_aparecem_na_listagem(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": colaborador.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(token),
    )

    resposta = client.get("/movimentacoes", headers=_headers(token))
    item = resposta.json()["items"][0]
    assert item["solicitante"]["username"] == usuario.username
    assert item["motivoResumo"]


def test_movimentacao_sem_solicitante_tem_solicitante_nulo(client, db_session):
    mov = MovimentacaoBuilder().build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.get(f"/movimentacoes/{mov.id}", headers=_headers(token))
    assert resposta.json()["solicitante"] is None
