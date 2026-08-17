import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  MovimentacaoDetalheResponse,
  MovimentacaoListaResponse,
  ResultadoValidacao,
  StatusMovimentacao,
  ValidarResponse
} from '../models/movimentacao.model';
import { API_BASE_URL } from './api-config';

export interface ListarMovimentacoesParams {
  page?: number;
  pageSize?: number;
  status?: StatusMovimentacao;
  busca?: string;
  ordenarPor?: string;
  direcao?: 'asc' | 'desc';
}

/**
 * Único ponto de comunicação com o backend (RC-10, CA-039 — nunca decide
 * validade, só consulta e repassa comandos). O gatilho normal do produto
 * continua sendo automático (producer + Worker); `validar()` existe
 * exclusivamente para o botão de validação manual do detalhe, mostrado só
 * quando a solicitação ainda não foi efetivamente aprovada (ADR-0010) — não
 * é chamado em nenhum outro fluxo da listagem ou do carregamento normal do
 * detalhe.
 */
@Injectable({ providedIn: 'root' })
export class MovimentacaoService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = API_BASE_URL;

  listar(params: ListarMovimentacoesParams): Observable<MovimentacaoListaResponse> {
    let httpParams = new HttpParams();
    if (params.page) httpParams = httpParams.set('page', params.page);
    if (params.pageSize) httpParams = httpParams.set('pageSize', params.pageSize);
    if (params.status) httpParams = httpParams.set('status', params.status);
    if (params.busca) httpParams = httpParams.set('busca', params.busca);
    if (params.ordenarPor) httpParams = httpParams.set('ordenarPor', params.ordenarPor);
    if (params.direcao) httpParams = httpParams.set('direcao', params.direcao);

    return this.http.get<MovimentacaoListaResponse>(`${this.baseUrl}/movimentacoes`, {
      params: httpParams
    });
  }

  buscarPorId(id: number): Observable<MovimentacaoDetalheResponse> {
    return this.http.get<MovimentacaoDetalheResponse>(`${this.baseUrl}/movimentacoes/${id}`);
  }

  /**
   * Validação manual sob demanda (botão "Validar agora" do detalhe).
   * Chama o adaptador síncrono técnico `POST /validar` — o mesmo
   * `ValidacaoService` usado pelo Worker — e por isso funciona
   * independentemente do Worker estar rodando ou não (ex.: Worker parado,
   * travado ou reiniciando): não depende da fila `JobValidacao` em nenhum
   * ponto.
   */
  validar(movimentacaoId: number): Observable<ValidarResponse> {
    return this.http.post<ValidarResponse>(`${this.baseUrl}/validar`, { movimentacaoId });
  }
}

export const RESULTADO_LABEL: Record<ResultadoValidacao, string> = {
  APROVADA: 'Aprovada',
  REPROVADA: 'Reprovada',
  AGUARDANDO_APROVACAO: 'Aguardando aprovação'
};

export const STATUS_LABEL: Record<StatusMovimentacao, string> = {
  PENDENTE: 'Pendente',
  APROVADA: 'Aprovada',
  REPROVADA: 'Reprovada'
};
