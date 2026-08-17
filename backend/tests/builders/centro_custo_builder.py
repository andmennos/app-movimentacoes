from app.models import CentroCusto

from .contador import proximo
from .estrutura_builder import EstruturaOrganizacionalBuilder


class CentroCustoBuilder:
    def __init__(self, **overrides):
        n = proximo()
        self.dados = dict(
            codigo=f"CC{n:05d}",
            nome=f"Centro de Custo {n}",
            ativo=True,
            responsavel_id=None,
            estrutura_id=None,
        )
        self.dados.update(overrides)

    def build(self, session) -> CentroCusto:
        if self.dados.get("estrutura_id") is None:
            self.dados["estrutura_id"] = EstruturaOrganizacionalBuilder().build(session).id
        obj = CentroCusto(**self.dados)
        session.add(obj)
        session.flush()
        return obj
