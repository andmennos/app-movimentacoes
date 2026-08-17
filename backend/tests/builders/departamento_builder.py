from app.models import Departamento

from .contador import proximo
from .estrutura_builder import EstruturaOrganizacionalBuilder


class DepartamentoBuilder:
    def __init__(self, **overrides):
        n = proximo()
        self.dados = dict(
            codigo=f"DEP{n:05d}",
            nome=f"Departamento {n}",
            ativo=True,
            gestor_id=None,
            estrutura_id=None,
        )
        self.dados.update(overrides)

    def build(self, session) -> Departamento:
        if self.dados.get("estrutura_id") is None:
            self.dados["estrutura_id"] = EstruturaOrganizacionalBuilder().build(session).id
        obj = Departamento(**self.dados)
        session.add(obj)
        session.flush()
        return obj
