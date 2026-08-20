import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { MovimentacaoDetalheResponse } from '../../../core/models/movimentacao.model';
import {
  MovimentacaoService,
  RESULTADO_LABEL,
  STATUS_LABEL
} from '../../../core/services/movimentacao.service';
import { InconsistenciasComponent } from '../inconsistencias/inconsistencias.component';

@Component({
  selector: 'app-detalhe',
  standalone: true,
  imports: [CommonModule, RouterLink, InconsistenciasComponent],
  templateUrl: './detalhe.component.html',
  styleUrl: './detalhe.component.css'
})
export class DetalheComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly service = inject(MovimentacaoService);

  readonly statusLabel = STATUS_LABEL;
  readonly resultadoLabel = RESULTADO_LABEL;

  readonly carregando = signal(false);
  readonly erro = signal<string | null>(null);
  readonly movimentacao = signal<MovimentacaoDetalheResponse | null>(null);

  readonly validando = signal(false);
  readonly erroValidacaoManual = signal<string | null>(null);

  private movimentacaoId!: number;

  ngOnInit(): void {
    this.movimentacaoId = Number(this.route.snapshot.paramMap.get('id'));
    this.carregar();
  }

  carregar(): void {
    this.carregando.set(true);
    this.erro.set(null);
    this.service.buscarPorId(this.movimentacaoId).subscribe({
      next: (mov) => {
        this.movimentacao.set(mov);
        this.carregando.set(false);
      },
      error: (resposta) => {
        this.erro.set(
          resposta?.error?.erro?.mensagem ?? 'Não foi possível carregar esta movimentação.'
        );
        this.carregando.set(false);
      }
    });
  }

  /**
   * Validação manual sob demanda — o botão só aparece quando o backend
   * retorna `processamento.podeValidarManualmente=true` (RC-13); o Angular
   * nunca deriva essa elegibilidade a partir do status por conta própria.
   */
  validarAgora(): void {
    this.validando.set(true);
    this.erroValidacaoManual.set(null);
    this.service.validar(this.movimentacaoId).subscribe({
      next: () => {
        this.validando.set(false);
        this.carregar();
      },
      error: (resposta) => {
        this.validando.set(false);
        if (resposta?.status === 409) {
          // Conflito de negócio (o gate mudou, já em andamento ou já
          // concluída) — não é falha técnica: recarrega para refletir o
          // estado real que o backend já decidiu.
          this.carregar();
          return;
        }
        this.erroValidacaoManual.set(
          resposta?.error?.erro?.mensagem ??
            'Não foi possível se comunicar com o servidor. Tente novamente.'
        );
      }
    });
  }
}
