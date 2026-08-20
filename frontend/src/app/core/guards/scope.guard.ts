import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from '../services/auth.service';

/**
 * spec.md RC-39/T-77 — controla apenas navegação/UX para rotas com
 * capability específica (ex.: `/aprovacoes` requer `movimentacoes:approve`).
 * Usa exatamente os scopes devolvidos pelo backend em `/auth/login`/
 * `/auth/me` (`AuthService.temEscopo`) — nenhuma matriz de autorização
 * própria no Angular. O backend continua sendo a segurança real (RC-16):
 * mesmo sem este guard, cada rota da API reautoriza por conta própria.
 * Sem o escopo, redireciona para a rota permitida (`/`) sem expor a ação —
 * não há mensagem de "acesso negado" a esconder, a rota simplesmente não
 * aparece como destino de navegação.
 */
export function scopeGuard(escopo: string): CanActivateFn {
  return () => {
    const auth = inject(AuthService);
    const router = inject(Router);

    if (auth.temEscopo(escopo)) {
      return true;
    }

    return router.createUrlTree(['/']);
  };
}
