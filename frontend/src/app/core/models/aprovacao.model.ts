import { ColaboradorResumo, SolicitanteResumo, TipoAprovacao, TipoMovimentacao } from './movimentacao.model';

export interface AprovacaoPendenteResponse {
  movimentacaoId: number;
  tipo: TipoAprovacao;
  tipoMovimentacao: TipoMovimentacao;
  ordem: number;
  colaborador: ColaboradorResumo;
  dataSolicitacao: string;
  solicitante: SolicitanteResumo | null;
  origem: string | null;
  destino: string | null;
  setor: string | null;
}

export type DecisaoAprovacao = 'APROVADA' | 'REPROVADA';

export interface DecidirAprovacaoRequest {
  decisao: DecisaoAprovacao;
  justificativa?: string;
}

export interface DecidirAprovacaoResponse {
  movimentacaoId: number;
  tipo: TipoAprovacao;
  estado: string;
  dataDecisao: string;
  movimentacaoStatus: string;
}
