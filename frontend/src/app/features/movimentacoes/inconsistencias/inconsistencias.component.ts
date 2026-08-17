import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';

import { InconsistenciaResponse } from '../../../core/models/movimentacao.model';

@Component({
  selector: 'app-inconsistencias',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './inconsistencias.component.html',
  styleUrl: './inconsistencias.component.css'
})
export class InconsistenciasComponent {
  @Input() inconsistencias: InconsistenciaResponse[] = [];
}
