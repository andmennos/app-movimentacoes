from app.models import EstruturaOrganizacional

from .contador import proximo


class EstruturaOrganizacionalBuilder:
    def __init__(self, **overrides):
        n = proximo()
        self.dados = dict(
            codigo=f"EST{n:05d}",
            nome=f"Estrutura {n}",
            ativo=True,
            estrutura_pai_id=None,
            nivel=1,
        )
        self.dados.update(overrides)

    def build(self, session) -> EstruturaOrganizacional:
        obj = EstruturaOrganizacional(**self.dados)
        session.add(obj)
        session.flush()
        return obj
