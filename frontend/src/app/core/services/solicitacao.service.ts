import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { CriarMovimentacaoRequest, CriarMovimentacaoResponse } from '../models/solicitacao.model';
import { API_BASE_URL } from './api-config';

/**
 * spec.md §4.2 — o payload nunca inclui origem/solicitante/status; o
 * backend deriva tudo do JWT e do estado atual do colaborador. Esta tela
 * não implementa nenhuma lógica de política de aprovação (spec §14.2).
 */
@Injectable({ providedIn: 'root' })
export class SolicitacaoService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = API_BASE_URL;

  criar(payload: CriarMovimentacaoRequest): Observable<CriarMovimentacaoResponse> {
    return this.http.post<CriarMovimentacaoResponse>(`${this.baseUrl}/movimentacoes`, payload);
  }
}
