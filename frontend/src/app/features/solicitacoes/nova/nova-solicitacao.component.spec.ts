import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { ReferenciaService } from '../../../core/services/referencia.service';
import { SolicitacaoService } from '../../../core/services/solicitacao.service';
import { NovaSolicitacaoComponent } from './nova-solicitacao.component';

describe('NovaSolicitacaoComponent', () => {
  let fixture: ComponentFixture<NovaSolicitacaoComponent>;
  let component: NovaSolicitacaoComponent;
  let referencias: jasmine.SpyObj<ReferenciaService>;
  let solicitacoes: jasmine.SpyObj<SolicitacaoService>;
  let router: Router;

  function montar() {
    fixture = TestBed.createComponent(NovaSolicitacaoComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  beforeEach(async () => {
    referencias = jasmine.createSpyObj('ReferenciaService', [
      'listarColaboradores',
      'listarDepartamentos',
      'listarCargos',
      'listarCentrosCusto',
      'listarEstruturas'
    ]);
    referencias.listarColaboradores.and.returnValue(of([{ id: 1, matricula: 'M000001', nome: 'Fulano' }]));
    referencias.listarDepartamentos.and.returnValue(of([{ id: 5, codigo: 'DEP-A', nome: 'Operações', ativo: true }]));
    referencias.listarCargos.and.returnValue(of([{ id: 8, nome: 'Analista Pleno', nivel: 2 }]));
    referencias.listarCentrosCusto.and.returnValue(of([{ id: 3, codigo: 'CC-A', nome: 'CC Operações', ativo: true }]));
    referencias.listarEstruturas.and.returnValue(of([{ id: 7, codigo: 'EST-A', nome: 'Estrutura A', ativo: true }]));

    solicitacoes = jasmine.createSpyObj('SolicitacaoService', ['criar']);

    await TestBed.configureTestingModule({
      imports: [NovaSolicitacaoComponent],
      providers: [
        provideRouter([]),
        { provide: ReferenciaService, useValue: referencias },
        { provide: SolicitacaoService, useValue: solicitacoes }
      ]
    }).compileComponents();

    router = TestBed.inject(Router);
  });

  it('carrega departamentos/cargos/centros de custo/estruturas/gestores ao iniciar', () => {
    montar();
    expect(referencias.listarColaboradores).toHaveBeenCalled();
    expect(referencias.listarDepartamentos).toHaveBeenCalled();
    expect(referencias.listarCargos).toHaveBeenCalled();
    expect(referencias.listarCentrosCusto).toHaveBeenCalled();
    expect(referencias.listarEstruturas).toHaveBeenCalled();
    expect(component.gestores().length).toBe(1);
    expect(component.estruturas().length).toBe(1);
  });

  it('T-86 — exibe os cinco tipos criáveis', () => {
    montar();
    const valores = component.tipos.map((t) => t.valor);
    expect(valores).toEqual([
      'TRANSFERENCIA',
      'PROMOCAO',
      'MUDANCA_CENTRO_CUSTO',
      'TROCA_GESTOR',
      'ALTERACAO_ESTRUTURA'
    ]);
  });

  it('trocar o tipo limpa o destino selecionado', () => {
    montar();
    component.destinoId = 5;
    component.tipo = 'PROMOCAO';
    component.onTipoMudou();
    expect(component.destinoId).toBeNull();
  });

  it('envia TRANSFERENCIA com o payload correto e navega para o detalhe criado', () => {
    solicitacoes.criar.and.returnValue(
      of({ id: 99, tipo: 'TRANSFERENCIA', status: 'AGUARDANDO_APROVACAO', dataSolicitacao: '2026-01-01T10:00:00' })
    );
    spyOn(router, 'navigate');
    montar();

    component.tipo = 'TRANSFERENCIA';
    component.colaboradorId = 1;
    component.destinoId = 5;
    component.enviar();

    expect(solicitacoes.criar).toHaveBeenCalledWith({
      tipo: 'TRANSFERENCIA',
      colaboradorId: 1,
      departamentoDestinoId: 5
    });
    expect(router.navigate).toHaveBeenCalledWith(['/movimentacoes', 99]);
  });

  it('envia PROMOCAO com cargoDestinoId', () => {
    solicitacoes.criar.and.returnValue(
      of({ id: 100, tipo: 'PROMOCAO', status: 'AGUARDANDO_APROVACAO', dataSolicitacao: '2026-01-01T10:00:00' })
    );
    montar();

    component.tipo = 'PROMOCAO';
    component.colaboradorId = 1;
    component.destinoId = 8;
    component.enviar();

    expect(solicitacoes.criar).toHaveBeenCalledWith({ tipo: 'PROMOCAO', colaboradorId: 1, cargoDestinoId: 8 });
  });

  it('T-86 — envia TROCA_GESTOR com gestorDestinoId', () => {
    solicitacoes.criar.and.returnValue(
      of({ id: 101, tipo: 'TROCA_GESTOR', status: 'AGUARDANDO_APROVACAO', dataSolicitacao: '2026-01-01T10:00:00' })
    );
    montar();

    component.tipo = 'TROCA_GESTOR';
    component.colaboradorId = 1;
    component.destinoId = 42;
    component.enviar();

    expect(solicitacoes.criar).toHaveBeenCalledWith({
      tipo: 'TROCA_GESTOR',
      colaboradorId: 1,
      gestorDestinoId: 42
    });
  });

  it('T-86 — envia ALTERACAO_ESTRUTURA com estruturaDestinoId', () => {
    solicitacoes.criar.and.returnValue(
      of({
        id: 102,
        tipo: 'ALTERACAO_ESTRUTURA',
        status: 'AGUARDANDO_APROVACAO',
        dataSolicitacao: '2026-01-01T10:00:00'
      })
    );
    montar();

    component.tipo = 'ALTERACAO_ESTRUTURA';
    component.colaboradorId = 1;
    component.destinoId = 7;
    component.enviar();

    expect(solicitacoes.criar).toHaveBeenCalledWith({
      tipo: 'ALTERACAO_ESTRUTURA',
      colaboradorId: 1,
      estruturaDestinoId: 7
    });
  });

  it('não envia quando colaborador ou destino não estão selecionados', () => {
    montar();
    component.colaboradorId = null;
    component.destinoId = null;
    component.enviar();
    expect(solicitacoes.criar).not.toHaveBeenCalled();
  });

  it('em erro do backend, mostra mensagem e não navega', () => {
    solicitacoes.criar.and.returnValue(
      throwError(() => ({ error: { erro: { mensagem: 'Colaborador fora do escopo.' } } }))
    );
    spyOn(router, 'navigate');
    montar();

    component.tipo = 'TRANSFERENCIA';
    component.colaboradorId = 1;
    component.destinoId = 5;
    component.enviar();

    expect(component.erro()).toBe('Colaborador fora do escopo.');
    expect(router.navigate).not.toHaveBeenCalled();
  });

  describe('T-86 — autocomplete de colaborador', () => {
    it('digitar ao menos 2 caracteres busca sugestões no backend (com debounce)', fakeAsync(() => {
      referencias.listarColaboradores.calls.reset();
      referencias.listarColaboradores.and.returnValue(
        of([{ id: 2, matricula: 'M000002', nome: 'Priscila Tanaka' }])
      );
      montar();
      referencias.listarColaboradores.calls.reset();

      component.onColaboradorTextoMudou('ta');
      tick(300);

      expect(referencias.listarColaboradores).toHaveBeenCalledWith('ta');
      expect(component.sugestoesColaborador().length).toBe(1);
    }));

    it('não busca com menos de 2 caracteres e limpa sugestões', fakeAsync(() => {
      montar();
      referencias.listarColaboradores.calls.reset();

      component.onColaboradorTextoMudou('t');
      tick(300);

      expect(referencias.listarColaboradores).not.toHaveBeenCalled();
      expect(component.sugestoesColaborador().length).toBe(0);
    }));

    it('selecionar uma sugestão define colaboradorId e preenche o texto', () => {
      montar();
      component.selecionarColaborador({ id: 2, matricula: 'M000002', nome: 'Priscila Tanaka' });

      expect(component.colaboradorId).toBe(2);
      expect(component.colaboradorTexto).toBe('Priscila Tanaka (M000002)');
      expect(component.sugestoesColaborador().length).toBe(0);
    });

    it('digitar de novo depois de selecionar limpa o colaboradorId (obriga nova seleção)', () => {
      montar();
      component.selecionarColaborador({ id: 2, matricula: 'M000002', nome: 'Priscila Tanaka' });
      component.onColaboradorTextoMudou('Priscila Tan');

      expect(component.colaboradorId).toBeNull();
    });
  });
});
