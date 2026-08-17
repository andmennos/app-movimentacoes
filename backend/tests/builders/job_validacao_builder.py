from datetime import datetime

from app.models import JobValidacao, StatusJob

from .movimentacao_builder import MovimentacaoBuilder


class JobValidacaoBuilder:
    def __init__(self, **overrides):
        self.dados = dict(
            movimentacao_id=None,
            status=StatusJob.PENDENTE,
            tentativas=0,
            criado_em=datetime(2026, 1, 1, 9, 0, 0),
            iniciado_em=None,
            finalizado_em=None,
            ultimo_erro=None,
        )
        self.dados.update(overrides)

    def build(self, session) -> JobValidacao:
        if self.dados.get("movimentacao_id") is None:
            self.dados["movimentacao_id"] = MovimentacaoBuilder().build(session).id
        obj = JobValidacao(**self.dados)
        session.add(obj)
        session.flush()
        return obj
