from datetime import datetime

from app.models import PerfilUsuario, Usuario

from .contador import proximo


class UsuarioBuilder:
    def __init__(self, **overrides):
        n = proximo()
        self.dados = dict(
            username=f"usuario{n:05d}",
            password_hash=f"hash-fake-{n:05d}",
            perfil=PerfilUsuario.ADMIN,
            colaborador_id=None,
            ativo=True,
            criado_em=datetime(2026, 1, 1, 9, 0, 0),
        )
        self.dados.update(overrides)

    def build(self, session) -> Usuario:
        obj = Usuario(**self.dados)
        session.add(obj)
        session.flush()
        return obj
