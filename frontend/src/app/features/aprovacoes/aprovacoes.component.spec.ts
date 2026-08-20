import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';

import { AprovacaoPendenteResponse } from '../../core/models/aprovacao.model';
import { AprovacaoService } from '../../core/services/aprovacao.service';
import { AprovacoesComponent } from './aprovacoes.component';

function pendente(overrides: Partial<AprovacaoPendenteResponse> = {}): AprovacaoPendenteResponse {
  return {
    movimentacaoId: 1,
    tipo: 'GESTOR_ORIGEM',
    tipoMovimentacao: 'TRANSFERENCIA',
    ordem: 1,
    colaborador: { id: 1, matricula: 'M000001', nome: 'Fulano' },
    dataSolicitacao: '2026-01-01T10:00:00',
    solicitante: { id: 9, username: 'admin', perfil: 'ADMIN' },
    origem: 'Departamento A',
    destino: 'Departamento B',
    setor: 'Departamento A',
    ...overrides
  };
}

describe('AprovacoesComponent', () => {
  let fixture: ComponentFixture<AprovacoesComponent>;
  let component: AprovacoesComponent;
  let service: jasmine.SpyObj<AprovacaoService>;

  function montar() {
    fixture = TestBed.createComponent(AprovacoesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  beforeEach(async () => {
    service = jasmine.createSpyObj('AprovacaoService', ['listarPendentes', 'decidir']);
    service.listarPendentes.and.returnValue(of([]));

    await TestBed.configureTestingModule({
      imports: [AprovacoesComponent],
      providers: [provideRouter([]), { provide: AprovacaoService, useValue: service }]
    }).compileComponents();
  });

  it('carrega as pendências ao iniciar', () => {
    montar();
    expect(service.listarPendentes).toHaveBeenCalledTimes(1);
  });

  it('exibe estado vazio quando não há pendências', () => {
    montar();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('Nenhuma aprovação pendente');
  });

  it('renderiza as pendências retornadas', () => {
    service.listarPendentes.and.returnValue(of([pendente({ movimentacaoId: 1 }), pendente({ movimentacaoId: 2 })]));
    montar();
    expect(component.pendentes().length).toBe(2);
  });

  it('aprovar chama o serviço e recarrega a lista da API em caso de sucesso', () => {
    // RC-35/T-75 — decidir uma etapa pode destravar a ordem de outra que
    // antes não era acionável (ex.: RH após GESTOR_ORIGEM); por isso o
    // componente recarrega da API em vez de só remover o item local — a
    // 2ª chamada aqui devolve uma lista diferente da 1ª para provar isso.
    const item = pendente({ movimentacaoId: 1, tipo: 'GESTOR_ORIGEM' });
    const proximaEtapa = pendente({ movimentacaoId: 1, tipo: 'RH' });
    service.listarPendentes.and.returnValues(of([item]), of([proximaEtapa]));
    service.decidir.and.returnValue(
      of({ movimentacaoId: 1, tipo: 'GESTOR_ORIGEM', estado: 'APROVADA', dataDecisao: '2026-01-01T10:00:00', movimentacaoStatus: 'AGUARDANDO_APROVACAO' })
    );
    montar();

    component.decidir(item, 'APROVADA');

    expect(service.decidir).toHaveBeenCalledWith(1, 'GESTOR_ORIGEM', { decisao: 'APROVADA' });
    expect(service.listarPendentes).toHaveBeenCalledTimes(2);
    expect(component.pendentes()).toEqual([proximaEtapa]);
  });

  it('reprovar com justificativa inclui a justificativa no payload', () => {
    const item = pendente({ movimentacaoId: 1, tipo: 'RH' });
    service.listarPendentes.and.returnValue(of([item]));
    service.decidir.and.returnValue(
      of({ movimentacaoId: 1, tipo: 'RH', estado: 'REPROVADA', dataDecisao: '2026-01-01T10:00:00', movimentacaoStatus: 'BLOQUEADA' })
    );
    montar();
    component.justificativas['1:RH'] = 'não atende aos critérios';

    component.decidir(item, 'REPROVADA');

    expect(service.decidir).toHaveBeenCalledWith(1, 'RH', {
      decisao: 'REPROVADA',
      justificativa: 'não atende aos critérios'
    });
  });

  it('em erro na decisão (ex.: 409 dupla decisão), mantém o item na lista e mostra a mensagem', () => {
    const item = pendente({ movimentacaoId: 1, tipo: 'GESTOR_ORIGEM' });
    service.listarPendentes.and.returnValue(of([item]));
    service.decidir.and.returnValue(
      throwError(() => ({ error: { erro: { mensagem: 'Esta aprovação já foi decidida.' } } }))
    );
    montar();

    component.decidir(item, 'APROVADA');

    expect(component.pendentes().length).toBe(1);
    expect(component.erroDecisao()['1:GESTOR_ORIGEM']).toBe('Esta aprovação já foi decidida.');
  });

  describe('T-87 — tabela pesquisável e ordenável', () => {
    it('renderiza uma tabela com ID/Data/Tipo/Solicitante/Colaborador/Origem/Destino/Setor', () => {
      service.listarPendentes.and.returnValue(of([pendente({ movimentacaoId: 42 })]));
      montar();

      const cabecalhos: string[] = Array.from(
        (fixture.nativeElement as HTMLElement).querySelectorAll('.tabela thead th')
      ).map((th) => (th.textContent ?? '').replace(/\s+/g, ' ').trim());
      expect(cabecalhos).toEqual([
        'ID',
        'Data da Solicitação ▼', // ordenação padrão
        'Tipo',
        'Solicitante',
        'Colaborador',
        'Setor',
        'Origem',
        'Destino',
        'Justificativa',
        'Ações'
      ]);

      const linha = (fixture.nativeElement as HTMLElement).querySelector('.tabela tbody tr') as HTMLElement;
      const celulas: string[] = Array.from(linha.querySelectorAll('td')).map((td) =>
        (td.textContent ?? '').replace(/\s+/g, ' ').trim()
      );
      // T-87 — cada linha precisa ter exatamente uma célula por cabeçalho,
      // na mesma ordem, senão as colunas seguintes desalinham silenciosamente
      // (bug real pego só na verificação manual: a célula de Setor estava
      // ausente do template, empurrando Origem/Destino uma coluna para a
      // esquerda mesmo com os testes anteriores, que só checavam substring
      // solta em `linha.textContent`, passando verdes).
      expect(celulas.length).toBe(cabecalhos.length);
      expect(celulas[0]).toBe('42');
      expect(celulas[3]).toBe('admin');
      expect(celulas[4]).toContain('Fulano');
      expect(celulas[5]).toBe('Departamento A'); // Setor
      expect(celulas[6]).toBe('Departamento A'); // Origem
      expect(celulas[7]).toBe('Departamento B'); // Destino
    });

    it('busca dispara nova chamada ao serviço com o termo (com debounce)', fakeAsync(() => {
      montar();
      service.listarPendentes.calls.reset();

      component.onBuscaMudou('42');
      tick(400);

      expect(service.listarPendentes).toHaveBeenCalledWith(
        jasmine.objectContaining({ busca: '42' })
      );
    }));

    it('clicar em uma coluna ordenável alterna ordenarPor/direcao e recarrega', () => {
      montar();
      service.listarPendentes.calls.reset();

      component.ordenarPorCampo('colaborador');
      expect(component.ordenarPor).toBe('colaborador');
      expect(component.direcao).toBe('asc');
      expect(service.listarPendentes).toHaveBeenCalledWith(
        jasmine.objectContaining({ ordenarPor: 'colaborador', direcao: 'asc' })
      );

      service.listarPendentes.calls.reset();
      component.ordenarPorCampo('colaborador');
      expect(component.direcao).toBe('desc');
    });

    it('carrega com ordenação padrão data_solicitacao desc', () => {
      montar();
      expect(service.listarPendentes).toHaveBeenCalledWith(
        jasmine.objectContaining({ ordenarPor: 'data_solicitacao', direcao: 'desc' })
      );
    });

    it('botão Aprovar é azul (classe primario) e Reprovar é vermelho (classe perigo)', () => {
      service.listarPendentes.and.returnValue(of([pendente({ movimentacaoId: 1 })]));
      montar();

      const botoes: HTMLButtonElement[] = Array.from(
        (fixture.nativeElement as HTMLElement).querySelectorAll('.celula-acoes button')
      );
      expect(botoes[0].classList.contains('primario')).toBeTrue();
      expect(botoes[0].textContent?.trim()).toBe('Aprovar');
      expect(botoes[1].classList.contains('perigo')).toBeTrue();
      expect(botoes[1].textContent?.trim()).toBe('Reprovar');
    });
  });
});
