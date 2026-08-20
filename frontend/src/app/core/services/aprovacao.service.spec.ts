import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';

import { AprovacaoService } from './aprovacao.service';
import { API_BASE_URL } from './api-config';

describe('AprovacaoService', () => {
  let service: AprovacaoService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(AprovacaoService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('lista pendentes em GET /aprovacoes/pendentes', () => {
    service.listarPendentes().subscribe();
    const req = httpMock.expectOne(`${API_BASE_URL}/aprovacoes/pendentes`);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('T-87 — envia busca/ordenarPor/direcao como query params', () => {
    service.listarPendentes({ busca: '42', ordenarPor: 'colaborador', direcao: 'asc' }).subscribe();
    const req = httpMock.expectOne(
      (r) =>
        r.url === `${API_BASE_URL}/aprovacoes/pendentes` &&
        r.params.get('busca') === '42' &&
        r.params.get('ordenarPor') === 'colaborador' &&
        r.params.get('direcao') === 'asc'
    );
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('decide uma aprovação em POST /movimentacoes/{id}/aprovacoes/{tipo}/decidir', () => {
    service.decidir(7, 'GESTOR_ORIGEM', { decisao: 'APROVADA', justificativa: 'ok' }).subscribe();

    const req = httpMock.expectOne(`${API_BASE_URL}/movimentacoes/7/aprovacoes/GESTOR_ORIGEM/decidir`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ decisao: 'APROVADA', justificativa: 'ok' });
    req.flush({
      movimentacaoId: 7,
      tipo: 'GESTOR_ORIGEM',
      estado: 'APROVADA',
      dataDecisao: '2026-01-01T10:00:00',
      movimentacaoStatus: 'PENDENTE'
    });
  });
});
