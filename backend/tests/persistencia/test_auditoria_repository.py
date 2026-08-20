from datetime import datetime

from app.models import OrigemExecucao, ResultadoValidacao
from app.repositories import auditoria_repository as repo
from app.validation.types import Inconsistencia, Severidade
from tests.builders import MovimentacaoBuilder


def test_criar_grava_um_registro_com_n_inconsistencias(db_session):
    mov = MovimentacaoBuilder().build(db_session)
    inconsistencias = [
        Inconsistencia(codigo="G02", mensagem="Colaborador não está ativo"),
        Inconsistencia(codigo="T03", mensagem="Departamento de destino não encontrado"),
    ]

    auditoria = repo.criar(
        db_session,
        movimentacao_id=mov.id,
        resultado=ResultadoValidacao.REPROVADA,
        inconsistencias=inconsistencias,
        versao_motor="1.0.0",
        data_hora=datetime(2026, 1, 1, 10, 0, 0),
        origem_execucao=OrigemExecucao.AUTOMATICO,
    )

    assert auditoria.id is not None
    assert auditoria.total_inconsistencias == 2
    assert len(auditoria.inconsistencias) == 2
    assert {i.codigo_regra for i in auditoria.inconsistencias} == {"G02", "T03"}
    assert all(i.severidade.value == Severidade.ERRO.value for i in auditoria.inconsistencias)


def test_buscar_ultima_retorna_a_mais_recente(db_session):
    mov = MovimentacaoBuilder().build(db_session)
    repo.criar(
        db_session,
        mov.id,
        ResultadoValidacao.REPROVADA,
        [],
        "1.0.0",
        datetime(2026, 1, 1, 10, 0, 0),
        OrigemExecucao.AUTOMATICO,
    )
    mais_recente = repo.criar(
        db_session,
        mov.id,
        ResultadoValidacao.APROVADA,
        [],
        "1.0.0",
        datetime(2026, 1, 2, 10, 0, 0),
        OrigemExecucao.AUTOMATICO,
    )

    encontrada = repo.buscar_ultima(db_session, mov.id)

    assert encontrada.id == mais_recente.id
    assert encontrada.resultado == ResultadoValidacao.APROVADA


def test_revalidar_nao_altera_registros_anteriores(db_session):
    mov = MovimentacaoBuilder().build(db_session)
    primeira = repo.criar(
        db_session,
        mov.id,
        ResultadoValidacao.REPROVADA,
        [],
        "1.0.0",
        datetime(2026, 1, 1, 10, 0, 0),
        OrigemExecucao.AUTOMATICO,
    )
    repo.criar(
        db_session,
        mov.id,
        ResultadoValidacao.APROVADA,
        [],
        "1.0.0",
        datetime(2026, 1, 2, 10, 0, 0),
        OrigemExecucao.AUTOMATICO,
    )

    primeira_id = primeira.id
    db_session.expire_all()
    ainda_la = db_session.get(type(primeira), primeira_id)

    assert ainda_la is not None
    assert ainda_la.resultado == ResultadoValidacao.REPROVADA


def test_buscar_ultima_sem_validacao_retorna_none(db_session):
    mov = MovimentacaoBuilder().build(db_session)
    assert repo.buscar_ultima(db_session, mov.id) is None


def test_repositorio_nao_expoe_update_nem_delete():
    nomes_publicos = {nome for nome in dir(repo) if not nome.startswith("_")}
    proibidos = {"atualizar", "editar", "remover", "deletar", "excluir", "update", "delete"}
    assert nomes_publicos.isdisjoint(proibidos)
    assert {"criar", "buscar_ultima"} <= nomes_publicos
