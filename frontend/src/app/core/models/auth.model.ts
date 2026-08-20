import { PerfilUsuario } from './movimentacao.model';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface UsuarioResponse {
  id: number;
  username: string;
  perfil: PerfilUsuario;
  /** spec.md RC-39/T-77 — scopes efetivos, vindos do backend (fonte única). */
  scopes: string[];
}

export interface LoginResponse {
  accessToken: string;
  tokenType: string;
  expiresIn: number;
  usuario: UsuarioResponse;
}
