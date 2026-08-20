from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import ConfigDict, Field

from app.api.schemas.base import CamelModel


class ColaboradorResumo(CamelModel):
    id: int
    matricula: str
    nome: str


class ColaboradorDetalhe(ColaboradorResumo):
    ativo: bool


class CargoResumo(CamelModel):
    id: int
    nome: str
    nivel: int


class DepartamentoResumo(CamelModel):
    id: int
    codigo: str
    nome: str
    ativo: bool


class CentroCustoResumo(CamelModel):
    id: int
    codigo: str
    nome: str
    ativo: bool


class EstruturaResumo(CamelModel):
    id: int
    codigo: str
    nome: str
    ativo: bool


class GestorResumo(CamelModel):
    id: int
    matricula: str
    nome: str
    ativo: bool


class SolicitanteResumo(CamelModel):
    id: int
    username: str
    perfil: str


class AprovacaoResponse(CamelModel):
    tipo: str
    estado: str
    aprovador: ColaboradorResumo | None
    data_decisao: datetime | None


class InconsistenciaResponse(CamelModel):
    codigo: str
    mensagem: str
    severidade: str


class UltimaValidacaoResponse(CamelModel):
    resultado: str
    validado_em: datetime
    inconsistencias: list[InconsistenciaResponse]


class ImpedimentoResponse(CamelModel):
    origem: str
    codigo: str
    mensagem: str


class ProcessamentoResponse(CamelModel):
    estado: str | None
    pode_validar_manualmente: bool
    motivo_validacao_manual: str | None


class EventoHistoricoResponse(CamelModel):
    tipo_evento: str
    data_hora: datetime
    origem: str
    mensagem: str
    detalhe_sanitizado: str | None
    ator: str | None = None
    solicitante: str | None = None


class MovimentacaoItem(CamelModel):
    id: int
    tipo: str
    status: str
    colaborador: ColaboradorResumo
    data_solicitacao: datetime
    resultado_ultima_validacao: str | None
    solicitante: SolicitanteResumo | None = None
    motivo_resumo: str


class CriarTransferenciaRequest(CamelModel):
    """spec.md §4.2 — o cliente nunca envia origem/solicitante/status; o
    backend deriva tudo a partir do JWT e do estado atual do colaborador."""

    model_config = ConfigDict(extra="forbid")

    tipo: Literal["TRANSFERENCIA"]
    colaborador_id: int
    departamento_destino_id: int


class CriarPromocaoRequest(CamelModel):
    model_config = ConfigDict(extra="forbid")

    tipo: Literal["PROMOCAO"]
    colaborador_id: int
    cargo_destino_id: int


class CriarMudancaCentroCustoRequest(CamelModel):
    model_config = ConfigDict(extra="forbid")

    tipo: Literal["MUDANCA_CENTRO_CUSTO"]
    colaborador_id: int
    centro_custo_destino_id: int


class CriarTrocaGestorRequest(CamelModel):
    """spec.md RC-48/T-86 — origem (`gestor_origem_id`) é derivada pelo
    backend a partir do `gestor_id` atual do colaborador; o cliente só
    controla o destino."""

    model_config = ConfigDict(extra="forbid")

    tipo: Literal["TROCA_GESTOR"]
    colaborador_id: int
    gestor_destino_id: int


class CriarAlteracaoEstruturaRequest(CamelModel):
    model_config = ConfigDict(extra="forbid")

    tipo: Literal["ALTERACAO_ESTRUTURA"]
    colaborador_id: int
    estrutura_destino_id: int


CriarMovimentacaoRequest = Annotated[
    Union[
        CriarTransferenciaRequest,
        CriarPromocaoRequest,
        CriarMudancaCentroCustoRequest,
        CriarTrocaGestorRequest,
        CriarAlteracaoEstruturaRequest,
    ],
    Field(discriminator="tipo"),
]


class CriarMovimentacaoResponse(CamelModel):
    id: int
    tipo: str
    status: str
    data_solicitacao: datetime


class MovimentacaoListaResponse(CamelModel):
    items: list[MovimentacaoItem]
    page: int
    page_size: int
    total: int
    total_pages: int


class MovimentacaoDetalheResponse(CamelModel):
    id: int
    tipo: str
    status: str
    data_solicitacao: datetime
    colaborador: ColaboradorDetalhe

    cargo_atual: CargoResumo | None = None
    cargo_destino: CargoResumo | None = None

    departamento_origem: DepartamentoResumo | None = None
    departamento_destino: DepartamentoResumo | None = None

    centro_custo_origem: CentroCustoResumo | None = None
    centro_custo_destino: CentroCustoResumo | None = None

    estrutura_origem: EstruturaResumo | None = None
    estrutura_destino: EstruturaResumo | None = None

    gestor_origem: GestorResumo | None = None
    gestor_destino: GestorResumo | None = None

    solicitante: SolicitanteResumo | None = None
    motivo_resumo: str

    aprovacoes: list[AprovacaoResponse]
    ultima_validacao: UltimaValidacaoResponse | None
    impedimentos: list[ImpedimentoResponse]
    processamento: ProcessamentoResponse
    historico_processamento: list[EventoHistoricoResponse]
