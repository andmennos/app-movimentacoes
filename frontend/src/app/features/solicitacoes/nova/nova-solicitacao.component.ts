import { HttpErrorResponse } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged, switchMap } from 'rxjs';
import { forkJoin } from 'rxjs';

import {
  CargoResumo,
  CentroCustoResumo,
  ColaboradorResumo,
  DepartamentoResumo,
  EstruturaResumo
} from '../../../core/models/movimentacao.model';
import { CriarMovimentacaoRequest, TipoMovimentacaoCriavel } from '../../../core/models/solicitacao.model';
import { ReferenciaService } from '../../../core/services/referencia.service';
import { SolicitacaoService } from '../../../core/services/solicitacao.service';

const TIPOS: { valor: TipoMovimentacaoCriavel; rotulo: string }[] = [
  { valor: 'TRANSFERENCIA', rotulo: 'Transferência' },
  { valor: 'PROMOCAO', rotulo: 'Promoção' },
  { valor: 'MUDANCA_CENTRO_CUSTO', rotulo: 'Mudança de centro de custo' },
  { valor: 'TROCA_GESTOR', rotulo: 'Troca de gestor' },
  { valor: 'ALTERACAO_ESTRUTURA', rotulo: 'Alteração de estrutura' }
];

@Component({
  selector: 'app-nova-solicitacao',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './nova-solicitacao.component.html',
  styleUrl: './nova-solicitacao.component.css'
})
export class NovaSolicitacaoComponent implements OnInit {
  private readonly referencias = inject(ReferenciaService);
  private readonly solicitacoes = inject(SolicitacaoService);
  private readonly router = inject(Router);
  private readonly buscaColaboradorMudou = new Subject<string>();

  readonly tipos = TIPOS;

  readonly carregandoReferencias = signal(true);
  readonly enviando = signal(false);
  readonly erro = signal<string | null>(null);

  readonly departamentos = signal<DepartamentoResumo[]>([]);
  readonly cargos = signal<CargoResumo[]>([]);
  readonly centrosCusto = signal<CentroCustoResumo[]>([]);
  readonly estruturas = signal<EstruturaResumo[]>([]);
  readonly gestores = signal<ColaboradorResumo[]>([]);

  /** spec.md RC-49/T-86 — resultados do autocomplete de colaborador, vindos
   * já filtrados por BOLA do backend (`GET /colaboradores?busca=`). */
  readonly sugestoesColaborador = signal<ColaboradorResumo[]>([]);
  readonly buscandoColaborador = signal(false);

  tipo: TipoMovimentacaoCriavel = 'TRANSFERENCIA';
  colaboradorId: number | null = null;
  colaboradorTexto = '';
  destinoId: number | null = null;

  ngOnInit(): void {
    forkJoin({
      departamentos: this.referencias.listarDepartamentos(),
      cargos: this.referencias.listarCargos(),
      centrosCusto: this.referencias.listarCentrosCusto(),
      estruturas: this.referencias.listarEstruturas(),
      gestores: this.referencias.listarColaboradores()
    }).subscribe({
      next: (resultado) => {
        this.departamentos.set(resultado.departamentos);
        this.cargos.set(resultado.cargos);
        this.centrosCusto.set(resultado.centrosCusto);
        this.estruturas.set(resultado.estruturas);
        this.gestores.set(resultado.gestores);
        this.carregandoReferencias.set(false);
      },
      error: () => {
        this.erro.set('Não foi possível carregar os dados para o formulário. Tente novamente.');
        this.carregandoReferencias.set(false);
      }
    });

    this.buscaColaboradorMudou
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        switchMap((termo) => {
          if (!termo || termo.length < 2) {
            this.buscandoColaborador.set(false);
            return [];
          }
          this.buscandoColaborador.set(true);
          return this.referencias.listarColaboradores(termo);
        })
      )
      .subscribe({
        next: (resultado) => {
          this.sugestoesColaborador.set(resultado);
          this.buscandoColaborador.set(false);
        },
        error: () => this.buscandoColaborador.set(false)
      });
  }

  onTipoMudou(): void {
    this.destinoId = null;
  }

  onColaboradorTextoMudou(valor: string): void {
    this.colaboradorTexto = valor;
    this.colaboradorId = null;
    this.buscaColaboradorMudou.next(valor);
  }

  selecionarColaborador(colaborador: ColaboradorResumo): void {
    this.colaboradorId = colaborador.id;
    this.colaboradorTexto = `${colaborador.nome} (${colaborador.matricula})`;
    this.sugestoesColaborador.set([]);
  }

  enviar(): void {
    if (!this.colaboradorId || !this.destinoId) return;

    const payload = this.montarPayload();
    this.enviando.set(true);
    this.erro.set(null);
    this.solicitacoes.criar(payload).subscribe({
      next: (resposta) => {
        this.enviando.set(false);
        this.router.navigate(['/movimentacoes', resposta.id]);
      },
      error: (resposta: HttpErrorResponse) => {
        this.enviando.set(false);
        this.erro.set(
          resposta.error?.erro?.mensagem ?? 'Não foi possível enviar a solicitação. Tente novamente.'
        );
      }
    });
  }

  private montarPayload(): CriarMovimentacaoRequest {
    const colaboradorId = this.colaboradorId!;
    const destinoId = this.destinoId!;
    switch (this.tipo) {
      case 'TRANSFERENCIA':
        return { tipo: 'TRANSFERENCIA', colaboradorId, departamentoDestinoId: destinoId };
      case 'PROMOCAO':
        return { tipo: 'PROMOCAO', colaboradorId, cargoDestinoId: destinoId };
      case 'MUDANCA_CENTRO_CUSTO':
        return { tipo: 'MUDANCA_CENTRO_CUSTO', colaboradorId, centroCustoDestinoId: destinoId };
      case 'TROCA_GESTOR':
        return { tipo: 'TROCA_GESTOR', colaboradorId, gestorDestinoId: destinoId };
      case 'ALTERACAO_ESTRUTURA':
        return { tipo: 'ALTERACAO_ESTRUTURA', colaboradorId, estruturaDestinoId: destinoId };
    }
  }
}
