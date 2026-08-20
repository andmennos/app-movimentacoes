"""Rótulos de apresentação (origem/destino/setor) por tipo de movimentação —
spec.md RC-51/T-87, usados pela tabela de Aprovações. Puramente de exibição:
não decide nada, só formata o snapshot já persistido em `Movimentacao`
(mesmos pares origem/destino já usados no detalhe — cargo usa
`mov.cargo_origem`, o snapshot da solicitação, não `colaborador.cargo`, que
já pode ter sido efetivado — mesma correção de T-74)."""

from __future__ import annotations

from app.models import Movimentacao, TipoMovimentacao


def origem_destino(mov: Movimentacao) -> tuple[str | None, str | None]:
    if mov.tipo == TipoMovimentacao.TRANSFERENCIA:
        origem = mov.departamento_origem.nome if mov.departamento_origem else None
        destino = mov.departamento_destino.nome if mov.departamento_destino else None
        return origem, destino
    if mov.tipo == TipoMovimentacao.PROMOCAO:
        origem = mov.cargo_origem.nome if mov.cargo_origem else None
        destino = mov.cargo_destino.nome if mov.cargo_destino else None
        return origem, destino
    if mov.tipo == TipoMovimentacao.TROCA_GESTOR:
        origem = mov.gestor_origem.nome if mov.gestor_origem else None
        destino = mov.gestor_destino.nome if mov.gestor_destino else None
        return origem, destino
    if mov.tipo == TipoMovimentacao.MUDANCA_CENTRO_CUSTO:
        origem = mov.centro_custo_origem.nome if mov.centro_custo_origem else None
        destino = mov.centro_custo_destino.nome if mov.centro_custo_destino else None
        return origem, destino
    if mov.tipo == TipoMovimentacao.ALTERACAO_ESTRUTURA:
        origem = mov.estrutura_origem.nome if mov.estrutura_origem else None
        destino = mov.estrutura_destino.nome if mov.estrutura_destino else None
        return origem, destino
    return None, None  # pragma: no cover — união exaustiva de TipoMovimentacao


def setor(mov: Movimentacao) -> str | None:
    """spec.md RC-51/T-87 — reaproveita `Colaborador.departamento`, único
    relacionamento de setor/departamento já existente no domínio; nenhuma
    entidade `Setor` nova foi criada."""
    departamento = mov.colaborador.departamento if mov.colaborador else None
    return departamento.nome if departamento else None
