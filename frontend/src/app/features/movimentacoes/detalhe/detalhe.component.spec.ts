import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { MovimentacaoDetalheResponse } from '../../../core/models/movimentacao.model';
import { MovimentacaoService } from '../../../core/services/movimentacao.service';
import { DetalheComponent } from './detalhe.component';

function movimentacaoBase(overrides: Partial<MovimentacaoDetalheResponse> = {}): MovimentacaoDetalheResponse {
  return {
    id: 5,
    tipo: 'TRANSFERENCIA',
    status: 'PENDENTE',
    dataSolicitacao: '2026-01-01T10:00:00',
    colaborador: { id: 1, matricula: 'M000001', nome: 'Fulano', ativo: true },
    cargoAtual: null,
    cargoDestino: null,
    departamentoOrigem: { id: 1, codigo: 'DEP-A', nome: 'Operações', ativo: true },
    departamentoDestino: { id: 2, codigo: 'DEP-B', nome: 'Comercial', ativo: true },
    centroCustoOrigem: null,
    centroCustoDestino: null,
    estruturaOrigem: null,
    estruturaDestino: null,
    gestorOrigem: null,
    gestorDestino: null,
    aprovacoes: [],
    ultimaValidacao: null,
    ...overrides
  };
}

describe('DetalheComponent', () => {
  let fixture: ComponentFixture<DetalheComponent>;
  let component: DetalheComponent;
  let service: jasmine.SpyObj<MovimentacaoService>;

  function montar() {
    fixture = TestBed.createComponent(DetalheComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  beforeEach(async () => {
    service = jasmine.createSpyObj('MovimentacaoService', ['buscarPorId', 'validar']);
    service.buscarPorId.and.returnValue(of(movimentacaoBase()));

    await TestBed.configureTestingModule({
      imports: [DetalheComponent],
      providers: [
        { provide: MovimentacaoService, useValue: service },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: convertToParamMap({ id: '5' }) } }
        }
      ]
    }).compileComponents();
  });

  it('carrega a movimentação pelo id da rota', () => {
    montar();
    expect(service.buscarPorId).toHaveBeenCalledWith(5);
    expect(component.movimentacao()?.id).toBe(5);
  });

  it('exibe estado de erro quando a busca falha', () => {
    service.buscarPorId.and.returnValue(
      throwError(() => ({ error: { erro: { mensagem: 'não encontrada' } } }))
    );
    montar();
    expect(component.erro()).toContain('não encontrada');
  });

  it('CA-020: quando PENDENTE sem última validação, comunica aguardando aprovação/processamento sem sugerir ação', () => {
    service.buscarPorId.and.returnValue(of(movimentacaoBase({ status: 'PENDENTE', ultimaValidacao: null })));
    montar();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto.toLowerCase()).toContain('aguardando aprovação');
    expect(texto.toLowerCase()).not.toContain('validar movimentação');
  });

  it('CA-020: quando REPROVADA sem última validação, comunica bloqueio pelo gate de aprovação', () => {
    service.buscarPorId.and.returnValue(of(movimentacaoBase({ status: 'REPROVADA', ultimaValidacao: null })));
    montar();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto.toLowerCase()).toContain('bloqueada');
  });

  it('exibe a última validação e as inconsistências quando presentes', () => {
    service.buscarPorId.and.returnValue(
      of(
        movimentacaoBase({
          status: 'REPROVADA',
          ultimaValidacao: {
            resultado: 'REPROVADA',
            validadoEm: '2026-01-02T10:00:00',
            inconsistencias: [
              { codigo: 'T05', mensagem: 'Departamento de origem e destino são iguais', severidade: 'ERRO' }
            ]
          }
        })
      )
    );
    montar();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('T05');
    expect(texto).toContain('Departamento de origem e destino são iguais');
  });

  it('ADR-0010: exibe o botão "Validar agora" quando PENDENTE', () => {
    service.buscarPorId.and.returnValue(of(movimentacaoBase({ status: 'PENDENTE', ultimaValidacao: null })));
    montar();
    const botao = fixture.nativeElement.querySelector('button.primario') as HTMLButtonElement | null;
    expect(botao).not.toBeNull();
    expect(botao?.textContent).toContain('Validar agora');
  });

  it('ADR-0010: exibe o botão "Validar agora" quando REPROVADA (bloqueada)', () => {
    service.buscarPorId.and.returnValue(of(movimentacaoBase({ status: 'REPROVADA', ultimaValidacao: null })));
    montar();
    expect(fixture.nativeElement.querySelector('button.primario')).not.toBeNull();
  });

  it('ADR-0010: não exibe o botão "Validar agora" quando APROVADA', () => {
    service.buscarPorId.and.returnValue(
      of(
        movimentacaoBase({
          status: 'APROVADA',
          ultimaValidacao: { resultado: 'APROVADA', validadoEm: '2026-01-02T10:00:00', inconsistencias: [] }
        })
      )
    );
    montar();
    expect(fixture.nativeElement.querySelector('button.primario')).toBeNull();
  });

  it('ADR-0010: ao clicar em "Validar agora" com sucesso, chama validar() e recarrega o detalhe', () => {
    service.buscarPorId.and.returnValue(of(movimentacaoBase({ status: 'PENDENTE', ultimaValidacao: null })));
    service.validar.and.returnValue(
      of({ movimentacaoId: 5, status: 'AGUARDANDO_APROVACAO', validadoEm: '2026-01-03T10:00:00', inconsistencias: [] })
    );
    montar();

    component.validarAgora();

    expect(service.validar).toHaveBeenCalledWith(5);
    expect(service.buscarPorId).toHaveBeenCalledTimes(2);
    expect(component.validando()).toBeFalse();
    expect(component.erroValidacaoManual()).toBeNull();
  });

  it('ADR-0010: quando validar() falha, mostra a mensagem de erro e não recarrega', () => {
    service.buscarPorId.and.returnValue(of(movimentacaoBase({ status: 'PENDENTE', ultimaValidacao: null })));
    service.validar.and.returnValue(throwError(() => ({ error: { erro: { mensagem: 'Worker travado' } } })));
    montar();

    component.validarAgora();

    expect(component.erroValidacaoManual()).toBe('Worker travado');
    expect(component.validando()).toBeFalse();
    expect(service.buscarPorId).toHaveBeenCalledTimes(1);
  });

  it('ADR-0010: solicitação APROVADA mostra o histórico em vez da última validação, com a entrada ilustrativa marcada', () => {
    service.buscarPorId.and.returnValue(
      of(
        movimentacaoBase({
          status: 'APROVADA',
          dataSolicitacao: '2026-01-01T09:00:00',
          aprovacoes: [
            {
              tipo: 'GESTOR_ORIGEM',
              estado: 'APROVADA',
              aprovador: { id: 2, matricula: 'M000002', nome: 'Ciclana' },
              dataDecisao: '2026-01-01T11:00:00'
            }
          ],
          ultimaValidacao: { resultado: 'APROVADA', validadoEm: '2026-01-01T12:00:00', inconsistencias: [] }
        })
      )
    );
    montar();

    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('Histórico da solicitação');
    expect(texto).toContain('Aprovação GESTOR_ORIGEM concluída por Ciclana');
    expect(texto).toContain('Validação executada automaticamente');
    expect(texto).toContain('cenário ilustrativo');
    expect(fixture.nativeElement.querySelector('button.primario')).toBeNull();

    const itens = component.historico(component.movimentacao()!);
    expect(itens[itens.length - 1].ilustrativo).toBeTrue();
  });
});
