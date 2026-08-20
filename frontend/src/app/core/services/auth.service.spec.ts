import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';

import { AuthService } from './auth.service';
import { API_BASE_URL } from './api-config';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()]
    });
    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('começa sem sessão (token/usuário nulos, autenticado=false)', () => {
    expect(service.token()).toBeNull();
    expect(service.usuario()).toBeNull();
    expect(service.autenticado()).toBeFalse();
  });

  it('login com sucesso: POST /auth/login e guarda token/usuário só em memória', () => {
    service.login({ username: 'admin', password: 'admin' }).subscribe();

    const req = httpMock.expectOne(`${API_BASE_URL}/auth/login`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ username: 'admin', password: 'admin' });

    req.flush({
      accessToken: 'token-fake',
      tokenType: 'bearer',
      expiresIn: 1800,
      usuario: { id: 1, username: 'admin', perfil: 'ADMIN', scopes: ['movimentacoes:read'] }
    });

    expect(service.token()).toBe('token-fake');
    expect(service.usuario()?.username).toBe('admin');
    expect(service.autenticado()).toBeTrue();
  });

  it('login com credenciais inválidas (401): não autentica', () => {
    let capturouErro = false;
    service.login({ username: 'admin', password: 'errada' }).subscribe({
      error: () => (capturouErro = true)
    });

    httpMock
      .expectOne(`${API_BASE_URL}/auth/login`)
      .flush({ erro: { codigo: 'CREDENCIAIS_INVALIDAS', mensagem: 'Usuário ou senha inválidos.' } }, { status: 401, statusText: 'Unauthorized' });

    expect(capturouErro).toBeTrue();
    expect(service.autenticado()).toBeFalse();
  });

  it('login bloqueado (429): não autentica e propaga o erro', () => {
    let statusCapturado: number | undefined;
    service.login({ username: 'admin', password: 'admin' }).subscribe({
      error: (erro) => (statusCapturado = erro.status)
    });

    httpMock
      .expectOne(`${API_BASE_URL}/auth/login`)
      .flush(
        { erro: { codigo: 'LOGIN_BLOQUEADO', mensagem: 'Muitas tentativas.' } },
        { status: 429, statusText: 'Too Many Requests' }
      );

    expect(statusCapturado).toBe(429);
    expect(service.autenticado()).toBeFalse();
  });

  it('logout limpa token e usuário da memória', () => {
    service.login({ username: 'admin', password: 'admin' }).subscribe();
    httpMock.expectOne(`${API_BASE_URL}/auth/login`).flush({
      accessToken: 'token-fake',
      tokenType: 'bearer',
      expiresIn: 1800,
      usuario: { id: 1, username: 'admin', perfil: 'ADMIN', scopes: ['movimentacoes:read'] }
    });
    expect(service.autenticado()).toBeTrue();

    service.logout();

    expect(service.token()).toBeNull();
    expect(service.usuario()).toBeNull();
    expect(service.autenticado()).toBeFalse();
  });

  it('menu: usa exatamente os scopes devolvidos pelo backend, sem matriz própria', () => {
    // spec.md RC-39/T-77 — o Angular não decide "quem pode o quê" por
    // perfil; só lê a lista de scopes que o backend mandou.
    const SCOPES_POR_PERFIL_NO_BACKEND: Record<string, string[]> = {
      ADMIN: ['movimentacoes:read', 'movimentacoes:create', 'movimentacoes:approve', 'colaboradores:read'],
      RH_ANALISTA: ['movimentacoes:read', 'movimentacoes:create', 'colaboradores:read'],
      RH_GESTOR: ['movimentacoes:read', 'movimentacoes:approve', 'colaboradores:read']
    };
    const logarComo = (perfil: 'ADMIN' | 'RH_ANALISTA' | 'RH_GESTOR') => {
      service.login({ username: 'x', password: 'y' }).subscribe();
      httpMock.expectOne(`${API_BASE_URL}/auth/login`).flush({
        accessToken: 't',
        tokenType: 'bearer',
        expiresIn: 1800,
        usuario: { id: 1, username: 'x', perfil, scopes: SCOPES_POR_PERFIL_NO_BACKEND[perfil] }
      });
    };

    logarComo('ADMIN');
    expect(service.podeCriarSolicitacao()).toBeTrue();
    expect(service.podeAprovar()).toBeTrue();

    logarComo('RH_ANALISTA');
    expect(service.podeCriarSolicitacao()).toBeTrue();
    expect(service.podeAprovar()).toBeFalse();

    logarComo('RH_GESTOR');
    expect(service.podeCriarSolicitacao()).toBeFalse();
    expect(service.podeAprovar()).toBeTrue();
  });

  it('temEscopo: reflete exatamente a lista recebida do backend, sem fallback vazio silencioso', () => {
    expect(service.temEscopo('movimentacoes:approve')).toBeFalse();

    service.login({ username: 'x', password: 'y' }).subscribe();
    httpMock.expectOne(`${API_BASE_URL}/auth/login`).flush({
      accessToken: 't',
      tokenType: 'bearer',
      expiresIn: 1800,
      usuario: { id: 1, username: 'x', perfil: 'LIDERANCA', scopes: ['movimentacoes:read', 'movimentacoes:approve'] }
    });

    expect(service.temEscopo('movimentacoes:approve')).toBeTrue();
    expect(service.temEscopo('colaboradores:read')).toBeFalse();
  });
});
