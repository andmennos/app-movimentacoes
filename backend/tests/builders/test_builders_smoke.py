from app.models import TipoMovimentacao

from . import MovimentacaoBuilder, criar_aprovacoes_exigidas


def test_builder_cria_movimentacao_valida_por_padrao_para_cada_tipo(db_session):
    for tipo in TipoMovimentacao:
        mov = MovimentacaoBuilder(tipo=tipo).build(db_session)
        assert mov.id is not None
        assert mov.colaborador_id is not None


def test_criar_aprovacoes_exigidas_cobre_todos_os_tipos(db_session):
    for tipo in TipoMovimentacao:
        mov = MovimentacaoBuilder(tipo=tipo).build(db_session)
        aprovacoes = criar_aprovacoes_exigidas(db_session, mov)
        assert len(aprovacoes) >= 1
        assert all(a.movimentacao_id == mov.id for a in aprovacoes)
