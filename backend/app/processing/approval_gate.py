"""Gate de aprovação do fluxo automático — spec.md §5.4.

Reutiliza exclusivamente `app.validation.aprovacoes` (`tipos_exigidos`,
`integra`) como fonte única das exigências por tipo. Não existe, e não deve
existir, um segundo mapa de aprovações exigidas em `processing/`.
"""

from __future__ import annotations

import enum

from app.validation import aprovacoes
from app.validation.types import EstadoAprovacao, ValidationContext


class GateResultado(str, enum.Enum):
    """`ANOMALO`: linha exigida ausente, ou aprovação `APROVADA` sem
    integridade (spec §5.4, última linha da tabela). Cenário anômalo de
    dado — o producer não o mascara como `PENDENTE` nem como `REPROVADA`;
    apenas não agenda. Continua coberto pelas regras de integridade do motor
    (T06/P04-06/TG06/CC06/AE06) quando a movimentação for validada
    diretamente."""

    APTA = "APTA"
    PENDENTE = "PENDENTE"
    REPROVADA = "REPROVADA"
    ANOMALO = "ANOMALO"


def avaliar(ctx: ValidationContext) -> GateResultado:
    """spec.md §5.4 — situação das aprovações exigidas → ação do producer.

    Precedência REPROVADA > ANOMALO > PENDENTE > APTA: a mesma ordem de
    decisividade usada por `validation.engine.resolver_resultado` (uma
    reprovação nunca é mascarada por outra situação menos decisiva).
    """
    tipos = aprovacoes.tipos_exigidos(ctx)
    linhas = {linha.tipo: linha for linha in ctx.aprovacoes}

    tem_reprovada = False
    tem_pendente = False
    tem_anomalia = False

    for tipo in tipos:
        linha = linhas.get(tipo)
        if linha is None:
            tem_anomalia = True
            continue
        if linha.estado == EstadoAprovacao.REPROVADA:
            tem_reprovada = True
        elif linha.estado == EstadoAprovacao.PENDENTE:
            tem_pendente = True
        elif linha.estado == EstadoAprovacao.APROVADA and not aprovacoes.integra(ctx, tipo):
            tem_anomalia = True

    if tem_reprovada:
        return GateResultado.REPROVADA
    if tem_anomalia:
        return GateResultado.ANOMALO
    if tem_pendente:
        return GateResultado.PENDENTE
    return GateResultado.APTA
