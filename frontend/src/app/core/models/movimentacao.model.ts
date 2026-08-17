export type TipoMovimentacao =
  | 'TRANSFERENCIA'
  | 'PROMOCAO'
  | 'TROCA_GESTOR'
  | 'MUDANCA_CENTRO_CUSTO'
  | 'ALTERACAO_ESTRUTURA';

export type StatusMovimentacao = 'PENDENTE' | 'APROVADA' | 'REPROVADA';

export type ResultadoValidacao = 'APROVADA' | 'REPROVADA' | 'AGUARDANDO_APROVACAO';

export type EstadoAprovacao = 'PENDENTE' | 'APROVADA' | 'REPROVADA';

export type TipoAprovacao = 'GESTOR_ORIGEM' | 'GESTOR_DESTINO' | 'RH' | 'GERENCIA' | 'DIRETORIA';

export interface ColaboradorResumo {
  id: number;
  matricula: string;
  nome: string;
}

export interface ColaboradorDetalhe extends ColaboradorResumo {
  ativo: boolean;
}

export interface CargoResumo {
  id: number;
  nome: string;
  nivel: number;
}

export interface DepartamentoResumo {
  id: number;
  codigo: string;
  nome: string;
  ativo: boolean;
}

export interface CentroCustoResumo {
  id: number;
  codigo: string;
  nome: string;
  ativo: boolean;
}

export interface EstruturaResumo {
  id: number;
  codigo: string;
  nome: string;
  ativo: boolean;
}

export interface GestorResumo {
  id: number;
  matricula: string;
  nome: string;
  ativo: boolean;
}

export interface AprovacaoResponse {
  tipo: TipoAprovacao;
  estado: EstadoAprovacao;
  aprovador: ColaboradorResumo | null;
  dataDecisao: string | null;
}

export interface InconsistenciaResponse {
  codigo: string;
  mensagem: string;
  severidade: string;
}

export interface UltimaValidacaoResponse {
  resultado: ResultadoValidacao;
  validadoEm: string;
  inconsistencias: InconsistenciaResponse[];
}

export interface MovimentacaoItem {
  id: number;
  tipo: TipoMovimentacao;
  status: StatusMovimentacao;
  colaborador: ColaboradorResumo;
  dataSolicitacao: string;
  resultadoUltimaValidacao: ResultadoValidacao | null;
}

export interface MovimentacaoListaResponse {
  items: MovimentacaoItem[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface MovimentacaoDetalheResponse {
  id: number;
  tipo: TipoMovimentacao;
  status: StatusMovimentacao;
  dataSolicitacao: string;
  colaborador: ColaboradorDetalhe;

  cargoAtual: CargoResumo | null;
  cargoDestino: CargoResumo | null;

  departamentoOrigem: DepartamentoResumo | null;
  departamentoDestino: DepartamentoResumo | null;

  centroCustoOrigem: CentroCustoResumo | null;
  centroCustoDestino: CentroCustoResumo | null;

  estruturaOrigem: EstruturaResumo | null;
  estruturaDestino: EstruturaResumo | null;

  gestorOrigem: GestorResumo | null;
  gestorDestino: GestorResumo | null;

  aprovacoes: AprovacaoResponse[];
  ultimaValidacao: UltimaValidacaoResponse | null;
}

/**
 * Formato de resposta de `POST /validar` — usado exclusivamente pelo botão
 * de validação manual do detalhe (ADR-0010), não pela listagem nem pelo
 * carregamento normal do detalhe.
 */
export interface ValidarResponse {
  movimentacaoId: number;
  status: ResultadoValidacao;
  validadoEm: string;
  inconsistencias: InconsistenciaResponse[];
}

export interface ErroResposta {
  erro: {
    codigo: string;
    mensagem: string;
  };
}
