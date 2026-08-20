import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { Router, UrlTree, provideRouter } from '@angular/router';

import { AuthService } from '../services/auth.service';
import { scopeGuard } from './scope.guard';

describe('scopeGuard', () => {
  let auth: AuthService;
  let router: Router;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient()]
    });
    auth = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
  });

  function executar(escopo: string) {
    const guard = scopeGuard(escopo);
    return TestBed.runInInjectionContext(() => guard({} as never, {} as never));
  }

  it('permite navegação quando o usuário tem o escopo exigido', () => {
    spyOn(auth, 'temEscopo').and.returnValue(true);

    const resultado = executar('movimentacoes:approve');

    expect(resultado).toBeTrue();
  });

  it('redireciona para "/" sem expor a ação quando falta o escopo (ex.: analistaRh em /aprovacoes)', () => {
    spyOn(auth, 'temEscopo').and.returnValue(false);
    spyOn(router, 'createUrlTree').and.callThrough();

    const resultado = executar('movimentacoes:approve') as UrlTree;

    expect(router.createUrlTree).toHaveBeenCalledWith(['/']);
    expect(resultado).toBeTruthy();
  });

  it('consulta exatamente o escopo pedido pela rota, não uma lista fixa', () => {
    const spy = spyOn(auth, 'temEscopo').and.returnValue(true);

    executar('movimentacoes:create');

    expect(spy).toHaveBeenCalledWith('movimentacoes:create');
  });
});
