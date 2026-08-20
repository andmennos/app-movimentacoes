import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { Router, UrlTree, provideRouter } from '@angular/router';

import { AuthService } from '../services/auth.service';
import { authGuard } from './auth.guard';

describe('authGuard', () => {
  let auth: AuthService;
  let router: Router;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient()]
    });
    auth = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
  });

  function executar(url: string) {
    return TestBed.runInInjectionContext(() =>
      authGuard({} as never, { url } as never)
    );
  }

  it('permite navegação quando autenticado', () => {
    spyOn(auth, 'autenticado').and.returnValue(true);

    const resultado = executar('/movimentacoes/5');

    expect(resultado).toBeTrue();
  });

  it('redireciona para /login preservando returnUrl quando não autenticado', () => {
    spyOn(auth, 'autenticado').and.returnValue(false);
    spyOn(router, 'createUrlTree').and.callThrough();

    const resultado = executar('/aprovacoes') as UrlTree;

    expect(router.createUrlTree).toHaveBeenCalledWith(['/login'], {
      queryParams: { returnUrl: '/aprovacoes' }
    });
    expect(resultado).toBeTruthy();
  });
});
