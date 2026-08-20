import { Routes } from '@angular/router';

import { authGuard } from './core/guards/auth.guard';
import { scopeGuard } from './core/guards/scope.guard';
import { AprovacoesComponent } from './features/aprovacoes/aprovacoes.component';
import { LoginComponent } from './features/auth/login/login.component';
import { DetalheComponent } from './features/movimentacoes/detalhe/detalhe.component';
import { ListagemComponent } from './features/movimentacoes/listagem/listagem.component';
import { NovaSolicitacaoComponent } from './features/solicitacoes/nova/nova-solicitacao.component';

export const routes: Routes = [
  { path: 'login', component: LoginComponent },
  { path: '', component: ListagemComponent, canActivate: [authGuard] },
  { path: 'movimentacoes/nova', component: NovaSolicitacaoComponent, canActivate: [authGuard] },
  { path: 'movimentacoes/:id', component: DetalheComponent, canActivate: [authGuard] },
  {
    path: 'aprovacoes',
    component: AprovacoesComponent,
    canActivate: [authGuard, scopeGuard('movimentacoes:approve')]
  },
  { path: '**', redirectTo: '' }
];
