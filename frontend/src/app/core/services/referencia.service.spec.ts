import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';

import { ReferenciaService } from './referencia.service';
import { API_BASE_URL } from './api-config';

describe('ReferenciaService', () => {
  let service: ReferenciaService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(ReferenciaService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('lista colaboradores em GET /colaboradores (já filtrado por BOLA no backend)', () => {
    service.listarColaboradores().subscribe();
    const req = httpMock.expectOne(`${API_BASE_URL}/colaboradores`);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('lista cargos em GET /referencias/cargos', () => {
    service.listarCargos().subscribe();
    const req = httpMock.expectOne(`${API_BASE_URL}/referencias/cargos`);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('lista departamentos em GET /referencias/departamentos', () => {
    service.listarDepartamentos().subscribe();
    const req = httpMock.expectOne(`${API_BASE_URL}/referencias/departamentos`);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('lista centros de custo em GET /referencias/centros-custo', () => {
    service.listarCentrosCusto().subscribe();
    const req = httpMock.expectOne(`${API_BASE_URL}/referencias/centros-custo`);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('lista estruturas em GET /referencias/estruturas', () => {
    service.listarEstruturas().subscribe();
    const req = httpMock.expectOne(`${API_BASE_URL}/referencias/estruturas`);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('T-86 — envia o termo de busca como query param ao autocompletar colaborador', () => {
    service.listarColaboradores('tanaka').subscribe();
    const req = httpMock.expectOne((r) => r.url === `${API_BASE_URL}/colaboradores` && r.params.get('busca') === 'tanaka');
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });
});
