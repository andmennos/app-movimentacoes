import { TipoMovimentacao } from './movimentacao.model';

/**
 * spec.md RC-48/T-86 — os cinco tipos do domínio são criáveis pela UI/API.
 * O backend deriva origem/solicitante/status a partir do JWT e do estado
 * atual do colaborador — o payload nunca os envia.
 */
export type TipoMovimentacaoCriavel = TipoMovimentacao;

export interface CriarTransferenciaRequest {
  tipo: 'TRANSFERENCIA';
  colaboradorId: number;
  departamentoDestinoId: number;
}

export interface CriarPromocaoRequest {
  tipo: 'PROMOCAO';
  colaboradorId: number;
  cargoDestinoId: number;
}

export interface CriarMudancaCentroCustoRequest {
  tipo: 'MUDANCA_CENTRO_CUSTO';
  colaboradorId: number;
  centroCustoDestinoId: number;
}

export interface CriarTrocaGestorRequest {
  tipo: 'TROCA_GESTOR';
  colaboradorId: number;
  gestorDestinoId: number;
}

export interface CriarAlteracaoEstruturaRequest {
  tipo: 'ALTERACAO_ESTRUTURA';
  colaboradorId: number;
  estruturaDestinoId: number;
}

export type CriarMovimentacaoRequest =
  | CriarTransferenciaRequest
  | CriarPromocaoRequest
  | CriarMudancaCentroCustoRequest
  | CriarTrocaGestorRequest
  | CriarAlteracaoEstruturaRequest;

export interface CriarMovimentacaoResponse {
  id: number;
  tipo: TipoMovimentacao;
  status: string;
  dataSolicitacao: string;
}
