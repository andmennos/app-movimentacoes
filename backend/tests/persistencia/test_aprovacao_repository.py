from sqlalchemy import event

from app.models import EstadoAprovacao, TipoAprovacao
from app.repositories import aprovacao_repository as repo
from tests.builders import AprovacaoBuilder, MovimentacaoBuilder


def test_lista_aprovacoes_por_movimentacao_com_aprovador_resolvido(db_session):
    mov = MovimentacaoBuilder().build(db_session)
    AprovacaoBuilder(
        movimentacao_id=mov.id, tipo=TipoAprovacao.GESTOR_ORIGEM, estado=EstadoAprovacao.APROVADA
    ).build(db_session)
    AprovacaoBuilder(
        movimentacao_id=mov.id, tipo=TipoAprovacao.GESTOR_DESTINO, estado=EstadoAprovacao.PENDENTE
    ).build(db_session)

    aprovacoes = repo.listar_por_movimentacao(db_session, mov.id)

    assert len(aprovacoes) == 2
    aprovada = next(a for a in aprovacoes if a.estado == EstadoAprovacao.APROVADA)
    assert aprovada.aprovador is not None


def test_carga_em_consulta_unica_sem_n_mais_1(db_session, engine):
    mov = MovimentacaoBuilder().build(db_session)
    mov_id = mov.id
    for tipo in (TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO, TipoAprovacao.RH):
        AprovacaoBuilder(movimentacao_id=mov_id, tipo=tipo, estado=EstadoAprovacao.APROVADA).build(
            db_session
        )
    db_session.expire_all()

    contagem = {"total": 0, "sql": []}

    def contar(conn, cursor, statement, *args, **kwargs):
        contagem["total"] += 1
        contagem["sql"].append(statement)

    event.listen(engine, "after_cursor_execute", contar)
    try:
        aprovacoes = repo.listar_por_movimentacao(db_session, mov_id)
        # acessar o aprovador de todas as linhas não deve disparar novas consultas:
        # já veio carregado pelo joinedload da própria consulta (sem N+1).
        nomes = [a.aprovador.nome for a in aprovacoes]
    finally:
        event.remove(engine, "after_cursor_execute", contar)

    assert len(nomes) == 3
    assert contagem["total"] == 1, contagem["sql"]
