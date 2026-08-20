import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { LoginRequest, LoginResponse, UsuarioResponse } from '../models/auth.model';
import { API_BASE_URL } from './api-config';

/**
 * spec.md RC-15/§12.2 — o token nunca é persistido (sem `localStorage`);
 * fica só em memória (signal), então um reload completo da página exige
 * novo login (aceitável no MVP, plan.md §17.1).
 *
 * spec.md RC-39/T-77 — os scopes efetivos vêm de `/auth/login`/`/auth/me`
 * (backend, fonte única — `security/permissions.py::scopes_do_perfil`).
 * Este serviço não mantém nenhuma matriz `SCOPES_POR_PERFIL` própria;
 * `temEscopo`/`scopeGuard` só controlam navegação/UX — o backend sempre
 * reautoriza cada rota de verdade (RC-16).
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = API_BASE_URL;

  private readonly _token = signal<string | null>(null);
  private readonly _usuario = signal<UsuarioResponse | null>(null);

  readonly token = this._token.asReadonly();
  readonly usuario = this._usuario.asReadonly();
  readonly autenticado = computed(() => this._token() !== null);

  login(credenciais: LoginRequest): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${this.baseUrl}/auth/login`, credenciais).pipe(
      tap((resposta) => {
        this._token.set(resposta.accessToken);
        this._usuario.set(resposta.usuario);
      })
    );
  }

  logout(): void {
    this._token.set(null);
    this._usuario.set(null);
  }

  podeCriarSolicitacao(): boolean {
    return this.temEscopo('movimentacoes:create');
  }

  podeAprovar(): boolean {
    return this.temEscopo('movimentacoes:approve');
  }

  temEscopo(escopo: string): boolean {
    return this._usuario()?.scopes.includes(escopo) ?? false;
  }
}
