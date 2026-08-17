import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';

import { MovimentacaoService } from './movimentacao.service';
import { API_BASE_URL } from './api-config';

describe('MovimentacaoService', () => {
  let service: MovimentacaoService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()]
    });
    service = TestBed.inject(MovimentacaoService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('monta a query string de listagem com os parâmetros informados', () => {
    service
      .listar({ page: 2, pageSize: 50, status: 'REPROVADA', busca: 'ana', ordenarPor: 'tipo', direcao: 'asc' })
      .subscribe();

    const req = httpMock.expectOne(
      (r) => r.url === `${API_BASE_URL}/movimentacoes`
    );
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('page')).toBe('2');
    expect(req.request.params.get('pageSize')).toBe('50');
    expect(req.request.params.get('status')).toBe('REPROVADA');
    expect(req.request.params.get('busca')).toBe('ana');
    expect(req.request.params.get('ordenarPor')).toBe('tipo');
    expect(req.request.params.get('direcao')).toBe('asc');
    req.flush({ items: [], page: 2, pageSize: 50, total: 0, totalPages: 0 });
  });

  it('omite parâmetros não informados', () => {
    service.listar({}).subscribe();

    const req = httpMock.expectOne(`${API_BASE_URL}/movimentacoes`);
    expect(req.request.params.keys().length).toBe(0);
    req.flush({ items: [], page: 1, pageSize: 20, total: 0, totalPages: 0 });
  });

  it('busca uma movimentação por id', () => {
    service.buscarPorId(42).subscribe((resp) => expect(resp.id).toBe(42));

    const req = httpMock.expectOne(`${API_BASE_URL}/movimentacoes/42`);
    expect(req.request.method).toBe('GET');
    req.flush({ id: 42 });
  });

  it('nenhuma requisição é feita para /validar durante o uso normal (listar/buscarPorId)', () => {
    // O gatilho normal do produto é automático (producer + Worker) — listar()
    // e buscarPorId() nunca disparam validação por conta própria. `validar()`
    // (ADR-0010) só é chamado explicitamente pelo botão de validação manual.
    service.listar({}).subscribe();
    httpMock.expectOne(`${API_BASE_URL}/movimentacoes`).flush({ items: [], page: 1, pageSize: 20, total: 0, totalPages: 0 });

    service.buscarPorId(1).subscribe();
    httpMock.expectOne(`${API_BASE_URL}/movimentacoes/1`).flush({ id: 1 });

    const chamadasParaValidar = httpMock.match(`${API_BASE_URL}/validar`);
    expect(chamadasParaValidar.length).toBe(0);
  });

  it('ADR-0010: validar() faz POST /validar com o id da movimentação e repassa a resposta', () => {
    let resposta: unknown;
    service.validar(7).subscribe((r) => (resposta = r));

    const req = httpMock.expectOne(`${API_BASE_URL}/validar`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ movimentacaoId: 7 });

    const corpo = {
      movimentacaoId: 7,
      status: 'REPROVADA',
      validadoEm: '2026-01-01T10:00:00',
      inconsistencias: [{ codigo: 'T05', mensagem: 'Departamento de origem e destino são iguais', severidade: 'ERRO' }]
    };
    req.flush(corpo);
    expect(resposta).toEqual(corpo);
  });
});
