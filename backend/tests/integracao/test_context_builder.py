from app.models import TipoMovimentacao
from app.repositories import movimentacao_repository
from app.services.movimentacao_service import montar_contexto
from tests.builders import (
    CargoBuilder,
    ColaboradorBuilder,
    DepartamentoBuilder,
    MovimentacaoBuilder,
    criar_aprovacoes_exigidas,
)


def _carregar_e_montar(db_session, mov_id):
    mov = movimentacao_repository.carregar_para_validacao(db_session, mov_id)
    return montar_contexto(db_session, mov)


def test_transferencia_deriva_aprovadores_dos_gestores_dos_departamentos(db_session):
    gestor_origem = ColaboradorBuilder().build(db_session)
    gestor_destino = ColaboradorBuilder().build(db_session)
    dep_origem = DepartamentoBuilder(gestor_id=gestor_origem.id).build(db_session)
    dep_destino = DepartamentoBuilder(gestor_id=gestor_destino.id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA,
        departamento_origem_id=dep_origem.id,
        departamento_destino_id=dep_destino.id,
    ).build(db_session)

    ctx = _carregar_e_montar(db_session, mov.id)

    assert ctx.responsaveis_derivados["GESTOR_ORIGEM"].id == gestor_origem.id
    assert ctx.responsaveis_derivados["GESTOR_DESTINO"].id == gestor_destino.id


def test_promocao_deriva_gestor_origem_do_colaborador_gestor_id(db_session):
    gestor = ColaboradorBuilder().build(db_session)
    colaborador = ColaboradorBuilder(gestor_id=gestor.id, cargo_id=CargoBuilder(nivel=1).build(db_session).id).build(
        db_session
    )
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.PROMOCAO,
        colaborador_id=colaborador.id,
        cargo_origem_id=colaborador.cargo_id,
        cargo_destino_id=CargoBuilder(nivel=2).build(db_session).id,
    ).build(db_session)

    ctx = _carregar_e_montar(db_session, mov.id)

    assert ctx.responsaveis_derivados["GESTOR_ORIGEM"].id == gestor.id
    assert ctx.cargo_atual.nivel == 1
    assert ctx.cargo_destino.nivel == 2


def test_troca_gestor_deriva_de_campos_proprios_da_movimentacao(db_session):
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.TROCA_GESTOR).build(db_session)

    ctx = _carregar_e_montar(db_session, mov.id)

    assert ctx.responsaveis_derivados["GESTOR_ORIGEM"].id == mov.gestor_origem_id
    assert ctx.responsaveis_derivados["GESTOR_DESTINO"].id == mov.gestor_destino_id


def test_centro_custo_deriva_do_responsavel_do_destino(db_session):
    responsavel = ColaboradorBuilder().build(db_session)
    from tests.builders import CentroCustoBuilder

    cc_destino = CentroCustoBuilder(responsavel_id=responsavel.id).build(db_session)
    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.MUDANCA_CENTRO_CUSTO, centro_custo_destino_id=cc_destino.id
    ).build(db_session)

    ctx = _carregar_e_montar(db_session, mov.id)

    assert ctx.responsaveis_derivados["GESTOR_DESTINO"].id == responsavel.id
    assert "GESTOR_ORIGEM" not in ctx.responsaveis_derivados


def test_estrutura_deriva_gestor_origem_do_colaborador_gestor_id(db_session):
    gestor = ColaboradorBuilder().build(db_session)
    colaborador = ColaboradorBuilder(gestor_id=gestor.id).build(db_session)
    mov = MovimentacaoBuilder(tipo=TipoMovimentacao.ALTERACAO_ESTRUTURA, colaborador_id=colaborador.id).build(
        db_session
    )

    ctx = _carregar_e_montar(db_session, mov.id)

    assert ctx.responsaveis_derivados["GESTOR_ORIGEM"].id == gestor.id


def test_g04_detecta_conflito_mesmo_tipo_mesmo_colaborador_pendente(db_session):
    from app.models import StatusMovimentacao

    colaborador = ColaboradorBuilder().build(db_session)
    MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA, colaborador_id=colaborador.id, status=StatusMovimentacao.PENDENTE
    ).build(db_session)
    mov2 = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TRANSFERENCIA, colaborador_id=colaborador.id, status=StatusMovimentacao.PENDENTE
    ).build(db_session)

    ctx = _carregar_e_montar(db_session, mov2.id)

    assert ctx.conflito_mesmo_tipo_em_aberto is True


def test_g04_nao_detecta_conflito_de_tipo_diferente(db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    MovimentacaoBuilder(tipo=TipoMovimentacao.TRANSFERENCIA, colaborador_id=colaborador.id).build(db_session)
    mov2 = MovimentacaoBuilder(tipo=TipoMovimentacao.PROMOCAO, colaborador_id=colaborador.id).build(db_session)

    ctx = _carregar_e_montar(db_session, mov2.id)

    assert ctx.conflito_mesmo_tipo_em_aberto is False


def test_tg05_cadeia_hierarquica_precarregada_a_partir_do_gestor_destino(db_session):
    avo = ColaboradorBuilder().build(db_session)
    pai = ColaboradorBuilder(gestor_id=avo.id).build(db_session)
    cargo_gestor = CargoBuilder(permite_gestao=True).build(db_session)
    novo_gestor = ColaboradorBuilder(gestor_id=pai.id, cargo_id=cargo_gestor.id).build(db_session)

    mov = MovimentacaoBuilder(
        tipo=TipoMovimentacao.TROCA_GESTOR,
        gestor_destino_id=novo_gestor.id,
    ).build(db_session)

    ctx = _carregar_e_montar(db_session, mov.id)

    assert novo_gestor.id in ctx.cadeia_hierarquica
    assert pai.id in ctx.cadeia_hierarquica
    assert avo.id in ctx.cadeia_hierarquica
    assert ctx.cadeia_hierarquica[novo_gestor.id].gestor_id == pai.id
