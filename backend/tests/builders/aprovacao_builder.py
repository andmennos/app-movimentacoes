from datetime import datetime

from app.models import Aprovacao, EstadoAprovacao, TipoAprovacao

from .colaborador_builder import ColaboradorBuilder


class AprovacaoBuilder:
    def __init__(self, **overrides):
        self.dados = dict(
            movimentacao_id=None,
            tipo=TipoAprovacao.GESTOR_ORIGEM,
            estado=EstadoAprovacao.APROVADA,
            aprovador_id=None,
            data_decisao=datetime(2026, 1, 2, 9, 0, 0),
            justificativa=None,
        )
        self.dados.update(overrides)

    def build(self, session) -> Aprovacao:
        if self.dados["estado"] in (EstadoAprovacao.APROVADA, EstadoAprovacao.REPROVADA):
            if self.dados.get("aprovador_id") is None:
                self.dados["aprovador_id"] = ColaboradorBuilder().build(session).id
        else:
            self.dados["aprovador_id"] = None
            self.dados["data_decisao"] = None
        obj = Aprovacao(**self.dados)
        session.add(obj)
        session.flush()
        return obj
