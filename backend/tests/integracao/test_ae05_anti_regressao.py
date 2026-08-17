"""Guarda anti-regressão de AE05 (spec.md §9) — nível de integração, com uma
árvore real de `EstruturaOrganizacional` persistida no banco. Prova, contra
dados reais de ancestralidade, que a validação não enxerga a árvore.

CA-027 (inspeção estática de que `estrutura.py` não referencia
`estrutura_pai_id`) foi deliberadamente removido do conjunto de testes
automatizados — testava implementação, não comportamento — e é verificado
por revisão de código (plan.md V-03). O que resta aqui são os testes
comportamentais que efetivamente impedem a reintrodução de ciclo.
"""

from app.models import TipoMovimentacao
from app.repositories import movimentacao_repository
from app.services.movimentacao_service import montar_contexto
from app.validation.engine import executar
from tests.builders import (
    ColaboradorBuilder,
    EstruturaOrganizacionalBuilder,
    MovimentacaoBuilder,
    criar_aprovacoes_exigidas,
)


def _validar(db_session, mov_id):
    mov = movimentacao_repository.carregar_para_validacao(db_session, mov_id)
    ctx = montar_contexto(db_session, mov)
    return executar(ctx)


def _colaborador_com_gestor_ativo(db_session):
    """AE06 deriva GESTOR_ORIGEM de `colaborador.gestor_id` (spec §5.3.1) —
    para isolar o comportamento de AE05, o colaborador precisa de um gestor
    ativo, senão AE06 dispara e contamina a lista de códigos de estrutura."""
    gestor = ColaboradorBuilder().build(db_session)
    return ColaboradorBuilder(gestor_id=gestor.id).build(db_session)


def test_cn_a01_destino_ancestral_da_origem_valida_sem_inconsistencia_de_estrutura(db_session):
    raiz = EstruturaOrganizacionalBuilder(nivel=1).build(db_session)
    filha = EstruturaOrganizacionalBuilder(nivel=2, estrutura_pai_id=raiz.id).build(db_session)
    neta = EstruturaOrganizacionalBuilder(nivel=3, estrutura_pai_id=filha.id).build(db_session)
    colaborador = _colaborador_com_gestor_ativo(db_session)

    # destino (raiz) é ancestral da origem (neta) — cenário que reprovaria
    # se uma regra de ciclo fosse reintroduzida em AE05.
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.ALTERACAO_ESTRUTURA,
        colaborador_id=colaborador.id,
        estrutura_origem_id=neta.id,
        estrutura_destino_id=raiz.id,
    ).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    inconsistencias = _validar(db_session, mov.id)

    codigos_estrutura = [i.codigo for i in inconsistencias if i.codigo.startswith("AE")]
    assert codigos_estrutura == []


def test_cn_a02_destino_descendente_da_origem_valida_sem_inconsistencia_de_estrutura(db_session):
    raiz = EstruturaOrganizacionalBuilder(nivel=1).build(db_session)
    filha = EstruturaOrganizacionalBuilder(nivel=2, estrutura_pai_id=raiz.id).build(db_session)
    neta = EstruturaOrganizacionalBuilder(nivel=3, estrutura_pai_id=filha.id).build(db_session)
    colaborador = _colaborador_com_gestor_ativo(db_session)

    # destino (neta) é descendente da origem (raiz) — idem CN-A01, sentido oposto.
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.ALTERACAO_ESTRUTURA,
        colaborador_id=colaborador.id,
        estrutura_origem_id=raiz.id,
        estrutura_destino_id=neta.id,
    ).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    inconsistencias = _validar(db_session, mov.id)

    codigos_estrutura = [i.codigo for i in inconsistencias if i.codigo.startswith("AE")]
    assert codigos_estrutura == []


def test_ca025_origem_igual_destino_emite_ae05_sem_mencionar_ciclo(db_session):
    est = EstruturaOrganizacionalBuilder().build(db_session)
    colaborador = _colaborador_com_gestor_ativo(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.ALTERACAO_ESTRUTURA,
        colaborador_id=colaborador.id,
        estrutura_origem_id=est.id,
        estrutura_destino_id=est.id,
    ).build(db_session)
    criar_aprovacoes_exigidas(db_session, mov)
    db_session.commit()

    inconsistencias = _validar(db_session, mov.id)

    codigos = [i.codigo for i in inconsistencias]
    assert codigos == ["AE05"]
    assert "ciclo" not in inconsistencias[0].mensagem.lower()


def test_cn_a04_conjunto_de_codigos_emitiveis_e_subconjunto_dos_10_esperados(db_session):
    # colaborador inativo (G02) + estrutura inativa e igual em ambos os lados
    # (AE02, AE04, AE05) + nenhuma aprovação criada (AE06): vários códigos de
    # uma vez, todos dentro do conjunto fechado esperado para este tipo.
    colaborador = ColaboradorBuilder(ativo=False).build(db_session)
    raiz = EstruturaOrganizacionalBuilder(nivel=1, ativo=False).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.ALTERACAO_ESTRUTURA,
        colaborador_id=colaborador.id,
        estrutura_origem_id=raiz.id,
        estrutura_destino_id=raiz.id,
    ).build(db_session)
    db_session.commit()

    inconsistencias = _validar(db_session, mov.id)

    esperado = {"G01", "G02", "G03", "G04", "AE01", "AE02", "AE03", "AE04", "AE05", "AE06"}
    codigos = {i.codigo for i in inconsistencias}
    assert codigos <= esperado
    assert {"G02", "AE02", "AE04", "AE05", "AE06"} <= codigos
