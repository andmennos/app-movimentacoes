"""Efetivação local — spec.md §4.2/RC-18. Aplica no cadastro do colaborador a
mudança aprovada, na mesma unidade transacional da auditoria/status/job
(coordenada pelo orquestrador — `processing/orchestrator.py`).

Só é chamado depois que a engine terminou sem inconsistências (INV-12). Os
campos de origem/destino da `Movimentacao` permanecem snapshot da solicitação
— nunca são sobrescritos aqui.
"""

from __future__ import annotations

from app.models import Colaborador, Movimentacao, TipoMovimentacao

_CAMPO_POR_TIPO: dict[TipoMovimentacao, tuple[str, str]] = {
    TipoMovimentacao.TRANSFERENCIA: ("departamento_id", "departamento_destino_id"),
    TipoMovimentacao.PROMOCAO: ("cargo_id", "cargo_destino_id"),
    TipoMovimentacao.TROCA_GESTOR: ("gestor_id", "gestor_destino_id"),
    TipoMovimentacao.MUDANCA_CENTRO_CUSTO: ("centro_custo_id", "centro_custo_destino_id"),
    TipoMovimentacao.ALTERACAO_ESTRUTURA: ("estrutura_id", "estrutura_destino_id"),
}


def efetivar(colaborador: Colaborador, movimentacao: Movimentacao) -> None:
    """Aplica no `colaborador` o campo atual correspondente ao `destino` da
    movimentação (spec.md §4.2 — mapa fixo por tipo, um único campo por tipo).
    PROMOCAO também atualiza o custo comprometido do centro de custo atual
    (spec §11.1) — mesma chamada, mesma transação do orquestrador."""
    if movimentacao.tipo == TipoMovimentacao.PROMOCAO:
        _efetivar_promocao(colaborador, movimentacao)
        return
    campo_colaborador, campo_destino = _CAMPO_POR_TIPO[movimentacao.tipo]
    novo_valor = getattr(movimentacao, campo_destino)
    setattr(colaborador, campo_colaborador, novo_valor)


def _efetivar_promocao(colaborador: Colaborador, movimentacao: Movimentacao) -> None:
    cargo_atual = colaborador.cargo
    cargo_destino = movimentacao.cargo_destino
    centro_custo = movimentacao.centro_custo_origem

    custo_atual = cargo_atual.custo_mensal_referencia if cargo_atual is not None else 0
    custo_destino = cargo_destino.custo_mensal_referencia if cargo_destino is not None else 0
    delta = max(custo_destino - custo_atual, 0)

    colaborador.cargo_id = movimentacao.cargo_destino_id
    if centro_custo is not None and delta:
        centro_custo.custo_comprometido += delta
