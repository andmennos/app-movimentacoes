"""Fábricas leves de `ValidationContext` — sem banco, sem ORM. As regras são
funções puras (RNF-05); estes helpers só montam as estruturas de dados."""

from __future__ import annotations

from app.validation.aprovacoes import EXIGENCIAS_BASE_POR_TIPO
from app.validation.types import (
    AprovacaoRef,
    CargoRef,
    CentroCustoRef,
    ColaboradorRef,
    DepartamentoRef,
    EstadoAprovacao,
    EstruturaRef,
    MovimentacaoRef,
    NoHierarquia,
    TipoAprovacao,
    TipoMovimentacao,
    ValidationContext,
)

_id_counter = iter(range(1, 10_000))
_NAO_INFORMADO = object()
"""Sentinela distinta de None: permite que um teste passe `colaborador=None`
deliberadamente (G01 ausente) sem cair no valor padrão."""


def novo_id() -> int:
    return next(_id_counter)


def cargo_ref(**overrides) -> CargoRef:
    dados = dict(id=novo_id(), nivel=1, ativo=True, permite_gestao=False, aprovacao_adicional=None)
    dados.update(overrides)
    return CargoRef(**dados)


def colaborador_ref(**overrides) -> ColaboradorRef:
    dados = dict(id=novo_id(), ativo=True, cargo=None, gestor_id=None)
    dados.update(overrides)
    return ColaboradorRef(**dados)


def departamento_ref(**overrides) -> DepartamentoRef:
    dados = dict(id=novo_id(), ativo=True, gestor_id=None)
    dados.update(overrides)
    return DepartamentoRef(**dados)


def centro_custo_ref(**overrides) -> CentroCustoRef:
    dados = dict(id=novo_id(), ativo=True, responsavel_id=None)
    dados.update(overrides)
    return CentroCustoRef(**dados)


def estrutura_ref(**overrides) -> EstruturaRef:
    dados = dict(id=novo_id(), ativo=True)
    dados.update(overrides)
    return EstruturaRef(**dados)


def aprovacao_ref(tipo: TipoAprovacao, **overrides) -> AprovacaoRef:
    dados = dict(tipo=tipo, estado=EstadoAprovacao.APROVADA, aprovador_id=novo_id(), aprovador_ativo=True)
    dados.update(overrides)
    return AprovacaoRef(**dados)


def aprovacoes_completas(tipo_movimentacao: TipoMovimentacao, extra: TipoAprovacao | None = None):
    tipos = list(EXIGENCIAS_BASE_POR_TIPO[tipo_movimentacao])
    if extra is not None:
        tipos.append(extra)
    return [aprovacao_ref(t) for t in tipos]


def responsaveis_padrao() -> dict[str, ColaboradorRef]:
    return {
        "GESTOR_ORIGEM": colaborador_ref(),
        "GESTOR_DESTINO": colaborador_ref(),
    }


def contexto_base(
    tipo: TipoMovimentacao,
    colaborador=_NAO_INFORMADO,
    aprovacoes=_NAO_INFORMADO,
    movimentacao=_NAO_INFORMADO,
    **overrides,
) -> ValidationContext:
    """Monta um `ValidationContext` válido por padrão para `tipo`. Passar
    `colaborador=None` explicitamente representa G01 (colaborador ausente) —
    diferente de simplesmente omitir o parâmetro."""
    if colaborador is _NAO_INFORMADO:
        colaborador = colaborador_ref()
    if aprovacoes is _NAO_INFORMADO:
        aprovacoes = aprovacoes_completas(tipo)

    colaborador_id = colaborador.id if colaborador is not None else novo_id()
    if movimentacao is _NAO_INFORMADO:
        movimentacao = MovimentacaoRef(id=novo_id(), tipo=tipo, colaborador_id=colaborador_id)

    dados = dict(
        movimentacao=movimentacao,
        colaborador=colaborador,
        aprovacoes=aprovacoes,
        responsaveis_derivados=responsaveis_padrao(),
        conflito_mesmo_tipo_em_aberto=False,
    )
    dados.update(overrides)
    return ValidationContext(**dados)


def contexto_transferencia(**overrides) -> ValidationContext:
    base = dict(
        departamento_origem=departamento_ref(),
        departamento_destino=departamento_ref(),
    )
    base.update(overrides)
    return contexto_base(TipoMovimentacao.TRANSFERENCIA, **base)


def contexto_promocao(cargo_atual=_NAO_INFORMADO, cargo_destino=_NAO_INFORMADO, **overrides):
    cargo_atual = cargo_ref(nivel=1) if cargo_atual is _NAO_INFORMADO else cargo_atual
    cargo_destino = cargo_ref(nivel=2) if cargo_destino is _NAO_INFORMADO else cargo_destino

    colaborador = overrides.pop("colaborador", _NAO_INFORMADO)
    if colaborador is _NAO_INFORMADO:
        colaborador = colaborador_ref(cargo=cargo_atual)

    extra = cargo_destino.aprovacao_adicional if cargo_destino is not None else None
    extra_tipo = TipoAprovacao(extra.value) if extra is not None else None

    base = dict(
        colaborador=colaborador,
        cargo_atual=cargo_atual,
        cargo_destino=cargo_destino,
    )
    if "aprovacoes" not in overrides:
        base["aprovacoes"] = aprovacoes_completas(TipoMovimentacao.PROMOCAO, extra=extra_tipo)
    base.update(overrides)
    return contexto_base(TipoMovimentacao.PROMOCAO, **base)


def contexto_troca_gestor(
    colaborador=_NAO_INFORMADO,
    gestor_destino=_NAO_INFORMADO,
    cadeia: dict[int, NoHierarquia] | None = None,
    **overrides,
) -> ValidationContext:
    colaborador = colaborador_ref() if colaborador is _NAO_INFORMADO else colaborador
    if gestor_destino is _NAO_INFORMADO:
        gestor_destino = colaborador_ref(cargo=cargo_ref(permite_gestao=True))

    if cadeia is None and gestor_destino is not None:
        cadeia = {gestor_destino.id: NoHierarquia(gestor_destino.id, None)}
    elif cadeia is None:
        cadeia = {}

    base = dict(
        colaborador=colaborador,
        gestor_origem=colaborador_ref(),
        gestor_destino=gestor_destino,
        cadeia_hierarquica=cadeia,
    )
    base.update(overrides)
    return contexto_base(TipoMovimentacao.TROCA_GESTOR, **base)


def contexto_centro_custo(**overrides) -> ValidationContext:
    base = dict(
        centro_custo_origem=centro_custo_ref(),
        centro_custo_destino=centro_custo_ref(),
    )
    base.update(overrides)
    return contexto_base(TipoMovimentacao.MUDANCA_CENTRO_CUSTO, **base)


def contexto_estrutura(**overrides) -> ValidationContext:
    base = dict(
        estrutura_origem=estrutura_ref(),
        estrutura_destino=estrutura_ref(),
    )
    base.update(overrides)
    return contexto_base(TipoMovimentacao.ALTERACAO_ESTRUTURA, **base)
