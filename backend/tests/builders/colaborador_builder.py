from datetime import date

from app.models import Colaborador

from .cargo_builder import CargoBuilder
from .centro_custo_builder import CentroCustoBuilder
from .contador import proximo
from .departamento_builder import DepartamentoBuilder


class ColaboradorBuilder:
    def __init__(self, **overrides):
        n = proximo()
        self.dados = dict(
            matricula=f"M{n:06d}",
            nome=f"Colaborador {n}",
            ativo=True,
            cargo_id=None,
            departamento_id=None,
            centro_custo_id=None,
            gestor_id=None,
            data_admissao=date(2020, 1, 1),
        )
        self.dados.update(overrides)

    def build(self, session) -> Colaborador:
        if self.dados.get("cargo_id") is None:
            self.dados["cargo_id"] = CargoBuilder().build(session).id
        if self.dados.get("departamento_id") is None:
            self.dados["departamento_id"] = DepartamentoBuilder().build(session).id
        if self.dados.get("centro_custo_id") is None:
            self.dados["centro_custo_id"] = CentroCustoBuilder().build(session).id
        obj = Colaborador(**self.dados)
        session.add(obj)
        session.flush()
        return obj
