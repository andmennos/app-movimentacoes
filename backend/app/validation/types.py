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
    GESTOR_SUPERIOR = "GESTOR_SUPERIOR"
    RH = "RH"
    GESTOR_RH = "GESTOR_RH"
    GERENCIA = "GERENCIA"
    DIRETORIA = "DIRETORIA"
    GESTOR_RH_ADICIONAL = "GESTOR_RH_ADICIONAL"


class EstadoAprovacao(str, enum.Enum):
    PENDENTE = "PENDENTE"
    APROVADA = "APROVADA"
    REPROVADA = "REPROVADA"


class AprovacaoAdicional(str, enum.Enum):
    GERENCIA = "GERENCIA"
    DIRETORIA = "DIRETORIA"


class ResultadoValidacao(str, enum.Enum):
    """spec.md §7.5 — a engine só é chamada com aprovações já concluídas
    (gate). `AGUARDANDO_APROVACAO` não é mais resultado possível da engine."""

    APROVADA = "APROVADA"
    REPROVADA = "REPROVADA"


@dataclass(frozen=True)
class Inconsistencia:
    codigo: str
    mensagem: str
    severidade: Severidade = Severidade.ERRO


@dataclass(frozen=True)
class ExigenciaAprovacao:
    """spec.md §5/plan.md §9.1 — uma etapa exigida pela política dinâmica.

    `aprovador_esperado_colaborador_id` identifica uma etapa exigida de uma
    pessoa específica (GESTOR_ORIGEM/DESTINO/SUPERIOR); `perfil_esperado`
    identifica uma etapa decidida por perfil (RH/GESTOR_RH, hoje sempre
    `RH_GESTOR`) — as duas são mutuamente exclusivas. `ordem` só é
    significativa dentro de PROMOCAO (spec §5.4); nos demais tipos todas as
    etapas têm `ordem=1` (paralelas, sem sequenciamento)."""

    tipo: TipoAprovacao
    ordem: int
    aprovador_esperado_colaborador_id: int | None = None
    perfil_esperado: str | None = None


@dataclass(frozen=True)
class CargoRef:
    id: int
    nivel: int
    ativo: bool
    permite_gestao: bool
    aprovacao_adicional: AprovacaoAdicional | None
    familia_cargo: str | None = None
    ordem_progressao: int | None = None
    custo_mensal_referencia: int = 0


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
    orcamento_mensal: int = 0
    custo_comprometido: int = 0


@dataclass(frozen=True)
class EstruturaRef:
    id: int
    ativo: bool


@dataclass(frozen=True)
class MovimentacaoRef:
    id: int
    tipo: TipoMovimentacao
    colaborador_id: int
    data_solicitacao: datetime | None = None


@dataclass(frozen=True)
class AprovacaoRef:
    tipo: TipoAprovacao
    estado: EstadoAprovacao
    aprovador_id: int | None
    aprovador_ativo: bool | None
    aprovador_nome: str | None = None
    """Só usado para compor mensagens de `impedimentos` (spec §2.4) — as 34
    regras nunca leem este campo, apenas `aprovador_id`/`aprovador_ativo`."""


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
    """Responsável esperado por GESTOR_ORIGEM/GESTOR_DESTINO/GESTOR_SUPERIOR,
    resolvido conforme spec.md §5.3.1 — chaves "GESTOR_ORIGEM"/
    "GESTOR_DESTINO"/"GESTOR_SUPERIOR"."""

    conflito_mesmo_tipo_em_aberto: bool = False
    """G04: existe outra movimentação do mesmo tipo, mesmo colaborador, PENDENTE, id diferente."""

    solicitante_perfil: str | None = None
    """spec.md §5 — perfil do usuário que solicitou (para RH_ANALISTA/ADMIN
    influenciarem a política). `None` para solicitações sem usuário
    associado (dados históricos do seed pré-autenticação)."""
    solicitante_colaborador_id: int | None = None
    """Colaborador vinculado ao solicitante, quando houver — usado para
    detectar "solicitante é o próprio aprovador esperado" (RC-07)."""
    solicitante_superior_colaborador_id: int | None = None
    """`gestor_id` do colaborador do solicitante — só relevante para P/
    GESTOR_SUPERIOR (spec §5.4). `None` se o solicitante não tiver
    colaborador vinculado ou estiver no topo da hierarquia."""

    data_ultima_promocao_efetivada: datetime | None = None
    """spec.md §9.3/§11.1 — data de efetivação (`data_ultima_validacao`) da
    promoção mais recente já `APROVADA` deste colaborador, excluindo a
    movimentação atual. `None` se nunca houve promoção efetivada — P08 passa
    nesse caso (spec §11.4)."""
