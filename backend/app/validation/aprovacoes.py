"""Política dinâmica de aprovações — spec.md §5/plan.md §9.

Fonte única da verdade: `exigencias_para(ctx)` é a **única** função que
decide quais aprovações uma movimentação exige, para quem, e em que ordem.
Nenhum outro módulo (Router, Producer, Worker, AprovacaoService, seed,
Angular) mantém uma segunda cópia dessa matriz — todos chamam esta função
(diretamente ou via `tipos_exigidos`, que extrai só os tipos).

Perfis são comparados por string (`ctx.solicitante_perfil`) em vez de
importar `app.models.PerfilUsuario`: este módulo é puro (INV-01), sem
dependência de ORM — os valores coincidem por construção com
`PerfilUsuario.value` e são cobertos por teste.
"""

from __future__ import annotations

from app.validation.types import (
    EstadoAprovacao,
    ExigenciaAprovacao,
    Inconsistencia,
    TipoAprovacao,
    TipoMovimentacao,
    ValidationContext,
)

PERFIL_ADMIN = "ADMIN"
PERFIL_RH_ANALISTA = "RH_ANALISTA"
PERFIL_RH_GESTOR = "RH_GESTOR"


def _solicitante_e(ctx: ValidationContext, colaborador_id: int | None) -> bool:
    """spec.md RC-07 — ADMIN nunca aciona substituição/remoção de etapa: a
    política sempre monta a matriz "normal" para ele, e a exceção de
    autoaprovação é resolvida depois, na autorização da decisão (T-62), não
    aqui na composição das exigências."""
    if ctx.solicitante_perfil == PERFIL_ADMIN:
        return False
    if colaborador_id is None or ctx.solicitante_colaborador_id is None:
        return False
    return ctx.solicitante_colaborador_id == colaborador_id


def _e_rh_analista(ctx: ValidationContext) -> bool:
    return ctx.solicitante_perfil == PERFIL_RH_ANALISTA


def _aprovador_esperado(ctx: ValidationContext, chave: str) -> int | None:
    ref = ctx.responsaveis_derivados.get(chave)
    return ref.id if ref is not None else None


def _exigencia(tipo: TipoAprovacao, ordem: int, ctx: ValidationContext | None = None, chave: str | None = None) -> ExigenciaAprovacao:
    if chave is not None and ctx is not None:
        return ExigenciaAprovacao(tipo=tipo, ordem=ordem, aprovador_esperado_colaborador_id=_aprovador_esperado(ctx, chave))
    return ExigenciaAprovacao(tipo=tipo, ordem=ordem)


def _exigencia_perfil(tipo: TipoAprovacao, ordem: int, perfil: str = PERFIL_RH_GESTOR) -> ExigenciaAprovacao:
    return ExigenciaAprovacao(tipo=tipo, ordem=ordem, perfil_esperado=perfil)


def _transferencia(ctx: ValidationContext) -> list[ExigenciaAprovacao]:
    if _e_rh_analista(ctx):
        return [
            _exigencia(TipoAprovacao.GESTOR_ORIGEM, 1, ctx, "GESTOR_ORIGEM"),
            _exigencia(TipoAprovacao.GESTOR_DESTINO, 1, ctx, "GESTOR_DESTINO"),
            _exigencia_perfil(TipoAprovacao.GESTOR_RH, 1),
        ]
    exigencias = [
        _exigencia(TipoAprovacao.GESTOR_ORIGEM, 1, ctx, "GESTOR_ORIGEM"),
        _exigencia(TipoAprovacao.GESTOR_DESTINO, 1, ctx, "GESTOR_DESTINO"),
        _exigencia_perfil(TipoAprovacao.RH, 1),
    ]
    if _solicitante_e(ctx, _aprovador_esperado(ctx, "GESTOR_ORIGEM")):
        exigencias = [e for e in exigencias if e.tipo != TipoAprovacao.GESTOR_ORIGEM]
    elif _solicitante_e(ctx, _aprovador_esperado(ctx, "GESTOR_DESTINO")):
        exigencias = [e for e in exigencias if e.tipo != TipoAprovacao.GESTOR_DESTINO]
    return exigencias


def _troca_gestor(ctx: ValidationContext) -> list[ExigenciaAprovacao]:
    if _e_rh_analista(ctx):
        return [
            _exigencia(TipoAprovacao.GESTOR_ORIGEM, 1, ctx, "GESTOR_ORIGEM"),
            _exigencia(TipoAprovacao.GESTOR_DESTINO, 1, ctx, "GESTOR_DESTINO"),
            _exigencia_perfil(TipoAprovacao.GESTOR_RH, 1),
        ]
    exigencias = [
        _exigencia(TipoAprovacao.GESTOR_ORIGEM, 1, ctx, "GESTOR_ORIGEM"),
        _exigencia(TipoAprovacao.GESTOR_DESTINO, 1, ctx, "GESTOR_DESTINO"),
        _exigencia_perfil(TipoAprovacao.RH, 1),
    ]
    if _solicitante_e(ctx, _aprovador_esperado(ctx, "GESTOR_ORIGEM")):
        exigencias = [e for e in exigencias if e.tipo != TipoAprovacao.GESTOR_ORIGEM]
    elif _solicitante_e(ctx, _aprovador_esperado(ctx, "GESTOR_DESTINO")):
        exigencias = [e for e in exigencias if e.tipo != TipoAprovacao.GESTOR_DESTINO]
    return exigencias


