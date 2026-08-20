from datetime import datetime

from app.validation.engine import executar
from app.validation.promocao import (
    p01_cargo_destino_existe,
    p02_cargo_destino_ativo,
    p03_proximo_passo_da_trilha,
    p04_aprovacao_gestor,
    p05_aprovacao_rh,
    p06_aprovacao_superior,
    p07_mesma_familia_cargo,
    p08_intervalo_minimo_desde_ultima_promocao,
    p09_orcamento_centro_custo,
)
from app.validation.types import (
    AprovacaoAdicional,
    CentroCustoRef,
    EstadoAprovacao,
    MovimentacaoRef,
    TipoAprovacao,
    TipoMovimentacao,
)
from tests.validation.factories import aprovacao_ref, cargo_ref, contexto_promocao, novo_id


def test_p01_dispara_quando_cargo_destino_ausente():
    ctx = contexto_promocao(cargo_destino=None)
    assert [i.codigo for i in p01_cargo_destino_existe(ctx)] == ["P01"]


def test_p01_suprime_quando_cargo_destino_presente():
    assert p01_cargo_destino_existe(contexto_promocao()) == []


def test_p02_dispara_quando_cargo_destino_inativo():
    ctx = contexto_promocao(cargo_destino=cargo_ref(nivel=2, ativo=False))
    assert [i.codigo for i in p02_cargo_destino_ativo(ctx)] == ["P02"]


def test_p02_suprime_quando_cargo_destino_ativo():
    assert p02_cargo_destino_ativo(contexto_promocao()) == []


def test_p02_precondicao_nao_avalia_sem_cargo_destino():
    ctx = contexto_promocao(cargo_destino=None)
    assert p02_cargo_destino_ativo(ctx) == []


# --- P03: próximo passo exato da trilha (ordem_progressao), spec §10.3 ---


def test_p03_junior1_para_junior2_permitido():
    atual = cargo_ref(nivel=1, ordem_progressao=1)
    destino = cargo_ref(nivel=2, ordem_progressao=2)
    assert p03_proximo_passo_da_trilha(contexto_promocao(cargo_atual=atual, cargo_destino=destino)) == []


def test_p03_junior1_para_junior3_bloqueado():
    atual = cargo_ref(nivel=1, ordem_progressao=1)
    destino = cargo_ref(nivel=3, ordem_progressao=3)
    ctx = contexto_promocao(cargo_atual=atual, cargo_destino=destino)
    assert [i.codigo for i in p03_proximo_passo_da_trilha(ctx)] == ["P03"]


def test_p03_junior3_para_pleno1_permitido_apesar_do_numero_reiniciar():
    """spec.md §9.1 — Júnior 3 (ordem 3) -> Pleno 1 (ordem 4) é o próximo
    passo real da trilha, mesmo com o número do cargo reiniciando em 1."""
    atual = cargo_ref(nivel=3, ordem_progressao=3)
    destino = cargo_ref(nivel=1, ordem_progressao=4)
    assert p03_proximo_passo_da_trilha(contexto_promocao(cargo_atual=atual, cargo_destino=destino)) == []


def test_p03_junior3_para_pleno2_bloqueado_por_pular_uma_posicao():
    atual = cargo_ref(nivel=3, ordem_progressao=3)
    destino = cargo_ref(nivel=2, ordem_progressao=5)
    ctx = contexto_promocao(cargo_atual=atual, cargo_destino=destino)
    assert [i.codigo for i in p03_proximo_passo_da_trilha(ctx)] == ["P03"]


def test_p03_mesmo_cargo_bloqueado():
    atual = cargo_ref(nivel=2, ordem_progressao=4)
    destino = cargo_ref(nivel=2, ordem_progressao=4)
    ctx = contexto_promocao(cargo_atual=atual, cargo_destino=destino)
    assert [i.codigo for i in p03_proximo_passo_da_trilha(ctx)] == ["P03"]


def test_p03_precondicao_nao_avalia_sem_cargo_atual_conhecido():
    ctx = contexto_promocao(cargo_atual=None)
    assert p03_proximo_passo_da_trilha(ctx) == []


def test_p03_precondicao_nao_avalia_sem_cargo_destino():
    ctx = contexto_promocao(cargo_destino=None)
    assert p03_proximo_passo_da_trilha(ctx) == []


def test_p04_dispara_quando_aprovacao_gestor_ausente():
    ctx = contexto_promocao(aprovacoes=[aprovacao_ref(TipoAprovacao.RH)])
    assert [i.codigo for i in p04_aprovacao_gestor(ctx)] == ["P04"]


