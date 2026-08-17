"""Estruturas puras do motor de validação.

INV-01: nada neste módulo (nem em `validation/` como um todo) importa ORM,
FastAPI, Pydantic ou `app.models`. Todo dado chega pronto via `ValidationContext`,
montado pelo `services/` a partir de consultas explícitas.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date, datetime


class Severidade(str, enum.Enum):
    ERRO = "ERRO"


class TipoMovimentacao(str, enum.Enum):
    TRANSFERENCIA = "TRANSFERENCIA"
    PROMOCAO = "PROMOCAO"
    TROCA_GESTOR = "TROCA_GESTOR"
    MUDANCA_CENTRO_CUSTO = "MUDANCA_CENTRO_CUSTO"
    ALTERACAO_ESTRUTURA = "ALTERACAO_ESTRUTURA"


class TipoAprovacao(str, enum.Enum):
    GESTOR_ORIGEM = "GESTOR_ORIGEM"
    GESTOR_DESTINO = "GESTOR_DESTINO"
    RH = "RH"
    GERENCIA = "GERENCIA"
    DIRETORIA = "DIRETORIA"


class EstadoAprovacao(str, enum.Enum):
    PENDENTE = "PENDENTE"
    APROVADA = "APROVADA"
    REPROVADA = "REPROVADA"


class AprovacaoAdicional(str, enum.Enum):
    GERENCIA = "GERENCIA"
    DIRETORIA = "DIRETORIA"


class ResultadoValidacao(str, enum.Enum):
    APROVADA = "APROVADA"
    REPROVADA = "REPROVADA"
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"


@dataclass(frozen=True)
class Inconsistencia:
    codigo: str
    mensagem: str
    severidade: Severidade = Severidade.ERRO


@dataclass(frozen=True)
class CargoRef:
    id: int
    nivel: int
    ativo: bool
    permite_gestao: bool
    aprovacao_adicional: AprovacaoAdicional | None


@dataclass(frozen=True)
class ColaboradorRef:
    id: int
    ativo: bool
    cargo: CargoRef | None
    gestor_id: int | None


@dataclass(frozen=True)
class DepartamentoRef:
    id: int
    ativo: bool
    gestor_id: int | None


@dataclass(frozen=True)
class CentroCustoRef:
    id: int
    ativo: bool
    responsavel_id: int | None


@dataclass(frozen=True)
class EstruturaRef:
    id: int
    ativo: bool


@dataclass(frozen=True)
class MovimentacaoRef:
    id: int
    tipo: TipoMovimentacao
    colaborador_id: int


@dataclass(frozen=True)
class AprovacaoRef:
    tipo: TipoAprovacao
    estado: EstadoAprovacao
    aprovador_id: int | None
    aprovador_ativo: bool | None


@dataclass(frozen=True)
class NoHierarquia:
    """Um nó da cadeia de gestores, pré-carregada a partir de `gestor_destino`
    para sustentar TG05 sem I/O durante a regra."""

    id: int
    gestor_id: int | None


@dataclass
class ValidationContext:
    movimentacao: MovimentacaoRef | None
    colaborador: ColaboradorRef | None

    cargo_atual: CargoRef | None = None
    cargo_destino: CargoRef | None = None

    departamento_origem: DepartamentoRef | None = None
    departamento_destino: DepartamentoRef | None = None

    centro_custo_origem: CentroCustoRef | None = None
    centro_custo_destino: CentroCustoRef | None = None

    estrutura_origem: EstruturaRef | None = None
    estrutura_destino: EstruturaRef | None = None

    gestor_origem: ColaboradorRef | None = None
    gestor_destino: ColaboradorRef | None = None

    cadeia_hierarquica: dict[int, NoHierarquia] = field(default_factory=dict)
    """Todos os nós alcançáveis a partir de `gestor_destino` subindo por `gestor_id`,
    indexados por id — pré-carregados para TG05, sem I/O durante a regra."""

    aprovacoes: list[AprovacaoRef] = field(default_factory=list)

    responsaveis_derivados: dict[str, ColaboradorRef | None] = field(default_factory=dict)
    """Responsável esperado por GESTOR_ORIGEM/GESTOR_DESTINO, resolvido conforme
    spec.md §5.3.1 — chaves "GESTOR_ORIGEM"/"GESTOR_DESTINO"."""

    conflito_mesmo_tipo_em_aberto: bool = False
    """G04: existe outra movimentação do mesmo tipo, mesmo colaborador, PENDENTE, id diferente."""
