from datetime import datetime

from app.models import Colaborador, Movimentacao, StatusMovimentacao, TipoMovimentacao

from .cargo_builder import CargoBuilder
from .centro_custo_builder import CentroCustoBuilder
from .colaborador_builder import ColaboradorBuilder
from .contador import proximo
from .departamento_builder import DepartamentoBuilder
from .estrutura_builder import EstruturaOrganizacionalBuilder


class MovimentacaoBuilder:
    """Constrói uma Movimentacao válida por padrão: os campos obrigatórios do
    tipo (spec.md §4.3) são preenchidos com entidades ativas e distintas;
    os demais pares permanecem nulos, salvo override explícito.
    """

    def __init__(self, **overrides):
        proximo()
        self.dados = dict(
            tipo=TipoMovimentacao.TRANSFERENCIA,
            status=StatusMovimentacao.AGUARDANDO_APROVACAO,
            colaborador_id=None,
            data_solicitacao=datetime(2026, 1, 1, 12, 0, 0),
            departamento_origem_id=None,
            departamento_destino_id=None,
            cargo_origem_id=None,
            cargo_destino_id=None,
            gestor_origem_id=None,
            gestor_destino_id=None,
            centro_custo_origem_id=None,
            centro_custo_destino_id=None,
            estrutura_origem_id=None,
            estrutura_destino_id=None,
            resultado_ultima_validacao=None,
            data_ultima_validacao=None,
        )
        self.dados.update(overrides)

    def build(self, session) -> Movimentacao:
        tipo = self.dados["tipo"]
        colaborador = self._resolver_colaborador(session, tipo)
        self.dados["colaborador_id"] = colaborador.id
        self._preencher_campos_do_tipo(session, tipo, colaborador)

        obj = Movimentacao(**self.dados)
        session.add(obj)
        session.flush()
        return obj

    def _resolver_colaborador(self, session, tipo) -> Colaborador:
        if self.dados.get("colaborador_id") is not None:
            return session.get(Colaborador, self.dados["colaborador_id"])
        if tipo == TipoMovimentacao.PROMOCAO:
            cargo_baixo = CargoBuilder(nivel=1).build(session)
            return ColaboradorBuilder(cargo_id=cargo_baixo.id).build(session)
        return ColaboradorBuilder().build(session)

    def _preencher_campos_do_tipo(self, session, tipo, colaborador: Colaborador) -> None:
        if tipo == TipoMovimentacao.TRANSFERENCIA:
            if self.dados.get("departamento_origem_id") is None:
                self.dados["departamento_origem_id"] = DepartamentoBuilder().build(session).id
            if self.dados.get("departamento_destino_id") is None:
                self.dados["departamento_destino_id"] = DepartamentoBuilder().build(session).id

        elif tipo == TipoMovimentacao.PROMOCAO:
            if self.dados.get("cargo_origem_id") is None:
                self.dados["cargo_origem_id"] = colaborador.cargo_id
            if self.dados.get("cargo_destino_id") is None:
                nivel_atual = colaborador.cargo.nivel
                self.dados["cargo_destino_id"] = CargoBuilder(nivel=nivel_atual + 1).build(session).id

        elif tipo == TipoMovimentacao.TROCA_GESTOR:
            if self.dados.get("gestor_origem_id") is None:
                self.dados["gestor_origem_id"] = ColaboradorBuilder().build(session).id
            if self.dados.get("gestor_destino_id") is None:
                cargo_gestor = CargoBuilder(permite_gestao=True).build(session)
                self.dados["gestor_destino_id"] = ColaboradorBuilder(cargo_id=cargo_gestor.id).build(session).id

        elif tipo == TipoMovimentacao.MUDANCA_CENTRO_CUSTO:
            if self.dados.get("centro_custo_origem_id") is None:
                self.dados["centro_custo_origem_id"] = CentroCustoBuilder().build(session).id
            if self.dados.get("centro_custo_destino_id") is None:
                self.dados["centro_custo_destino_id"] = CentroCustoBuilder().build(session).id

        elif tipo == TipoMovimentacao.ALTERACAO_ESTRUTURA:
            if self.dados.get("estrutura_origem_id") is None:
                self.dados["estrutura_origem_id"] = EstruturaOrganizacionalBuilder().build(session).id
            if self.dados.get("estrutura_destino_id") is None:
                self.dados["estrutura_destino_id"] = EstruturaOrganizacionalBuilder().build(session).id
