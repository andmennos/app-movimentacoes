"""T-57 — persistência e domínio base (spec.md revisão 2026-08-19, §2/§9/§7).

Cobre apenas schema/persistência: criação em banco limpo, FKs/unique, e a
garantia de que nenhuma senha é persistida em texto puro. Autenticação (T-58),
RBAC/BOLA (T-59) e as regras de negócio de promoção (T-64) ficam fora daqui.
"""

from datetime import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.models import (
    HistoricoProcessamento,
    OrigemEvento,
    OrigemExecucao,
    PerfilUsuario,
    ResultadoValidacao,
    SecurityLockout,
    TipoAprovacao,
    TipoEventoProcessamento,
    Usuario,
    ValidacaoAuditoria,
)
from tests.builders import CargoBuilder, CentroCustoBuilder, ColaboradorBuilder, MovimentacaoBuilder, UsuarioBuilder


def test_usuario_persiste_apenas_hash_nao_senha_em_texto_puro(db_session):
    usuario = UsuarioBuilder(username="admin", password_hash="$argon2id$fake$hash").build(db_session)

    assert usuario.password_hash != "admin"
    assert "argon2" in usuario.password_hash or usuario.password_hash.startswith("$")
    colunas = {c.key for c in inspect(Usuario).columns}
    assert "senha" not in colunas
    assert "password" not in colunas


def test_usuario_username_e_unico(db_session):
    UsuarioBuilder(username="admin").build(db_session)
    db_session.commit()

    with pytest.raises(IntegrityError):
        UsuarioBuilder(username="admin").build(db_session)