def _centro_custo(ctx: ValidationContext) -> list[ExigenciaAprovacao]:
    if _e_rh_analista(ctx):
        return [
            _exigencia(TipoAprovacao.GESTOR_DESTINO, 1, ctx, "GESTOR_DESTINO"),
            _exigencia_perfil(TipoAprovacao.GESTOR_RH, 1),
        ]
    if _solicitante_e(ctx, _aprovador_esperado(ctx, "GESTOR_DESTINO")):
        return [_exigencia_perfil(TipoAprovacao.RH, 1)]
    return [
        _exigencia(TipoAprovacao.GESTOR_DESTINO, 1, ctx, "GESTOR_DESTINO"),
        _exigencia_perfil(TipoAprovacao.RH, 1),
    ]


def _estrutura(ctx: ValidationContext) -> list[ExigenciaAprovacao]:
    if _e_rh_analista(ctx):
        return [
            _exigencia(TipoAprovacao.GESTOR_ORIGEM, 1, ctx, "GESTOR_ORIGEM"),
            _exigencia_perfil(TipoAprovacao.GESTOR_RH, 1),
        ]
    if _solicitante_e(ctx, _aprovador_esperado(ctx, "GESTOR_ORIGEM")):
        return [_exigencia_perfil(TipoAprovacao.RH, 1)]
    return [
        _exigencia(TipoAprovacao.GESTOR_ORIGEM, 1, ctx, "GESTOR_ORIGEM"),
        _exigencia_perfil(TipoAprovacao.RH, 1),
    ]


def _promocao(ctx: ValidationContext) -> list[ExigenciaAprovacao]:
    """spec.md §5.4 — sequência hierárquica -> RH/GESTOR_RH -> GERENCIA/
    DIRETORIA (quando aplicável). `ordem` reflete essa dependência; T-62
    aplica o bloqueio "etapa posterior não decide antes da anterior"."""
    gestor_atual_id = _aprovador_esperado(ctx, "GESTOR_ORIGEM")
    exigencias: list[ExigenciaAprovacao]

    if _e_rh_analista(ctx):
        exigencias = [
            _exigencia(TipoAprovacao.GESTOR_ORIGEM, 1, ctx, "GESTOR_ORIGEM"),
            _exigencia_perfil(TipoAprovacao.GESTOR_RH, 2),
        ]
    elif _solicitante_e(ctx, gestor_atual_id):
        if ctx.solicitante_superior_colaborador_id is not None:
            exigencias = [
                ExigenciaAprovacao(
                    tipo=TipoAprovacao.GESTOR_SUPERIOR,
                    ordem=1,
                    aprovador_esperado_colaborador_id=ctx.solicitante_superior_colaborador_id,
                ),
                _exigencia_perfil(TipoAprovacao.RH, 2),
            ]
        else:
            # spec §5.4 — solicitante (gestor) no topo, sem superior: uma
            # única etapa (tipo GESTOR_RH, decidida pelo perfil RH_GESTOR)
            # cobre a aprovação hierárquica; não existe uma segunda etapa
            # RH/GESTOR_RH separada.
            exigencias = [_exigencia_perfil(TipoAprovacao.GESTOR_RH, 1)]
    else:
        exigencias = [
            _exigencia(TipoAprovacao.GESTOR_ORIGEM, 1, ctx, "GESTOR_ORIGEM"),
            _exigencia_perfil(TipoAprovacao.RH, 2),
        ]

    extra = aprovacao_adicional_promocao(ctx)
    if extra is not None:
        # spec §5.4/RC-36/RC-37 (T-75) — duas anuências adicionais distintas
        # e obrigatórias, nesta ordem: a liderança hierárquica correspondente
        # (GERENCIA/DIRETORIA, pessoa concreta resolvida via
        # Cargo.papel_lideranca — services/movimentacao_service.py), depois
        # GESTOR_RH_ADICIONAL (perfil RH_GESTOR). Tipo técnico distinto de
        # GESTOR_RH para não colidir com uma substituição anterior da mesma
        # movimentação (UNIQUE(movimentacao_id, tipo)).
        ordem_lideranca = max((e.ordem for e in exigencias), default=0) + 1
        exigencias.append(_exigencia(extra, ordem_lideranca, ctx, extra.value))
        exigencias.append(
            _exigencia_perfil(TipoAprovacao.GESTOR_RH_ADICIONAL, ordem_lideranca + 1, PERFIL_RH_GESTOR)
        )

    return exigencias


