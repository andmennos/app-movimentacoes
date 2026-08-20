export type TipoMovimentacao =
  | 'TRANSFERENCIA'
  | 'PROMOCAO'
  | 'TROCA_GESTOR'
  | 'MUDANCA_CENTRO_CUSTO'
  | 'ALTERACAO_ESTRUTURA';

export type StatusMovimentacao =
  | 'AGUARDANDO_APROVACAO'
  | 'PENDENTE'
  | 'APROVADA'
  | 'REPROVADA'
  | 'BLOQUEADA';

export type ResultadoValidacao = 'APROVADA' | 'REPROVADA';

export type EstadoAprovacao = 'PENDENTE' | 'APROVADA' | 'REPROVADA';

export type TipoAprovacao =
  | 'GESTOR_ORIGEM'
  | 'GESTOR_DESTINO'
  | 'GESTOR_SUPERIOR'
  | 'RH'
  | 'GESTOR_RH'
  | 'GERENCIA'
  | 'DIRETORIA'
  | 'GESTOR_RH_ADICIONAL';

export type PerfilUsuario = 'ADMIN' | 'RH_ANALISTA' | 'RH_GESTOR' | 'LIDERANCA';

export interface SolicitanteResumo {
  id: number;
  username: string;
  perfil: PerfilUsuario;
}

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

export interface ImpedimentoResponse {
  origem: string;
  codigo: string;
  mensagem: string;
}

export interface ProcessamentoResponse {
  estado: string | null;
  podeValidarManualmente: boolean;
  motivoValidacaoManual: string | null;
}

export interface EventoHistoricoResponse {
  tipoEvento: string;
  dataHora: string;
  origem: string;
  mensagem: string;
  detalheSanitizado: string | null;
  ator: string | null;
  solicitante: string | null;
}

export interface MovimentacaoItem {
  id: number;
  tipo: TipoMovimentacao;
  status: StatusMovimentacao;
  colaborador: ColaboradorResumo;
  dataSolicitacao: string;
  resultadoUltimaValidacao: ResultadoValidacao | null;
  solicitante: SolicitanteResumo | null;
  motivoResumo: string;
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

  solicitante: SolicitanteResumo | null;
  motivoResumo: string;

  aprovacoes: AprovacaoResponse[];
  ultimaValidacao: UltimaValidacaoResponse | null;
  impedimentos: ImpedimentoResponse[];
  processamento: ProcessamentoResponse;
  historicoProcessamento: EventoHistoricoResponse[];
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
  impedimentos?: ImpedimentoResponse[];
}
