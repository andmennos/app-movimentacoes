"""T-69 — cenários dedicados de promoção no seed (trilha real de duas
famílias, orçamento, intervalo de 6 meses). Drena o Worker para provar que
cada cenário produz o resultado esperado quando realmente processado."""

from app.models import Colaborador, Movimentacao, StatusMovimentacao, TipoMovimentacao, ValidacaoAuditoria
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


def _codigos_reprovacao(db_session, mov: Movimentacao) -> set[str]:
    auditoria = (
        db_session.query(ValidacaoAuditoria)
        .filter_by(movimentacao_id=mov.id)
        .order_by(ValidacaoAuditoria.id.desc())
        .first()
    )
    if auditoria is None:
        return set()
    return {i.codigo_regra for i in auditoria.inconsistencias}


def test_cenarios_promocao_avancados_produzem_os_resultados_esperados(db_session):
    seed(db_session)
    worker.drenar_fila(db_session)

    casos = {
        "M900101": ("PRO-01 Júnior1->Júnior2", StatusMovimentacao.APROVADA, set()),
        "M900102": ("PRO-02 Júnior1->Júnior3", StatusMovimentacao.REPROVADA, {"P03"}),
        "M900103": ("PRO-03 Júnior3->Pleno1", StatusMovimentacao.APROVADA, set()),
        "M900104": ("PRO-04 Júnior3->Pleno2", StatusMovimentacao.REPROVADA, {"P03"}),
        "M900105": ("PRO-05 mesmo cargo", StatusMovimentacao.REPROVADA, {"P03"}),
        "M900106": ("PRO-06 família diferente", StatusMovimentacao.REPROVADA, {"P07"}),
        "M900109": ("PRO-09 saldo insuficiente", StatusMovimentacao.REPROVADA, {"P09"}),
        "M900110": ("PRO-10 saldo suficiente", StatusMovimentacao.APROVADA, set()),
        "M900111": ("T-73 Pleno3->Sênior1 (fronteira seguinte)", StatusMovimentacao.APROVADA, set()),
    }

    for matricula, (rotulo, status_esperado, codigos_esperados) in casos.items():
        mov = _movimentacao_do_colaborador(db_session, matricula)
        assert mov is not None, f"{rotulo}: movimentação não encontrada para {matricula}"
        assert mov.status == status_esperado, (
            f"{rotulo}: esperado {status_esperado}, obtido {mov.status} "
            f"(inconsistências: {_codigos_reprovacao(db_session, mov)})"
        )
        if codigos_esperados:
            assert codigos_esperados <= _codigos_reprovacao(db_session, mov), (
                f"{rotulo}: esperava {codigos_esperados} entre as inconsistências, "
                f"obtido {_codigos_reprovacao(db_session, mov)}"
            )


def test_intervalo_6_meses_recente_reprova_e_antigo_nao(db_session):
    seed(db_session)
    worker.drenar_fila(db_session)

    mov_recente = _movimentacao_do_colaborador(db_session, "M900107")
    assert mov_recente.status == StatusMovimentacao.REPROVADA
    assert "P08" in _codigos_reprovacao(db_session, mov_recente)

    mov_antigo = _movimentacao_do_colaborador(db_session, "M900108")
    assert mov_antigo.status == StatusMovimentacao.APROVADA


def test_efetivacao_do_cenario_pro10_atualiza_custo_comprometido(db_session):
    from app.models import CentroCusto

    seed(db_session)
    worker.drenar_fila(db_session)

    colaborador = db_session.query(Colaborador).filter_by(matricula="M900110").one()
    cc = db_session.query(CentroCusto).filter_by(codigo="CC-ORC-FOLGADO").one()
    # delta do cenário PRO-10 (Pleno2 -> Pleno3): 100_000
    assert cc.custo_comprometido >= 100_000
    assert colaborador.cargo.codigo == "OPS-PL3"
