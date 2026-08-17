import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';

import {
  MovimentacaoItem,
  StatusMovimentacao
} from '../../../core/models/movimentacao.model';
import {
  MovimentacaoService,
  RESULTADO_LABEL,
  STATUS_LABEL
} from '../../../core/services/movimentacao.service';

type Direcao = 'asc' | 'desc';

const CAMPOS_ORDENAVEIS: { valor: string; rotulo: string }[] = [
  { valor: 'dataSolicitacao', rotulo: 'Data da solicitação' },
  { valor: 'tipo', rotulo: 'Tipo' },
  { valor: 'status', rotulo: 'Status' },
  { valor: 'colaboradorNome', rotulo: 'Colaborador' }
];

@Component({
  selector: 'app-listagem',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './listagem.component.html',
  styleUrl: './listagem.component.css'
})
export class ListagemComponent implements OnInit {
  private readonly service = inject(MovimentacaoService);
  private readonly router = inject(Router);
  private readonly buscaMudou = new Subject<string>();

  readonly campos = CAMPOS_ORDENAVEIS;
  readonly statusLabel = STATUS_LABEL;
  readonly resultadoLabel = RESULTADO_LABEL;

  readonly carregando = signal(false);
  readonly erro = signal<string | null>(null);
  readonly items = signal<MovimentacaoItem[]>([]);
  readonly page = signal(1);
  readonly pageSize = signal(20);
  readonly total = signal(0);
  readonly totalPages = signal(0);

  busca = '';
  status: StatusMovimentacao | '' = '';
  ordenarPor = 'dataSolicitacao';
  direcao: Direcao = 'desc';

  ngOnInit(): void {
    this.buscaMudou.pipe(debounceTime(350), distinctUntilChanged()).subscribe(() => {
      this.page.set(1);
      this.carregar();
    });
    this.carregar();
  }

  onBuscaMudou(valor: string): void {
    this.busca = valor;
    this.buscaMudou.next(valor);
  }

  onStatusMudou(): void {
    this.page.set(1);
    this.carregar();
  }

  ordenarPorCampo(campo: string): void {
    if (this.ordenarPor === campo) {
      this.direcao = this.direcao === 'asc' ? 'desc' : 'asc';
    } else {
      this.ordenarPor = campo;
      this.direcao = 'asc';
    }
    this.page.set(1);
    this.carregar();
  }

  irParaPagina(pagina: number): void {
    if (pagina < 1 || pagina > this.totalPages()) return;
    this.page.set(pagina);
    this.carregar();
  }

  abrirDetalhe(item: MovimentacaoItem): void {
    this.router.navigate(['/movimentacoes', item.id]);
  }

  /** Distingue, sem sugerir ação manual, por que ainda não há resultado de
   * validação (spec §5.4): bloqueada pelo gate de aprovação vs. aguardando
   * conclusão das aprovações/processamento automático. */
  textoSemValidacao(item: MovimentacaoItem): string {
    return item.status === 'REPROVADA' ? 'bloqueada (aprovação reprovada)' : 'aguardando aprovação/processamento';
  }

  carregar(): void {
    this.carregando.set(true);
    this.erro.set(null);
    this.service
      .listar({
        page: this.page(),
        pageSize: this.pageSize(),
        status: this.status || undefined,
        busca: this.busca || undefined,
        ordenarPor: this.ordenarPor,
        direcao: this.direcao
      })
      .subscribe({
        next: (resposta) => {
          this.items.set(resposta.items);
          this.page.set(resposta.page);
          this.pageSize.set(resposta.pageSize);
          this.total.set(resposta.total);
          this.totalPages.set(resposta.totalPages);
          this.carregando.set(false);
        },
        error: () => {
          this.erro.set('Não foi possível carregar a listagem de movimentações. Tente novamente.');
          this.carregando.set(false);
        }
      });
  }
}