def test_usuario_vincula_colaborador_opcionalmente(db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    usuario = UsuarioBuilder(perfil=PerfilUsuario.RH_ANALISTA, colaborador_id=colaborador.id).build(db_session)
    db_session.commit()

    recarregado = db_session.get(Usuario, usuario.id)
    assert recarregado.colaborador_id == colaborador.id
    assert recarregado.perfil == PerfilUsuario.RH_ANALISTA


def test_perfil_usuario_tem_os_quatro_perfis():
    assert {p.value for p in PerfilUsuario} == {"ADMIN", "RH_ANALISTA", "RH_GESTOR", "LIDERANCA"}


def test_tipo_aprovacao_inclui_gestor_superior_e_gestor_rh():
    valores = {t.value for t in TipoAprovacao}
    assert "GESTOR_SUPERIOR" in valores
    assert "GESTOR_RH" in valores


def test_security_lockout_ip_e_unico(db_session):
    agora = datetime(2026, 8, 19, 10, 0, 0)
    db_session.add(SecurityLockout(ip="10.0.0.1", failed_attempts=1, updated_at=agora))
    db_session.commit()

    db_session.add(SecurityLockout(ip="10.0.0.1", failed_attempts=1, updated_at=agora))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_movimentacao_solicitante_usuario_id_e_nullable_e_referenciavel(db_session):
    sem_solicitante = MovimentacaoBuilder().build(db_session)
    db_session.commit()
    assert sem_solicitante.solicitante_usuario_id is None

    usuario = UsuarioBuilder().build(db_session)
    com_solicitante = MovimentacaoBuilder(solicitante_usuario_id=usuario.id).build(db_session)
    db_session.commit()

    recarregada = db_session.get(type(com_solicitante), com_solicitante.id)
    assert recarregada.solicitante_usuario_id == usuario.id
    assert recarregada.solicitante.username == usuario.username


def test_cargo_tem_familia_ordem_e_custo(db_session):
    cargo = CargoBuilder(familia_cargo="ANALISTA", ordem_progressao=3, custo_mensal_referencia=900_000).build(
        db_session
    )
    db_session.commit()

    recarregado = db_session.get(type(cargo), cargo.id)
    assert recarregado.familia_cargo == "ANALISTA"
    assert recarregado.ordem_progressao == 3
    assert recarregado.custo_mensal_referencia == 900_000


def test_centro_custo_tem_orcamento_e_custo_comprometido(db_session):
    cc = CentroCustoBuilder(orcamento_mensal=10_000_000, custo_comprometido=4_000_000).build(db_session)
    db_session.commit()

    recarregado = db_session.get(type(cc), cc.id)
    assert recarregado.orcamento_mensal == 10_000_000
    assert recarregado.custo_comprometido == 4_000_000
    assert recarregado.orcamento_mensal - recarregado.custo_comprometido == 6_000_000


def test_historico_processamento_registra_ator_e_solicitante(db_session):
    mov = MovimentacaoBuilder().build(db_session)
    ator = UsuarioBuilder(username="aprovador").build(db_session)
    solicitante = UsuarioBuilder(username="quem_pediu").build(db_session)
    db_session.commit()

    evento = HistoricoProcessamento(
        movimentacao_id=mov.id,
        tipo_evento=TipoEventoProcessamento.APROVACAO_CONCLUIDA,
        data_hora=datetime(2026, 8, 19, 11, 0, 0),
        origem=OrigemEvento.MANUAL,
        mensagem="Aprovação concluída.",
        ator_usuario_id=ator.id,
        solicitante_usuario_id=solicitante.id,
    )
    db_session.add(evento)
    db_session.commit()

    recarregado = db_session.get(HistoricoProcessamento, evento.id)
    assert recarregado.ator.username == "aprovador"
    assert recarregado.solicitante.username == "quem_pediu"


def test_historico_processamento_ator_e_solicitante_sao_nullable(db_session):
    mov = MovimentacaoBuilder().build(db_session)
    evento = HistoricoProcessamento(
        movimentacao_id=mov.id,
        tipo_evento=TipoEventoProcessamento.SOLICITACAO_RECEBIDA,
        data_hora=datetime(2026, 8, 19, 11, 0, 0),
        origem=OrigemEvento.SISTEMA,
        mensagem="Solicitação recebida.",
    )
    db_session.add(evento)
    db_session.commit()

    recarregado = db_session.get(HistoricoProcessamento, evento.id)
    assert recarregado.ator_usuario_id is None
    assert recarregado.solicitante_usuario_id is None


def test_validacao_auditoria_registra_solicitante_e_ator(db_session):
    mov = MovimentacaoBuilder().build(db_session)
    solicitante = UsuarioBuilder(username="solicitante_auditoria").build(db_session)
    db_session.commit()

    auditoria = ValidacaoAuditoria(
        movimentacao_id=mov.id,
        data_hora=datetime(2026, 8, 19, 12, 0, 0),
        resultado=ResultadoValidacao.APROVADA,
        total_inconsistencias=0,
        versao_motor="1.0.0",
        origem_execucao=OrigemExecucao.AUTOMATICO,
        solicitante_usuario_id=solicitante.id,
        ator_usuario_id=None,
    )
    db_session.add(auditoria)
    db_session.commit()

    recarregada = db_session.get(ValidacaoAuditoria, auditoria.id)
    assert recarregada.solicitante.username == "solicitante_auditoria"
    assert recarregada.ator_usuario_id is None


def test_indice_username_usuario(engine):
    inspector = inspect(engine)
    indices = [tuple(i["column_names"]) for i in inspector.get_indexes("usuario")]
    unicos = [tuple(u["column_names"]) for u in inspector.get_unique_constraints("usuario")]
    assert ("username",) in indices or ("username",) in unicos or any(
        "username" in cols for cols in indices
    )


def test_indice_ip_security_lockout(engine):
    inspector = inspect(engine)
    indices = [tuple(i["column_names"]) for i in inspector.get_indexes("security_lockout")]
    unicos = [tuple(u["column_names"]) for u in inspector.get_unique_constraints("security_lockout")]
    assert ("ip",) in indices or ("ip",) in unicos