_POLITICA_POR_TIPO = {
    TipoMovimentacao.TRANSFERENCIA: _transferencia,
    TipoMovimentacao.PROMOCAO: _promocao,
    TipoMovimentacao.TROCA_GESTOR: _troca_gestor,
    TipoMovimentacao.MUDANCA_CENTRO_CUSTO: _centro_custo,
    TipoMovimentacao.ALTERACAO_ESTRUTURA: _estrutura,
}


def aprovacao_adicional_promocao(ctx: ValidationContext) -> TipoAprovacao | None:
    """A aprovação extra de PROMOCAO (spec §5.3.1) — GERENCIA/DIRETORIA quando
    `cargo_destino.aprovacao_adicional` não é nulo. `None` nos demais tipos ou
    quando não aplicável."""
    if ctx.movimentacao is None or ctx.movimentacao.tipo != TipoMovimentacao.PROMOCAO:
        return None
    if ctx.cargo_destino is None or ctx.cargo_destino.aprovacao_adicional is None:
        return None
    return TipoAprovacao(ctx.cargo_destino.aprovacao_adicional.value)


def exigencias_para(ctx: ValidationContext) -> list[ExigenciaAprovacao]:
    """spec.md §5 — função central e determinística: única fonte das
    aprovações exigidas por uma movimentação, dado quem a solicitou."""
    if ctx.movimentacao is None:
        return []
    montar = _POLITICA_POR_TIPO.get(ctx.movimentacao.tipo)
    if montar is None:
        return []
    return montar(ctx)


def tipos_exigidos(ctx: ValidationContext) -> list[TipoAprovacao]:
    """Compatibilidade com o gate/producer, que só precisam do *tipo* e do
    *estado* de cada exigência (spec §5.3/processing/approval_gate.py) — a
    identidade do aprovador esperado é usada pela integridade (`integra`) e
    pela autorização de decisão (T-62)."""
    return [e.tipo for e in exigencias_para(ctx)]


def _linha(ctx: ValidationContext, tipo: TipoAprovacao):
    for aprovacao in ctx.aprovacoes:
        if aprovacao.tipo == tipo:
            return aprovacao
    return None


def _responsavel_esperado_valido(ctx: ValidationContext, tipo: TipoAprovacao) -> bool:
    """Condição 3 de spec §5.3 — aplica-se apenas às etapas de aprovador
    específico (pessoa), não às etapas por perfil (RH/GESTOR_RH/RH_GESTOR).
    O responsável esperado é resolvido pelo `services/` conforme spec
    §5.3.1 e chega pronto em `ctx.responsaveis_derivados`."""
    chave = {
        TipoAprovacao.GESTOR_ORIGEM: "GESTOR_ORIGEM",
        TipoAprovacao.GESTOR_DESTINO: "GESTOR_DESTINO",
        TipoAprovacao.GESTOR_SUPERIOR: "GESTOR_SUPERIOR",
        # T-75/RC-38 — GERENCIA/DIRETORIA passam a exigir pessoa concreta
        # (papel_lideranca); GESTOR_RH_ADICIONAL continua por perfil (não
        # entra aqui, mesma razão de RH/GESTOR_RH).
        TipoAprovacao.GERENCIA: "GERENCIA",
        TipoAprovacao.DIRETORIA: "DIRETORIA",
    }.get(tipo)
    if chave is None:
        return True
    responsavel = ctx.responsaveis_derivados.get(chave)
    return responsavel is not None and responsavel.ativo


def integra(ctx: ValidationContext, tipo: TipoAprovacao) -> bool:
    linha = _linha(ctx, tipo)
    if linha is None:
        return False
    if linha.estado in (EstadoAprovacao.APROVADA, EstadoAprovacao.REPROVADA):
        if not linha.aprovador_id or not linha.aprovador_ativo:
            return False
    return _responsavel_esperado_valido(ctx, tipo)


def mensagem_generica(tipo: TipoAprovacao) -> str:
    return f"Aprovação {tipo.value} ausente / aprovador inválido"


def emitir_se_nao_integra(
    ctx: ValidationContext, tipo: TipoAprovacao, codigo: str, mensagem: str | None = None
) -> list[Inconsistencia]:
    """Bloco de construção usado pelas regras Txx/Pxx/TGxx/CCxx/AExx de aprovação:
    avalia a integridade de `tipo` e, se falhar, emite uma Inconsistencia sob o
    código público da regra do tipo (spec §5.3) — nunca um código próprio."""
    if integra(ctx, tipo):
        return []
    return [Inconsistencia(codigo, mensagem or mensagem_generica(tipo))]
