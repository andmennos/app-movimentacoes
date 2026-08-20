import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { AprovacaoPendenteResponse, DecidirAprovacaoRequest, DecidirAprovacaoResponse } from '../models/aprovacao.model';
import { TipoAprovacao } from '../models/movimentacao.model';
import { API_BASE_URL } from './api-config';

export interface ListarPendentesParams {
  busca?: string;
  ordenarPor?: string;
  direcao?: 'asc' | 'desc';
}

/**
 * spec.md §6/RC-51 — a tela de Aprovações só mostra o que
 * `GET /aprovacoes/pendentes` devolve (já filtrado por quem pode decidir o
 * quê, e ordenado/pesquisado pelo backend); o Angular nunca calcula ordem
 * nem elegibilidade por conta própria (spec §14.2).
 */
@Injectable({ providedIn: 'root' })
export class AprovacaoService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = API_BASE_URL;

  listarPendentes(params: ListarPendentesParams = {}): Observable<AprovacaoPendenteResponse[]> {
    let httpParams = new HttpParams();
    if (params.busca) httpParams = httpParams.set('busca', params.busca);
    if (params.ordenarPor) httpParams = httpParams.set('ordenarPor', params.ordenarPor);
    if (params.direcao) httpParams = httpParams.set('direcao', params.direcao);
    return this.http.get<AprovacaoPendenteResponse[]>(`${this.baseUrl}/aprovacoes/pendentes`, {
      params: httpParams
    });
  }

  decidir(
    movimentacaoId: number,
    tipo: TipoAprovacao,
    payload: DecidirAprovacaoRequest
  ): Observable<DecidirAprovacaoResponse> {
    return this.http.post<DecidirAprovacaoResponse>(
      `${this.baseUrl}/movimentacoes/${movimentacaoId}/aprovacoes/${tipo}/decidir`,
      payload
    );
  }
}
