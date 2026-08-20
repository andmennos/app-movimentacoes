import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  CargoResumo,
  CentroCustoResumo,
  ColaboradorResumo,
  DepartamentoResumo,
  EstruturaResumo
} from '../models/movimentacao.model';
import { API_BASE_URL } from './api-config';

/**
 * spec.md §3.3/§4.2 — catálogos usados pela tela de Nova solicitação.
 * `listarColaboradores` já vem filtrado por BOLA pelo backend (RC-16): o
 * Angular nunca esconde/filtra colaboradores por conta própria, só exibe
 * o que a API devolve — inclusive quando filtrado por `busca` (RC-49,
 * autocomplete de nome/matrícula).
 */
@Injectable({ providedIn: 'root' })
export class ReferenciaService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = API_BASE_URL;

  listarColaboradores(busca?: string): Observable<ColaboradorResumo[]> {
    let params = new HttpParams();
    if (busca) params = params.set('busca', busca);
    return this.http.get<ColaboradorResumo[]>(`${this.baseUrl}/colaboradores`, { params });
  }

  listarCargos(): Observable<CargoResumo[]> {
    return this.http.get<CargoResumo[]>(`${this.baseUrl}/referencias/cargos`);
  }

  listarDepartamentos(): Observable<DepartamentoResumo[]> {
    return this.http.get<DepartamentoResumo[]>(`${this.baseUrl}/referencias/departamentos`);
  }

  listarCentrosCusto(): Observable<CentroCustoResumo[]> {
    return this.http.get<CentroCustoResumo[]>(`${this.baseUrl}/referencias/centros-custo`);
  }

  listarEstruturas(): Observable<EstruturaResumo[]> {
    return this.http.get<EstruturaResumo[]>(`${this.baseUrl}/referencias/estruturas`);
  }
}
