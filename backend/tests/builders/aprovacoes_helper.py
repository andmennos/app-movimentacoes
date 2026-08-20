from app.models import Cargo, EstadoAprovacao, Movimentacao, TipoAprovacao, TipoMovimentacao

from .aprovacao_builder import AprovacaoBuilder

EXIGENCIAS_POR_TIPO = {
    # spec.md revisão 2026-08-19 §5.3/§5.5/§5.6/§5.7 — RH passou a integrar
    # a matriz-base de TRANSFERENCIA/TROCA_GESTOR/MUDANCA_CENTRO_CUSTO/
    # ALTERACAO_ESTRUTURA (T-63). Equivale a `exigencias_para` sem
    # solicitante — nenhuma substituição se aplica.
    TipoMovimentacao.TRANSFERENCIA: [TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO, TipoAprovacao.RH],
    TipoMovimentacao.PROMOCAO: [TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.RH],
    TipoMovimentacao.TROCA_GESTOR: [TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO, TipoAprovacao.RH],
    TipoMovimentacao.MUDANCA_CENTRO_CUSTO: [TipoAprovacao.GESTOR_DESTINO, TipoAprovacao.RH],
    TipoMovimentacao.ALTERACAO_ESTRUTURA: [TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.RH],
}


def tipos_exigidos(session, movimentacao: Movimentacao) -> list[TipoAprovacao]:
    tipos = list(EXIGENCIAS_POR_TIPO[movimentacao.tipo])
    if movimentacao.tipo == TipoMovimentacao.PROMOCAO and movimentacao.cargo_destino_id is not None:
        cargo_destino = session.get(Cargo, movimentacao.cargo_destino_id)
        if cargo_destino is not None and cargo_destino.aprovacao_adicional is not None:
            tipos.append(TipoAprovacao(cargo_destino.aprovacao_adicional.value))
    return tipos


def criar_aprovacoes_exigidas(session, movimentacao: Movimentacao, estado=EstadoAprovacao.APROVADA):
    """Cria, para a movimentação, exatamente as linhas de aprovação exigidas pelo
    seu tipo (spec.md §5.2/§5.3.1), todas no `estado` informado (APROVADA por padrão,
    com aprovador ativo íntegro)."""
    criadas = []
    for tipo in tipos_exigidos(session, movimentacao):
        criadas.append(
            AprovacaoBuilder(movimentacao_id=movimentacao.id, tipo=tipo, estado=estado).build(session)
        )
    return criadas
