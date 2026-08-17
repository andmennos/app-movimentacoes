from app.models import Cargo

from .contador import proximo


class CargoBuilder:
    def __init__(self, **overrides):
        n = proximo()
        self.dados = dict(
            codigo=f"CARGO{n:05d}",
            nome=f"Cargo {n}",
            nivel=n,
            ativo=True,
            permite_gestao=False,
            aprovacao_adicional=None,
        )
        self.dados.update(overrides)

    def build(self, session) -> Cargo:
        obj = Cargo(**self.dados)
        session.add(obj)
        session.flush()
        return obj
