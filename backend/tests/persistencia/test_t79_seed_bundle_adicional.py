"""T-79 — cenário dedicado do bundle GERENCIA/DIRETORIA + GESTOR_RH_ADICIONAL
com a hierarquia REAL do seed (não builders isolados de teste), drenado pelo
Worker real, provando que as quatro ordens corretas são geradas e decididas
quando aplicável (plan.md §23 checklist de T-79)."""

from app.models import Aprovacao, Colaborador, EstadoAprovacao, Movimentacao, StatusMovimentacao, TipoMovimentacao
from app.processing import worker
from app.seed.seed import seed


def _movimentacao_do_colaborador(db_session, matricula: str) -> Movimentacao:
    colaborador = db_session.query(Colaborador).filter_by(matricula=matricula).one()
    return (
        db_session.query(Movimentacao)
        .filter_by(colaborador_id=colaborador.id, tipo=TipoMovimentacao.PROMOCAO)
        .order_by(Movimentacao.id.desc())
        .first()
    )


def test_bundle_gerencia_efetiva_com_quatro_aprovacoes_ordenadas(db_session):
    seed(db_session)
    worker.drenar_fila(db_session)

    mov = _movimentacao_do_colaborador(db_session, "M900201")
    assert mov is not None
    assert mov.status == StatusMovimentacao.APROVADA, "engine deve aprovar — bundle GERENCIA completo"

    aprovacoes = db_session.query(Aprovacao).filter_by(movimentacao_id=mov.id).all()
    tipos_aprovados = {a.tipo.value for a in aprovacoes if a.estado == EstadoAprovacao.APROVADA}
    assert tipos_aprovados == {"GESTOR_ORIGEM", "RH", "GERENCIA", "GESTOR_RH_ADICIONAL"}

    colaborador = db_session.get(Colaborador, mov.colaborador_id)
    assert colaborador.cargo_id == mov.cargo_destino_id, "efetivação real: cargo atualizado"


def test_bundle_diretoria_efetiva_com_quatro_aprovacoes_ordenadas(db_session):
    seed(db_session)
    worker.drenar_fila(db_session)

    mov = _movimentacao_do_colaborador(db_session, "M900202")
    assert mov is not None
    assert mov.status == StatusMovimentacao.APROVADA, "engine deve aprovar — bundle DIRETORIA completo"

    aprovacoes = db_session.query(Aprovacao).filter_by(movimentacao_id=mov.id).all()
    tipos_aprovados = {a.tipo.value for a in aprovacoes if a.estado == EstadoAprovacao.APROVADA}
    assert tipos_aprovados == {"GESTOR_ORIGEM", "RH", "DIRETORIA", "GESTOR_RH_ADICIONAL"}

    colaborador = db_session.get(Colaborador, mov.colaborador_id)
    assert colaborador.cargo_id == mov.cargo_destino_id


def test_bundle_aprovadores_sao_pessoas_reais_da_hierarquia_do_seed(db_session):
    """As linhas GERENCIA/DIRETORIA devem ter, como responsável esperado,
    de fato "gerente"/"diretor" da hierarquia do seed — não um perfil
    genérico (RC-38: sem parse de nome, resolução real pela cadeia)."""
    from app.services.movimentacao_service import montar_contexto
    from app.validation.aprovacoes import exigencias_para

    seed(db_session)

    gerente = db_session.query(Colaborador).filter_by(matricula="M000002").one()  # 2º da cadeia (ver _criar_hierarquia)
    diretor = db_session.query(Colaborador).filter_by(matricula="M000001").one()  # matrícula marcadora

    mov_gerencia = _movimentacao_do_colaborador(db_session, "M900201")
    ctx = montar_contexto(db_session, mov_gerencia)
    exigencia_gerencia = next(e for e in exigencias_para(ctx) if e.tipo.value == "GERENCIA")
    assert exigencia_gerencia.aprovador_esperado_colaborador_id == gerente.id

    mov_diretoria = _movimentacao_do_colaborador(db_session, "M900202")
    ctx2 = montar_contexto(db_session, mov_diretoria)
    exigencia_diretoria = next(e for e in exigencias_para(ctx2) if e.tipo.value == "DIRETORIA")
    assert exigencia_diretoria.aprovador_esperado_colaborador_id == diretor.id
