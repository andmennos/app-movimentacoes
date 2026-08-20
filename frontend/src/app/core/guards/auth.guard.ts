import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from '../services/auth.service';

/**
 * spec.md §14.1 — protege rotas que exigem sessão. Só verifica presença de
 * token em memória; a validade real (assinatura/expiração/usuário ativo) é
 * sempre reconferida pelo backend em cada chamada (RC-16), nunca aqui.
 */
export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.autenticado()) {
    return true;
  }

  return router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
};
