import { Component } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { Router, provideRouter } from '@angular/router';
import { TestBed } from '@angular/core/testing';

import { AppComponent } from './app.component';
import { AuthService } from './core/services/auth.service';

@Component({ standalone: true, template: '' })
class RotaFakeComponent {}

describe('AppComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideRouter([
          { path: '', component: RotaFakeComponent },
          { path: 'movimentacoes/nova', component: RotaFakeComponent },
          { path: 'aprovacoes', component: RotaFakeComponent }
        ]),
        provideHttpClient()
      ]
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the app title in the header', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.marca')?.textContent).toContain('Portal de Mobilidade Organizacional');
  });

  describe('T-83 — destaque de navegação ativa', () => {
    function autenticar(): void {
      const auth = TestBed.inject(AuthService);
      spyOn(auth, 'autenticado').and.returnValue(true);
      spyOn(auth, 'podeCriarSolicitacao').and.returnValue(true);
      spyOn(auth, 'podeAprovar').and.returnValue(true);
      spyOn(auth, 'usuario').and.returnValue({ id: 1, username: 'admin', perfil: 'ADMIN', scopes: [] });
    }

    it('marca "Movimentações" como ativo na rota raiz e nenhum outro item', async () => {
      autenticar();
      const fixture = TestBed.createComponent(AppComponent);
      const router = TestBed.inject(Router);
      fixture.detectChanges();
      await router.navigateByUrl('/');
      fixture.detectChanges();

      const links = fixture.nativeElement.querySelectorAll('.menu a');
      const ativos = Array.from(links as NodeListOf<HTMLElement>).filter((a) => a.classList.contains('ativo'));
      expect(ativos.length).toBe(1);
      expect(ativos[0].textContent).toContain('Movimentações');
    });

    it('move o destaque para "Nova solicitação" ao navegar, removendo do item anterior', async () => {
      autenticar();
      const fixture = TestBed.createComponent(AppComponent);
      const router = TestBed.inject(Router);
      await router.navigateByUrl('/');
      fixture.detectChanges();

      await router.navigateByUrl('/movimentacoes/nova');
      fixture.detectChanges();

      const links: HTMLElement[] = Array.from(fixture.nativeElement.querySelectorAll('.menu a'));
      const ativos = links.filter((a) => a.classList.contains('ativo'));
      expect(ativos.length).toBe(1);
      expect(ativos[0].textContent).toContain('Nova solicitação');
      const movimentacoesLink = links.find((a) => a.textContent?.includes('Movimentações'));
      expect(movimentacoesLink?.classList.contains('ativo')).toBeFalse();
    });

    it('marca "Aprovações" como ativo na rota /aprovacoes', async () => {
      autenticar();
      const fixture = TestBed.createComponent(AppComponent);
      const router = TestBed.inject(Router);
      fixture.detectChanges();
      await router.navigateByUrl('/aprovacoes');
      fixture.detectChanges();

      const links: HTMLElement[] = Array.from(fixture.nativeElement.querySelectorAll('.menu a'));
      const ativo = links.find((a) => a.classList.contains('ativo'));
      expect(ativo?.textContent).toContain('Aprovações');
    });
  });
});
