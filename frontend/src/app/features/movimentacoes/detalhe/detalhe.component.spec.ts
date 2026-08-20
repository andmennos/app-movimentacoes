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
    solicitante: { id: 9, username: 'admin', perfil: 'ADMIN' },
    motivoResumo: 'Processamento pendente.',
    aprovacoes: [],
    ultimaValidacao: null,
    impedimentos: [],
    processamento: { estado: null, podeValidarManualmente: false, motivoValidacaoManual: null },
    historicoProcessamento: [],
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

  it('exibe os cinco status com seus rótulos', () => {
    const casos: MovimentacaoDetalheResponse['status'][] = [
      'AGUARDANDO_APROVACAO',
      'PENDENTE',
      'APROVADA',
      'REPROVADA',
      'BLOQUEADA'
    ];
    for (const status of casos) {
      service.buscarPorId.and.returnValue(of(movimentacaoBase({ status })));
      montar();
      const badge = fixture.nativeElement.querySelector('.badge-' + status);
      expect(badge).not.toBeNull();
    }
  });

  it('BLOQUEADA: exibe os impedimentos e não exibe "Nenhuma inconsistência encontrada"', () => {
    service.buscarPorId.and.returnValue(
      of(
        movimentacaoBase({
          status: 'BLOQUEADA',
          ultimaValidacao: null,
          impedimentos: [
            {
              origem: 'APROVACAO',
              codigo: 'APROVACAO_REPROVADA',
              mensagem: 'Aprovação GESTOR_ORIGEM reprovada por Felipe Almeida.'
            }
          ]
        })
      )
    );
    montar();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('Aprovação GESTOR_ORIGEM reprovada por Felipe Almeida.');
    expect(texto).not.toContain('Nenhuma inconsistência encontrada');
  });

  it('AGUARDANDO_APROVACAO: exibe os impedimentos e não exibe "Nenhuma inconsistência encontrada"', () => {
    service.buscarPorId.and.returnValue(
      of(
        movimentacaoBase({
          status: 'AGUARDANDO_APROVACAO',
          ultimaValidacao: null,
          impedimentos: [
            { origem: 'APROVACAO', codigo: 'APROVACAO_PENDENTE', mensagem: 'Aguardando aprovação GESTOR_DESTINO.' }
          ]
        })
      )
    );
    montar();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('Aguardando aprovação GESTOR_DESTINO.');
    expect(texto).not.toContain('Nenhuma inconsistência encontrada');
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

  it('exibe o botão "Validar agora" somente quando processamento.podeValidarManualmente é true', () => {
    service.buscarPorId.and.returnValue(
      of(movimentacaoBase({ status: 'PENDENTE', processamento: { estado: 'PENDENTE', podeValidarManualmente: true, motivoValidacaoManual: null } }))
    );
    montar();
    const botao = fixture.nativeElement.querySelector('button.primario') as HTMLButtonElement | null;
    expect(botao).not.toBeNull();
    expect(botao?.textContent).toContain('Validar agora');
  });

  it('não exibe o botão "Validar agora" quando podeValidarManualmente é false, mesmo em BLOQUEADA/REPROVADA/APROVADA/AGUARDANDO_APROVACAO', () => {
    const casos: MovimentacaoDetalheResponse['status'][] = [
      'BLOQUEADA',
      'REPROVADA',
      'APROVADA',
      'AGUARDANDO_APROVACAO'
    ];
    for (const status of casos) {
      service.buscarPorId.and.returnValue(
        of(
          movimentacaoBase({
            status,
            processamento: { estado: null, podeValidarManualmente: false, motivoValidacaoManual: null }
          })
        )
      );
      montar();
      expect(fixture.nativeElement.querySelector('button.primario')).toBeNull();
    }
  });

  it('não exibe nenhum texto auxiliar removido junto ao botão', () => {
    service.buscarPorId.and.returnValue(
      of(movimentacaoBase({ processamento: { estado: 'PENDENTE', podeValidarManualmente: true, motivoValidacaoManual: null } }))
    );
    montar();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).not.toContain('Roda a validação na hora');
    expect(texto).not.toContain('A validação é executada automaticamente pelo backend');
    expect(texto).not.toContain('cenário ilustrativo');
  });

  it('ao clicar em "Validar agora" com sucesso, chama validar() e recarrega o detalhe', () => {
    service.buscarPorId.and.returnValue(
      of(movimentacaoBase({ processamento: { estado: 'PENDENTE', podeValidarManualmente: true, motivoValidacaoManual: null } }))
    );
    service.validar.and.returnValue(
      of({ movimentacaoId: 5, status: 'APROVADA', validadoEm: '2026-01-03T10:00:00', inconsistencias: [] })
    );
    montar();

    component.validarAgora();

    expect(service.validar).toHaveBeenCalledWith(5);
    expect(service.buscarPorId).toHaveBeenCalledTimes(2);
    expect(component.validando()).toBeFalse();
    expect(component.erroValidacaoManual()).toBeNull();
  });

  it('em 409 (conflito de negócio), recarrega o detalhe sem mostrar erro técnico', () => {
    service.buscarPorId.and.returnValue(
      of(movimentacaoBase({ processamento: { estado: 'PENDENTE', podeValidarManualmente: true, motivoValidacaoManual: null } }))
    );
    service.validar.and.returnValue(
      throwError(() => ({
        status: 409,
        error: { erro: { codigo: 'VALIDACAO_MANUAL_NAO_PERMITIDA', mensagem: 'não permitida' } }
      }))
    );
    montar();

    component.validarAgora();

    expect(component.erroValidacaoManual()).toBeNull();
    expect(service.buscarPorId).toHaveBeenCalledTimes(2);
  });

  it('em erro 5xx/rede, mostra mensagem de erro transitória e não recarrega', () => {
    service.buscarPorId.and.returnValue(
      of(movimentacaoBase({ processamento: { estado: 'PENDENTE', podeValidarManualmente: true, motivoValidacaoManual: null } }))
    );
    service.validar.and.returnValue(throwError(() => ({ status: 500, error: { erro: { mensagem: 'Erro interno' } } })));
    montar();

    component.validarAgora();

    expect(component.erroValidacaoManual()).toBe('Erro interno');
    expect(component.validando()).toBeFalse();
    expect(service.buscarPorId).toHaveBeenCalledTimes(1);
  });

  it('renderiza o histórico de processamento real vindo do backend', () => {
    service.buscarPorId.and.returnValue(
      of(
        movimentacaoBase({
          status: 'APROVADA',
          ultimaValidacao: { resultado: 'APROVADA', validadoEm: '2026-01-02T10:00:00', inconsistencias: [] },
          historicoProcessamento: [
            {
              tipoEvento: 'SOLICITACAO_RECEBIDA',
              dataHora: '2026-01-01T09:00:00',
              origem: 'SISTEMA',
              mensagem: 'Solicitação de transferencia recebida.',
              detalheSanitizado: null,
              ator: null,
              solicitante: null
            },
            {
              tipoEvento: 'MOVIMENTACAO_EFETIVADA',
              dataHora: '2026-01-02T10:00:00',
              origem: 'AUTOMATICO',
              mensagem: 'Movimentação efetivada no cadastro do colaborador.',
              detalheSanitizado: null,
              ator: null,
              solicitante: null
            }
          ]
        })
      )
    );
    montar();

    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('Solicitação de transferencia recebida.');
    expect(texto).toContain('Movimentação efetivada no cadastro do colaborador.');
  });
});
