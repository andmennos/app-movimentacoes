import { provideRouter } from '@angular/router';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { NEVER, of, throwError } from 'rxjs';

import { MovimentacaoItem, MovimentacaoListaResponse } from '../../../core/models/movimentacao.model';
import { MovimentacaoService } from '../../../core/services/movimentacao.service';
import { ListagemComponent } from './listagem.component';

function respostaVazia(): MovimentacaoListaResponse {
  return { items: [], page: 1, pageSize: 20, total: 0, totalPages: 0 };
}

function item(id: number): MovimentacaoItem {
  return {
    id,
    tipo: 'TRANSFERENCIA',
    status: 'PENDENTE',
    colaborador: { id: 1, matricula: 'M000001', nome: 'Fulano' },
    dataSolicitacao: '2026-01-01T10:00:00',
    resultadoUltimaValidacao: null,
    solicitante: { id: 9, username: 'admin', perfil: 'ADMIN' },
    motivoResumo: 'Processamento pendente.'
  };
}

describe('ListagemComponent', () => {
  let fixture: ComponentFixture<ListagemComponent>;
  let component: ListagemComponent;
  let service: jasmine.SpyObj<MovimentacaoService>;

  beforeEach(async () => {
    service = jasmine.createSpyObj('MovimentacaoService', ['listar']);
    service.listar.and.returnValue(of(respostaVazia()));

    await TestBed.configureTestingModule({
      imports: [ListagemComponent],
      providers: [provideRouter([]), { provide: MovimentacaoService, useValue: service }]
    }).compileComponents();

    fixture = TestBed.createComponent(ListagemComponent);
    component = fixture.componentInstance;
  });

  it('carrega a listagem ao iniciar', () => {
    fixture.detectChanges();
    expect(service.listar).toHaveBeenCalledTimes(1);
  });

  it('exibe estado de carregando enquanto a requisição está pendente', () => {
    service.listar.and.returnValue(NEVER);

    fixture.detectChanges();

    expect(component.carregando()).toBe(true);
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('Carregando movimentações');
  });

  it('exibe estado vazio quando não há itens', () => {
    fixture.detectChanges();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('Nenhuma movimentação encontrada');
  });

  it('exibe estado de erro quando a requisição falha', () => {
    service.listar.and.returnValue(throwError(() => new Error('falhou')));
    fixture.detectChanges();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('Não foi possível carregar');
  });

  it('renderiza os itens retornados (CA-016)', () => {
    service.listar.and.returnValue(
      of({ items: [item(1), item(2)], page: 1, pageSize: 20, total: 2, totalPages: 1 })
    );
    fixture.detectChanges();
    expect(component.items().length).toBe(2);
  });

  it('busca dispara uma nova chamada ao serviço com o termo (com debounce)', fakeAsync(() => {
    fixture.detectChanges();
    service.listar.calls.reset();

    component.onBuscaMudou('joão');
    tick(400);

    expect(service.listar).toHaveBeenCalledWith(
      jasmine.objectContaining({ busca: 'joão', page: 1 })
    );
  }));

  it('filtro de status reinicia a página e chama o serviço', () => {
    fixture.detectChanges();
    service.listar.calls.reset();

    component.status = 'REPROVADA';
    component.onStatusMudou();

    expect(service.listar).toHaveBeenCalledWith(jasmine.objectContaining({ status: 'REPROVADA', page: 1 }));
  });

  it('clicar em uma coluna ordenável alterna ordenarPor/direcao e recarrega', () => {
    fixture.detectChanges();
    service.listar.calls.reset();

    component.ordenarPorCampo('tipo');
    expect(component.ordenarPor).toBe('tipo');
    expect(component.direcao).toBe('asc');
    expect(service.listar).toHaveBeenCalledWith(jasmine.objectContaining({ ordenarPor: 'tipo', direcao: 'asc' }));

    service.listar.calls.reset();
    component.ordenarPorCampo('tipo');
    expect(component.direcao).toBe('desc');
  });

  it('T-84 — ID é a primeira coluna e aparece na primeira célula de cada linha', () => {
    service.listar.and.returnValue(
      of({ items: [item(42)], page: 1, pageSize: 20, total: 1, totalPages: 1 })
    );
    fixture.detectChanges();

    const cabecalhos: HTMLElement[] = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll('.tabela thead th')
    );
    expect(cabecalhos[0].textContent?.trim()).toBe('ID');

    const primeiraLinha = (fixture.nativeElement as HTMLElement).querySelector('.tabela tbody tr');
    const primeiraCelula = primeiraLinha?.querySelector('td');
    expect(primeiraCelula?.textContent?.trim()).toBe('42');
  });

  it('T-84 — busca envia o termo digitado independente de ser ID, matrícula ou nome', fakeAsync(() => {
    fixture.detectChanges();
    service.listar.calls.reset();

    component.onBuscaMudou('42');
    tick(400);

    expect(service.listar).toHaveBeenCalledWith(jasmine.objectContaining({ busca: '42', page: 1 }));
  }));

  it('T-84 — apenas a célula de motivo permite quebra de linha; as demais continuam centralizadas/sem quebra', () => {
    service.listar.and.returnValue(
      of({ items: [item(1)], page: 1, pageSize: 20, total: 1, totalPages: 1 })
    );
    fixture.detectChanges();

    const celulaMotivo = (fixture.nativeElement as HTMLElement).querySelector('.celula-motivo') as HTMLElement;
    const estiloMotivo = getComputedStyle(celulaMotivo);
    expect(estiloMotivo.whiteSpace).toBe('normal');

    const outraCelula = (fixture.nativeElement as HTMLElement).querySelector(
      '.tabela tbody tr td:not(.celula-motivo)'
    ) as HTMLElement;
    const estiloOutra = getComputedStyle(outraCelula);
    expect(estiloOutra.whiteSpace).toBe('nowrap');
    expect(estiloOutra.textAlign).toBe('center');
  });

  it('paginação navega para a página seguinte dentro dos limites', () => {
    service.listar.and.returnValue(
      of({ items: [item(1)], page: 1, pageSize: 20, total: 40, totalPages: 2 })
    );
    fixture.detectChanges();
    service.listar.calls.reset();

    component.irParaPagina(2);
    expect(service.listar).toHaveBeenCalledWith(jasmine.objectContaining({ page: 2 }));

    service.listar.calls.reset();
    component.irParaPagina(99); // fora do intervalo, não chama
    expect(service.listar).not.toHaveBeenCalled();
  });
});
