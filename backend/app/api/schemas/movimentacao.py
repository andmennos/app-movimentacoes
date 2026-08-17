from datetime import datetime

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


class MovimentacaoItem(CamelModel):
    id: int
    tipo: str
    status: str
    colaborador: ColaboradorResumo
    data_solicitacao: datetime
    resultado_ultima_validacao: str | None


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

    aprovacoes: list[AprovacaoResponse]
    ultima_validacao: UltimaValidacaoResponse | None
