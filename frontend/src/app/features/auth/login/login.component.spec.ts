import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';

import { AuthService } from '../../../core/services/auth.service';
import { LoginComponent } from './login.component';

describe('LoginComponent', () => {
  let fixture: ComponentFixture<LoginComponent>;
  let component: LoginComponent;
  let auth: jasmine.SpyObj<AuthService>;
  let router: Router;

  function montar() {
    fixture = TestBed.createComponent(LoginComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }

  beforeEach(async () => {
    auth = jasmine.createSpyObj('AuthService', ['login']);

    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: auth },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { queryParamMap: convertToParamMap({}) } }
        }
      ]
    }).compileComponents();

    router = TestBed.inject(Router);
  });

  it('login com sucesso: navega para "/" quando não há returnUrl', () => {
    auth.login.and.returnValue(
      of({
        accessToken: 't',
        tokenType: 'bearer',
        expiresIn: 1800,
        usuario: { id: 1, username: 'admin', perfil: 'ADMIN', scopes: ['movimentacoes:read'] }
      })
    );
    spyOn(router, 'navigateByUrl');
    montar();

    component.username = 'admin';
    component.password = 'admin';
    component.entrar();

    expect(auth.login).toHaveBeenCalledWith({ username: 'admin', password: 'admin' });
    expect(router.navigateByUrl).toHaveBeenCalledWith('/');
    expect(component.erro()).toBeNull();
  });

  it('senha errada (401): mostra mensagem genérica e limpa a senha', () => {
    auth.login.and.returnValue(throwError(() => ({ status: 401 })));
    montar();

    component.username = 'admin';
    component.password = 'errada';
    component.entrar();

    expect(component.erro()).toBe('Usuário ou senha inválidos.');
    expect(component.password).toBe('');
    expect(component.entrando()).toBeFalse();
  });

  it('bloqueado por força bruta (429): mostra mensagem com tempo de espera', () => {
    auth.login.and.returnValue(
      throwError(() => ({ status: 429, headers: { get: (nome: string) => (nome === 'Retry-After' ? '1800' : null) } }))
    );
    montar();

    component.username = 'admin';
    component.password = 'admin';
    component.entrar();

    expect(component.erro()).toContain('Muitas tentativas');
    expect(component.erro()).toContain('30 minuto');
  });

  it('não chama login() quando usuário ou senha estão vazios', () => {
    montar();
    component.username = '';
    component.password = '';
    component.entrar();
    expect(auth.login).not.toHaveBeenCalled();
  });
});
