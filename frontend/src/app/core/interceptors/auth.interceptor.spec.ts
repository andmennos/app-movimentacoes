import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { AuthService } from '../services/auth.service';
import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let auth: AuthService;
  let router: Router;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting()
      ]
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
  });

  afterEach(() => httpMock.verify());

  it('anexa o header Authorization quando há token em memória', () => {
    spyOn(auth, 'token').and.returnValue('token-fake');

    http.get('http://localhost:8000/movimentacoes').subscribe();

    const req = httpMock.expectOne('http://localhost:8000/movimentacoes');
    expect(req.request.headers.get('Authorization')).toBe('Bearer token-fake');
    req.flush({});
  });

  it('não anexa Authorization quando não há sessão', () => {
    spyOn(auth, 'logout');
    spyOn(router, 'navigate');

    http.get('http://localhost:8000/movimentacoes').subscribe({ error: () => {} });

    const req = httpMock.expectOne('http://localhost:8000/movimentacoes');
    expect(req.request.headers.has('Authorization')).toBeFalse();
    req.flush({}, { status: 401, statusText: 'Unauthorized' });
  });

  it('em 401 fora de /auth/login: limpa a sessão e navega para /login', () => {
    spyOn(auth, 'logout');
    spyOn(router, 'navigate');

    http.get('http://localhost:8000/movimentacoes').subscribe({ error: () => {} });
    httpMock.expectOne('http://localhost:8000/movimentacoes').flush(
      { erro: { codigo: 'TOKEN_INVALIDO', mensagem: 'expirado' } },
      { status: 401, statusText: 'Unauthorized' }
    );

    expect(auth.logout).toHaveBeenCalled();
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  });

  it('em 401 na própria chamada de /auth/login: não desloga nem redireciona (evita loop)', () => {
    spyOn(auth, 'logout');
    spyOn(router, 'navigate');

    http.post('http://localhost:8000/auth/login', {}).subscribe({ error: () => {} });
    httpMock.expectOne('http://localhost:8000/auth/login').flush(
      { erro: { codigo: 'CREDENCIAIS_INVALIDAS', mensagem: 'inválidas' } },
      { status: 401, statusText: 'Unauthorized' }
    );

    expect(auth.logout).not.toHaveBeenCalled();
    expect(router.navigate).not.toHaveBeenCalled();
  });

  it('em 429 (rate limit): não desloga, só propaga o erro', () => {
    spyOn(auth, 'logout');

    let statusCapturado: number | undefined;
    http.get('http://localhost:8000/movimentacoes').subscribe({ error: (e) => (statusCapturado = e.status) });
    httpMock
      .expectOne('http://localhost:8000/movimentacoes')
      .flush({ erro: { codigo: 'RATE_LIMIT_EXCEDIDO', mensagem: 'muitas' } }, { status: 429, statusText: 'Too Many Requests' });

    expect(statusCapturado).toBe(429);
    expect(auth.logout).not.toHaveBeenCalled();
  });
});