def test_p04_suprime_quando_aprovacao_gestor_integra():
    assert p04_aprovacao_gestor(contexto_promocao()) == []


def test_p04_reconhece_gestor_superior_como_etapa_hierarquica():
    from tests.validation.factories import colaborador_ref

    ctx = contexto_promocao(
        aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_SUPERIOR), aprovacao_ref(TipoAprovacao.RH)],
        responsaveis_derivados={"GESTOR_SUPERIOR": colaborador_ref()},
    )
    assert p04_aprovacao_gestor(ctx) == []


def test_p05_dispara_quando_aprovacao_rh_ausente():
    ctx = contexto_promocao(aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM)])
    assert [i.codigo for i in p05_aprovacao_rh(ctx)] == ["P05"]


def test_p05_suprime_quando_aprovacao_rh_integra():
    assert p05_aprovacao_rh(contexto_promocao()) == []


def test_p05_reconhece_gestor_rh_como_etapa_rh():
    ctx = contexto_promocao(
        aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM), aprovacao_ref(TipoAprovacao.GESTOR_RH)]
    )
    assert p05_aprovacao_rh(ctx) == []


def test_p06_dispara_quando_diretoria_exigida_e_ausente():
    """T-75 — P06 agora dispara uma vez por sub-etapa do bundle adicional
    faltante: aqui faltam as duas (DIRETORIA e GESTOR_RH_ADICIONAL)."""
    cargo_destino = cargo_ref(nivel=5, aprovacao_adicional=AprovacaoAdicional.DIRETORIA)
    ctx = contexto_promocao(
        cargo_destino=cargo_destino,
        aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM), aprovacao_ref(TipoAprovacao.RH)],
    )
    assert [i.codigo for i in p06_aprovacao_superior(ctx)] == ["P06", "P06"]


def test_p06_suprime_quando_nao_aplicavel():
    ctx = contexto_promocao(cargo_destino=cargo_ref(nivel=2, aprovacao_adicional=None))
    assert p06_aprovacao_superior(ctx) == []


def test_p06_suprime_quando_diretoria_exigida_e_integra():
    cargo_destino = cargo_ref(nivel=5, aprovacao_adicional=AprovacaoAdicional.DIRETORIA)
    ctx = contexto_promocao(cargo_destino=cargo_destino)
    assert p06_aprovacao_superior(ctx) == []


# --- P07: mesma família de cargo, spec §10.3 ---


def test_p07_familia_diferente_reprova():
    atual = cargo_ref(nivel=1, familia_cargo="OPERACOES")
    destino = cargo_ref(nivel=2, familia_cargo="TECNOLOGIA")
    ctx = contexto_promocao(cargo_atual=atual, cargo_destino=destino)
    assert [i.codigo for i in p07_mesma_familia_cargo(ctx)] == ["P07"]


def test_p07_mesma_familia_passa():
    atual = cargo_ref(nivel=1, familia_cargo="OPERACOES")
    destino = cargo_ref(nivel=2, familia_cargo="OPERACOES")
    ctx = contexto_promocao(cargo_atual=atual, cargo_destino=destino)
    assert p07_mesma_familia_cargo(ctx) == []


def test_p07_precondicao_nao_avalia_sem_cargo_destino():
    assert p07_mesma_familia_cargo(contexto_promocao(cargo_destino=None)) == []


# --- P08: intervalo mínimo de 6 meses-calendário, spec §9.3/§11.4 ---


def test_p08_promocao_efetivada_ha_menos_de_6_meses_reprova():
    ctx = contexto_promocao(
        movimentacao=MovimentacaoRef(
            id=novo_id(), tipo=TipoMovimentacao.PROMOCAO, colaborador_id=novo_id(),
            data_solicitacao=datetime(2026, 8, 19),
        ),
        data_ultima_promocao_efetivada=datetime(2026, 5, 1),
    )
    assert [i.codigo for i in p08_intervalo_minimo_desde_ultima_promocao(ctx)] == ["P08"]


def test_p08_promocao_efetivada_ha_exatamente_6_meses_passa():
    ctx = contexto_promocao(
        movimentacao=MovimentacaoRef(
            id=novo_id(), tipo=TipoMovimentacao.PROMOCAO, colaborador_id=novo_id(),
            data_solicitacao=datetime(2026, 8, 19),
        ),
        data_ultima_promocao_efetivada=datetime(2026, 2, 19),
    )
    assert p08_intervalo_minimo_desde_ultima_promocao(ctx) == []


