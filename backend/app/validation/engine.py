"""Motor de validação — composição das regras e resolução do resultado
(spec.md §7, plan.md §5.3/5.4).
"""

from __future__ import annotations

from app.validation.centro_custo import REGRAS_CENTRO_CUSTO
from app.validation.common import REGRAS_GERAIS
from app.validation.estrutura import REGRAS_ESTRUTURA
from app.validation.promocao import REGRAS_PROMOCAO
from app.validation.transferencia import REGRAS_TRANSFERENCIA
from app.validation.troca_gestor import REGRAS_TROCA_GESTOR
from app.validation.types import (
    EstadoAprovacao,
    Inconsistencia,
    ResultadoValidacao,
    TipoMovimentacao,
    ValidationContext,
)

REGRAS_POR_TIPO = {
    TipoMovimentacao.TRANSFERENCIA: [*REGRAS_GERAIS, *REGRAS_TRANSFERENCIA],
    TipoMovimentacao.PROMOCAO: [*REGRAS_GERAIS, *REGRAS_PROMOCAO],
    TipoMovimentacao.TROCA_GESTOR: [*REGRAS_GERAIS, *REGRAS_TROCA_GESTOR],
    TipoMovimentacao.MUDANCA_CENTRO_CUSTO: [*REGRAS_GERAIS, *REGRAS_CENTRO_CUSTO],
    TipoMovimentacao.ALTERACAO_ESTRUTURA: [*REGRAS_GERAIS, *REGRAS_ESTRUTURA],
}
"""Listas explícitas por tipo, gerais → específicas, na ordem do catálogo
(INV-05). Sem herança, sem registro dinâmico."""


def executar(ctx: ValidationContext) -> list[Inconsistencia]:
    """Executa todas as regras aplicáveis, na ordem do catálogo. Não para na
    primeira inconsistência (INV-02).

    Sem `try/except` por regra: uma exceção não tratada propaga para
    `services/` — não vira inconsistência, não existe `SYS01` (INV-04). A
    validação não foi concluída; não há resultado de negócio confiável a
    persistir.
    """
    if ctx.movimentacao is None:
        return []
    # G03 precisa ser alcançável mesmo quando `tipo` não pertence a nenhum
    # tipo conhecido — nesse caso, só as regras gerais rodam.
    regras = REGRAS_POR_TIPO.get(ctx.movimentacao.tipo, REGRAS_GERAIS)

    inconsistencias: list[Inconsistencia] = []
    for regra in regras:
        inconsistencias.extend(regra(ctx))
    return inconsistencias


def resolver_resultado(
    inconsistencias: list[Inconsistencia], aprovacoes: list
) -> ResultadoValidacao:
    """spec.md §5.4 / plan.md §5.4:

    inconsistências não vazias        -> REPROVADA
    alguma aprovação REPROVADA        -> REPROVADA
    alguma aprovação PENDENTE         -> AGUARDANDO_APROVACAO
    todas APROVADA                    -> APROVADA

    Aprovação exigida ausente ou não íntegra já gerou inconsistência na etapa
    anterior (via Txx/Pxx/TGxx/CCxx/AExx), portanto cai no primeiro ramo.
    """
    if inconsistencias:
        return ResultadoValidacao.REPROVADA
    if any(a.estado == EstadoAprovacao.REPROVADA for a in aprovacoes):
        return ResultadoValidacao.REPROVADA
    if any(a.estado == EstadoAprovacao.PENDENTE for a in aprovacoes):
        return ResultadoValidacao.AGUARDANDO_APROVACAO
    return ResultadoValidacao.APROVADA
