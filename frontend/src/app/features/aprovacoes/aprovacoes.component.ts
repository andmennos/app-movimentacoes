import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';

import { AprovacaoPendenteResponse, DecisaoAprovacao } from '../../core/models/aprovacao.model';
import { AprovacaoService } from '../../core/services/aprovacao.service';

/** Chave estável de uma pendência: uma movimentação pode ter mais de uma etapa. */
function chaveDe(item: AprovacaoPendenteResponse): string {
  return `${item.movimentacaoId}:${item.tipo}`;
}

type Direcao = 'asc' | 'desc';

const CAMPOS_ORDENAVEIS: { valor: string; rotulo: string }[] = [
  { valor: 'id', rotulo: 'ID' },
  { valor: 'data_solicitacao', rotulo: 'Data da Solicitação' },
  { valor: 'tipo', rotulo: 'Tipo' },
  { valor: 'solicitante', rotulo: 'Solicitante' },
  { valor: 'colaborador', rotulo: 'Colaborador' },
  { valor: 'setor', rotulo: 'Setor' }
];

@Component({
  selector: 'app-aprovacoes',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './aprovacoes.component.html',
  styleUrl: './aprovacoes.component.css'
})
export class AprovacoesComponent implements OnInit {
  private readonly service = inject(AprovacaoService);
  private readonly buscaMudou = new Subject<string>();

  readonly campos = CAMPOS_ORDENAVEIS;

  readonly carregando = signal(false);
  readonly erro = signal<string | null>(null);
  readonly pendentes = signal<AprovacaoPendenteResponse[]>([]);

  readonly decidindo = signal<string | null>(null);
  readonly erroDecisao = signal<Record<string, string>>({});

  justificativas: Record<string, string> = {};

  busca = '';
  ordenarPor = 'data_solicitacao';
  direcao: Direcao = 'desc';

  ngOnInit(): void {
    this.buscaMudou.pipe(debounceTime(350), distinctUntilChanged()).subscribe(() => this.carregar());
    this.carregar();
  }

  chave = chaveDe;

  onBuscaMudou(valor: string): void {
    this.busca = valor;
    this.buscaMudou.next(valor);
  }

  ordenarPorCampo(campo: string): void {
    if (this.ordenarPor === campo) {
      this.direcao = this.direcao === 'asc' ? 'desc' : 'asc';
    } else {
      this.ordenarPor = campo;
      this.direcao = 'asc';
    }
    this.carregar();
  }

  carregar(): void {
    this.carregando.set(true);
    this.erro.set(null);
    this.service
      .listarPendentes({ busca: this.busca || undefined, ordenarPor: this.ordenarPor, direcao: this.direcao })
      .subscribe({
        next: (itens) => {
          this.pendentes.set(itens);
          this.carregando.set(false);
        },
        error: () => {
          this.erro.set('Não foi possível carregar as aprovações pendentes. Tente novamente.');
          this.carregando.set(false);
        }
      });
  }

  decidir(item: AprovacaoPendenteResponse, decisao: DecisaoAprovacao): void {
    const chave = chaveDe(item);
    this.decidindo.set(chave);
    this.erroDecisao.update((atual) => ({ ...atual, [chave]: '' }));

    const justificativa = this.justificativas[chave]?.trim();
    this.service
      .decidir(item.movimentacaoId, item.tipo, {
        decisao,
        ...(justificativa ? { justificativa } : {})
      })
      .subscribe({
        next: () => {
          this.decidindo.set(null);
          // Recarrega da API em vez de só remover o item local: decidir uma
          // etapa pode destravar a ordem (RC-35) de outra que antes não
          // aparecia (ex.: RH após GESTOR_ORIGEM, ou GERENCIA após RH no
          // bundle de T-75) — só a API sabe o que passou a ser acionável.
          this.carregar();
        },
        error: (resposta) => {
          this.decidindo.set(null);
          this.erroDecisao.update((atual) => ({
            ...atual,
            [chave]: resposta?.error?.erro?.mensagem ?? 'Não foi possível registrar a decisão.'
          }));
        }
      });
  }
}
