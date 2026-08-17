import { TestBed } from '@angular/core/testing';

import { InconsistenciasComponent } from './inconsistencias.component';

describe('InconsistenciasComponent', () => {
  it('exibe estado "sem inconsistências" quando a lista está vazia (CA-020)', async () => {
    await TestBed.configureTestingModule({ imports: [InconsistenciasComponent] }).compileComponents();
    const fixture = TestBed.createComponent(InconsistenciasComponent);
    fixture.componentInstance.inconsistencias = [];
    fixture.detectChanges();

    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('Nenhuma inconsistência encontrada');
  });

  it('exibe código e mensagem de cada inconsistência, exatamente como recebidos (CA-019)', async () => {
    await TestBed.configureTestingModule({ imports: [InconsistenciasComponent] }).compileComponents();
    const fixture = TestBed.createComponent(InconsistenciasComponent);
    fixture.componentInstance.inconsistencias = [
      { codigo: 'P03', mensagem: 'Cargo de destino não possui nível superior ao cargo atual', severidade: 'ERRO' },
      { codigo: 'P05', mensagem: 'Aprovação de RH ausente / aprovador inválido', severidade: 'ERRO' }
    ];
    fixture.detectChanges();

    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('P03');
    expect(texto).toContain('Cargo de destino não possui nível superior ao cargo atual');
    expect(texto).toContain('P05');
    expect(texto).toContain('Aprovação de RH ausente / aprovador inválido');
  });
});