def test_p08_promocao_efetivada_ha_mais_de_6_meses_passa():
    ctx = contexto_promocao(
        movimentacao=MovimentacaoRef(
            id=novo_id(), tipo=TipoMovimentacao.PROMOCAO, colaborador_id=novo_id(),
            data_solicitacao=datetime(2026, 8, 19),
        ),
        data_ultima_promocao_efetivada=datetime(2025, 1, 1),
    )
    assert p08_intervalo_minimo_desde_ultima_promocao(ctx) == []


def test_p08_sem_promocao_anterior_passa():
    ctx = contexto_promocao(data_ultima_promocao_efetivada=None)
    assert p08_intervalo_minimo_desde_ultima_promocao(ctx) == []


def test_p08_precondicao_nao_avalia_sem_cargo_destino():
    ctx = contexto_promocao(cargo_destino=None, data_ultima_promocao_efetivada=datetime(2026, 8, 1))
    assert p08_intervalo_minimo_desde_ultima_promocao(ctx) == []


# --- P09: orçamento do centro de custo atual, spec §9.3/§11.5 ---


def test_p09_saldo_insuficiente_reprova():
    atual = cargo_ref(nivel=1, custo_mensal_referencia=500_000)
    destino = cargo_ref(nivel=2, custo_mensal_referencia=900_000)
    cc = CentroCustoRef(id=novo_id(), ativo=True, responsavel_id=None, orcamento_mensal=1_000_000, custo_comprometido=700_000)
    ctx = contexto_promocao(cargo_atual=atual, cargo_destino=destino, centro_custo_origem=cc)
    assert [i.codigo for i in p09_orcamento_centro_custo(ctx)] == ["P09"]


def test_p09_saldo_suficiente_passa():
    atual = cargo_ref(nivel=1, custo_mensal_referencia=500_000)
    destino = cargo_ref(nivel=2, custo_mensal_referencia=900_000)
    cc = CentroCustoRef(id=novo_id(), ativo=True, responsavel_id=None, orcamento_mensal=1_000_000, custo_comprometido=100_000)
    ctx = contexto_promocao(cargo_atual=atual, cargo_destino=destino, centro_custo_origem=cc)
    assert p09_orcamento_centro_custo(ctx) == []


def test_p09_delta_negativo_vira_zero_nunca_reprova():
    """destino mais barato que atual (raro, mas possível): delta = max(x, 0)."""
    atual = cargo_ref(nivel=2, custo_mensal_referencia=900_000)
    destino = cargo_ref(nivel=1, custo_mensal_referencia=500_000)
    cc = CentroCustoRef(id=novo_id(), ativo=True, responsavel_id=None, orcamento_mensal=100, custo_comprometido=100)
    ctx = contexto_promocao(cargo_atual=atual, cargo_destino=destino, centro_custo_origem=cc)
    assert p09_orcamento_centro_custo(ctx) == []


def test_p09_sem_centro_custo_origem_nao_avalia():
    assert p09_orcamento_centro_custo(contexto_promocao(centro_custo_origem=None)) == []


def test_p09_precondicao_nao_avalia_sem_cargo_destino():
    cc = CentroCustoRef(id=novo_id(), ativo=True, responsavel_id=None, orcamento_mensal=0, custo_comprometido=0)
    assert p09_orcamento_centro_custo(contexto_promocao(cargo_destino=None, centro_custo_origem=cc)) == []


def test_ca032_linha_ausente_reprova_sob_codigo_da_regra():
    ctx = contexto_promocao(aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM)])
    codigos = [i.codigo for i in executar(ctx)]
    assert "P05" in codigos


def test_ca033_aprovador_inativo_produz_inconsistencia_de_integridade():
    ctx = contexto_promocao(
        aprovacoes=[
            aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM),
            aprovacao_ref(TipoAprovacao.RH, estado=EstadoAprovacao.APROVADA, aprovador_ativo=False),
        ]
    )
    codigos = [i.codigo for i in executar(ctx)]
    assert "P05" in codigos


def test_cnm02_multiplas_inconsistencias_promocao():
    cargo_destino = cargo_ref(nivel=1, ativo=False, ordem_progressao=1)  # mesma ordem do atual + inativo
    ctx = contexto_promocao(
        cargo_atual=cargo_ref(nivel=1, ordem_progressao=1),
        cargo_destino=cargo_destino,
        aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM)],  # RH ausente
    )
    codigos = [i.codigo for i in executar(ctx)]
    assert "P02" in codigos
    assert "P03" in codigos
    assert "P05" in codigos
