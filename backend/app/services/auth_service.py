"""Login — spec.md §2.2/§12/plan.md §6.5.

Fluxo único: IP bloqueado? -> 429. Senão busca usuário, verifica hash,
incrementa/limpa lockout, emite JWT em caso de sucesso. Resposta de
credencial inválida é genérica (não revela se o username existe) — a
checagem "usuário não existe" e "senha errada" passam pelo mesmo caminho.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Usuario
from app.repositories import security_lockout_repository as lockout_repo
from app.repositories import usuario_repository
from app.security.jwt import create_access_token
from app.security.passwords import verify_password
from app.services.exceptions import CredenciaisInvalidas, LoginBloqueado

_HASH_FANTASMA = (
    "$argon2id$v=19$m=65536,t=3,p=4$MDAwMDAwMDAwMDAwMDAwMA$"
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA"
)
"""Hash usado quando o username não existe, para que `verify_password` gaste
tempo comparável ao caso "usuário existe, senha errada" (mitiga timing/
enumeração de usuários — spec §12.1: resposta não revela existência)."""


def login(session: Session, username: str, senha: str, ip: str, agora: datetime) -> tuple[str, int, Usuario]:
    bloqueado_por = lockout_repo.segundos_bloqueado_restantes(session, ip, agora)
    if bloqueado_por is not None:
        raise LoginBloqueado(bloqueado_por)

    usuario = usuario_repository.buscar_por_username(session, username)
    hash_para_verificar = usuario.password_hash if usuario is not None else _HASH_FANTASMA
    senha_confere = verify_password(senha, hash_para_verificar)

    if usuario is None or not usuario.ativo or not senha_confere:
        lockout_repo.registrar_falha(session, ip, agora)
        session.commit()
        raise CredenciaisInvalidas()

    lockout_repo.limpar_falhas(session, ip, agora)
    session.commit()

    token, expires_in = create_access_token(usuario.id, usuario.perfil.value)
    return token, expires_in, usuario
