import { HttpErrorResponse } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  username = '';
  password = '';

  readonly entrando = signal(false);
  readonly erro = signal<string | null>(null);

  entrar(): void {
    if (!this.username || !this.password) return;

    this.entrando.set(true);
    this.erro.set(null);
    this.auth.login({ username: this.username, password: this.password }).subscribe({
      next: () => {
        this.entrando.set(false);
        const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl') ?? '/';
        this.router.navigateByUrl(returnUrl);
      },
      error: (resposta: HttpErrorResponse) => {
        this.entrando.set(false);
        this.password = '';
        this.erro.set(this.mensagemDeErro(resposta));
      }
    });
  }

  private mensagemDeErro(resposta: HttpErrorResponse): string {
    if (resposta.status === 429) {
      const retryAfter = resposta.headers.get('Retry-After');
      const minutos = retryAfter ? Math.ceil(Number(retryAfter) / 60) : null;
      return minutos
        ? `Muitas tentativas de login. Tente novamente em cerca de ${minutos} minuto(s).`
        : 'Muitas tentativas de login. Tente novamente mais tarde.';
    }
    if (resposta.status === 401) {
      return 'Usuário ou senha inválidos.';
    }
    return 'Não foi possível se comunicar com o servidor. Tente novamente.';
  }
}
