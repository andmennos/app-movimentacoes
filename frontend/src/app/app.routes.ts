import { Routes } from '@angular/router';

import { DetalheComponent } from './features/movimentacoes/detalhe/detalhe.component';
import { ListagemComponent } from './features/movimentacoes/listagem/listagem.component';

export const routes: Routes = [
  { path: '', component: ListagemComponent },
  { path: 'movimentacoes/:id', component: DetalheComponent },
  { path: '**', redirectTo: '' }
];
