import pytest

from app.validation.engine import REGRAS_POR_TIPO, executar
from app.validation.types import TipoMovimentacao
from tests.validation.factories import (
    aprovacao_ref,
    contexto_estrutura,
    contexto_transferencia,
    departamento_ref,
)


def test_inv02_nao_para_na_primeira_inconsistencia():
    ctx = contexto_transferencia(departamento_destino=departamento_ref(ativo=False), aprovacoes=[])
    codigos = [i.codigo for i in executar(ctx)]
    assert len(codigos) >= 2
    assert "T04" in codigos
    assert "T06" in codigos


def test_inv04_excecao_nao_tratada_propaga_sem_virar_inconsistencia(monkeypatch):
    def regra_quebrada(ctx):
        raise RuntimeError("falha inesperada de código, não de negócio")

    tipo = TipoMovimentacao.TRANSFERENCIA
    regras_originais = REGRAS_POR_TIPO[tipo]
    monkeypatch.setitem(REGRAS_POR_TIPO, tipo, [*regras_originais, regra_quebrada])

    ctx = contexto_transferencia()
    with pytest.raises(RuntimeError, match="falha inesperada"):
        executar(ctx)


def test_inv05_ordem_deterministica_gerais_antes_de_especificas():
    ctx = contexto_transferencia(
        colaborador=None,  # G01
        departamento_destino=departamento_ref(ativo=False),  # T04
        aprovacoes=[],  # T06 x2
    )
    codigos = [i.codigo for i in executar(ctx)]
    assert codigos[0] == "G01"
    # específicas vêm depois das gerais, na ordem do catálogo T01..T06
    indice_t04 = codigos.index("T04")
    indice_primeiro_t06 = codigos.index("T06")
    assert indice_t04 < indice_primeiro_t06


def test_ca023_duas_execucoes_produzem_resultado_identico_na_mesma_ordem():
    ctx = contexto_transferencia(departamento_destino=departamento_ref(ativo=False), aprovacoes=[])
    primeira = [(i.codigo, i.mensagem) for i in executar(ctx)]
    segunda = [(i.codigo, i.mensagem) for i in executar(ctx)]
    assert primeira == segunda


def test_cnm04_cenario_catastrofico_nao_lanca_excecao():
    ctx = contexto_transferencia(
        colaborador=None,
        departamento_origem=None,
        departamento_destino=None,
        aprovacoes=[],
    )
    codigos = [i.codigo for i in executar(ctx)]
    assert "G01" in codigos
    # regras dependentes de departamento continuam avaliando independentemente (sem pré-condição em G01)
    assert "T01" in codigos
    assert "T03" in codigos


def test_todos_os_tipos_tem_regras_registradas():
    tamanho_esperado = {
        TipoMovimentacao.TRANSFERENCIA: 10,
        TipoMovimentacao.PROMOCAO: 13,  # 4 gerais + 9 específicas (spec revisão 2026-08-19)
        TipoMovimentacao.TROCA_GESTOR: 10,
        TipoMovimentacao.MUDANCA_CENTRO_CUSTO: 10,
        TipoMovimentacao.ALTERACAO_ESTRUTURA: 10,
    }
    for tipo in TipoMovimentacao:
        assert tipo in REGRAS_POR_TIPO
        assert len(REGRAS_POR_TIPO[tipo]) == tamanho_esperado[tipo]


def test_v01_total_de_codigos_no_catalogo_e_37():
    """spec.md §10.7 revisão 2026-08-19 — 4 gerais + 6 transferência + 9
    promoção + 6 troca de gestor + 6 centro de custo + 6 estrutura = 37."""
    codigos = set()
    for regras in REGRAS_POR_TIPO.values():
        for regra in regras:
            codigos.add(regra.__name__.split("_")[0].upper())
    assert len(codigos) == 37
