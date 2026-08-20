import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';

import { SolicitacaoService } from './solicitacao.service';
import { API_BASE_URL } from './api-config';

describe('SolicitacaoService', () => {
  let service: SolicitacaoService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(SolicitacaoService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('cria uma transferência via POST /movimentacoes com o payload discriminado por tipo', () => {
    service.criar({ tipo: 'TRANSFERENCIA', colaboradorId: 10, departamentoDestinoId: 5 }).subscribe();

    const req = httpMock.expectOne(`${API_BASE_URL}/movimentacoes`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ tipo: 'TRANSFERENCIA', colaboradorId: 10, departamentoDestinoId: 5 });
    // O backend deriva origem/solicitante/status — o payload nunca os envia.
    expect(Object.keys(req.request.body)).toEqual(['tipo', 'colaboradorId', 'departamentoDestinoId']);
    req.flush({ id: 1, tipo: 'TRANSFERENCIA', status: 'AGUARDANDO_APROVACAO', dataSolicitacao: '2026-01-01T10:00:00' });
  });
});
