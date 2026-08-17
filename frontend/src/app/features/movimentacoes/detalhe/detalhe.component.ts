import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { MovimentacaoDetalheResponse, StatusMovimentacao } from '../../../core/models/movimentacao.model';
import {
  MovimentacaoService,
  RESULTADO_LABEL,
  STATUS_LABEL
} from '../../../core/services/movimentacao.service';
import { InconsistenciasComponent } from '../inconsistencias/inconsistencias.component';

/**
 * Mensagem exibida quando ainda não há última validação — distingue duas
 * situações de negócio distintas (spec §5.4). O botão de validação manual
 * (ver `podeValidarManualmente`) cobre exatamente estes dois casos.
 */
const MENSAGEM_POR_STATUS_SEM_VALIDACAO: Partial<Record<StatusMovimentacao, string>> = {
  PENDENTE:
    'Aguardando aprovação ou processamento. Assim que todas as aprovações exigidas forem concluídas, a validação é executada automaticamente pelo backend — ou clique em "Validar agora" para conferir na hora.',
  REPROVADA:
    'Bloqueada: uma aprovação exigida foi reprovada. A solicitação não avançou para a validação automática — clique em "Validar agora" para ver o resultado detalhado.'
};

/** Um evento do histórico ilustrativo de uma solicitação aprovada. */
export interface EventoHistorico {
  rotulo: string;
  dataHora: string;
  ilustrativo?: boolean;
}

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

  mensagemSemValidacao(status: StatusMovimentacao): string {
    return MENSAGEM_POR_STATUS_SEM_VALIDACAO[status] ?? 'Ainda não há resultado de validação.';
  }

  /**
   * O botão de validação manual só aparece para solicitações que ainda não
   * foram efetivamente aprovadas: pendente (aguardando aprovação ou uma
   * anomalia de integridade — ambas hoje se manifestam como `PENDENTE`) ou
   * bloqueada/reprovada. Uma vez `APROVADA`, o detalhe mostra o histórico em
   * vez do botão — não há "revalidar" um caso já efetivado neste MVP.
   */
  podeValidarManualmente(status: StatusMovimentacao): boolean {
    return status === 'PENDENTE' || status === 'REPROVADA';
  }

  /**
   * Valida sob demanda via `POST /validar` — o mesmo caso de uso síncrono
   * usado pelo Worker (ADR-0010). Funciona mesmo que o Worker esteja parado
   * ou tenha travado num job anterior: não depende da fila `JobValidacao`.
   * Mostra o resultado assim que a resposta chega e, em seguida, recarrega
   * o detalhe para manter aprovações/status sincronizados com o backend.
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
        this.erroValidacaoManual.set(
          resposta?.error?.erro?.mensagem ?? 'Não foi possível validar agora. Tente novamente.'
        );
      }
    });
  }

  /**
   * Histórico ilustrativo de uma solicitação aprovada: solicitação recebida,
   * cada aprovação concluída, a validação automática, e uma última entrada
   * explicitamente marcada como cenário imaginário — este MVP não implementa
   * efetivação real em sistemas corporativos (RC-11); a entrada existe só
   * para evidenciar, na narrativa da demonstração, que "aprovada" significa
   * pronta para seguir adiante, não apenas validada.
   */
  historico(mov: MovimentacaoDetalheResponse): EventoHistorico[] {
    const eventos: EventoHistorico[] = [
      { rotulo: `Solicitação de ${mov.tipo.toLowerCase()} recebida`, dataHora: mov.dataSolicitacao }
    ];

    for (const aprovacao of mov.aprovacoes) {
      if (aprovacao.dataDecisao) {
        const quem = aprovacao.aprovador ? ` por ${aprovacao.aprovador.nome}` : '';
        eventos.push({
          rotulo: `Aprovação ${aprovacao.tipo} concluída${quem}`,
          dataHora: aprovacao.dataDecisao
        });
      }
    }

    if (mov.ultimaValidacao) {
      eventos.push({
        rotulo: 'Validação executada automaticamente — Aprovada',
        dataHora: mov.ultimaValidacao.validadoEm
      });
      eventos.push({
        rotulo: 'Movimentação efetivada nos sistemas corporativos',
        dataHora: mov.ultimaValidacao.validadoEm,
        ilustrativo: true
      });
    }

    return eventos.sort((a, b) => new Date(a.dataHora).getTime() - new Date(b.dataHora).getTime());
  }
}
