"""Gate de aprovação do fluxo automático — spec.md §5.3 (revisão 2026-08-18).

Reutiliza exclusivamente `app.validation.aprovacoes.tipos_exigidos` como fonte
única das exigências por tipo. Não existe, e não deve existir, um segundo mapa
de aprovações exigidas em `processing/`.

O gate avalia apenas o **estado** (PENDENTE/APROVADA/REPROVADA) de cada
aprovação exigida — não a integridade do aprovador. A integridade (aprovador
existe/ativo, é o responsável esperado) permanece exclusivamente com a engine,
via T06/P04-06/TG06/CC06/AE06, quando a movimentação chega lá (spec §5.2). Uma
aprovação `APROVADA` com aprovador inválido não bloqueia o gate — ela é
reprovada pela engine no momento certo. Por isso não existe mais o estado
`ANOMALO` desta revisão em diante.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from app.validation import aprovacoes
from app.validation.types import EstadoAprovacao, ValidationContext


class GateResultado(str, enum.Enum):
    APTO = "APTO"
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"
    BLOQUEADA = "BLOQUEADA"


@dataclass(frozen=True)
class Impedimento:
    """spec.md §2.4 — impedimento de **fluxo**, nunca confundido com
    `InconsistenciaAuditoria` (que é exclusivamente resultado das 34 regras,
    só existe quando a engine executa)."""

    origem: str
    codigo: str
    mensagem: str


def avaliar(ctx: ValidationContext) -> GateResultado:
    """spec.md §5.3 — precedência REPROVADA > PENDENTE > APTO. Considera
    somente aprovações exigidas (`tipos_exigidos`); uma aprovação extra não
    exigida (CN-Q20) nunca interfere. Uma linha ausente é tratada como não
    decidida (mesmo efeito de PENDENTE)."""
    tipos = aprovacoes.tipos_exigidos(ctx)
    linhas = {linha.tipo: linha for linha in ctx.aprovacoes}

    tem_reprovada = False
    tem_pendente = False

    for tipo in tipos:
        linha = linhas.get(tipo)
        if linha is None or linha.estado == EstadoAprovacao.PENDENTE:
            tem_pendente = True
        elif linha.estado == EstadoAprovacao.REPROVADA:
            tem_reprovada = True
        # APROVADA (íntegra ou não) não contribui para pendente/reprovada.

    if tem_reprovada:
        return GateResultado.BLOQUEADA
    if tem_pendente:
        return GateResultado.AGUARDANDO_APROVACAO
    return GateResultado.APTO


def calcular_impedimentos(ctx: ValidationContext) -> list[Impedimento]:
    """Só faz sentido chamar quando `avaliar(ctx)` não é `APTO` — mas é seguro
    chamar sempre: se todas as exigidas estiverem `APROVADA`, devolve lista
    vazia. Usado pelo detalhe (`GET /movimentacoes/{id}`) e pelas respostas
    409 de `POST /validar` (spec §8.2/§8.3).

    spec.md RC-47/T-85 — `BLOQUEADA` é terminal: quando existe ao menos uma
    etapa `REPROVADA` entre as exigidas, o workflow de aprovação já encerrou
    e nenhuma etapa de ordem posterior é alcançável — mesmo que sua linha
    ainda esteja `PENDENTE` no banco (ela nunca chegou a ser decidida, porque
    a ordem sequencial bloqueia decisão fora de sequência). Reportar essas
    linhas `PENDENTE` como "aguardando aprovação" junto da reprovação real é
    o bug real reproduzido no E2E (ex.: DIRETORIA reprovada + GESTOR_RH_ADICIONAL
    ainda PENDENTE aparecendo como se fosse a próxima etapa) — por isso, havendo
    reprovação, só as reprovações são reportadas."""
    tipos = aprovacoes.tipos_exigidos(ctx)
    linhas = {linha.tipo: linha for linha in ctx.aprovacoes}
    reprovados: list[Impedimento] = []
    pendentes: list[Impedimento] = []

    for tipo in tipos:
        linha = linhas.get(tipo)
        if linha is None or linha.estado == EstadoAprovacao.PENDENTE:
            pendentes.append(
                Impedimento(
                    origem="APROVACAO",
                    codigo="APROVACAO_PENDENTE",
                    mensagem=f"Aguardando aprovação {tipo.value}.",
                )
            )
        elif linha.estado == EstadoAprovacao.REPROVADA:
            quem = f" por {linha.aprovador_nome}" if linha.aprovador_nome else ""
            reprovados.append(
                Impedimento(
                    origem="APROVACAO",
                    codigo="APROVACAO_REPROVADA",
                    mensagem=f"Aprovação {tipo.value} reprovada{quem}.",
                )
            )

    return reprovados if reprovados else pendentes
