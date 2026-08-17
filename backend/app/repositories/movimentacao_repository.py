from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import CentroCusto, Colaborador, Departamento, Movimentacao, StatusMovimentacao

from .exceptions import OrdenacaoInvalida

PAGE_SIZE_MAXIMO = 100

CAMPOS_ORDENAVEIS = {
    "dataSolicitacao": Movimentacao.data_solicitacao,
    "tipo": Movimentacao.tipo,
    "status": Movimentacao.status,
    "colaboradorNome": Colaborador.nome,
}


def _entidades_relacionadas(query):
    return query.options(
        joinedload(Movimentacao.colaborador),
        joinedload(Movimentacao.departamento_origem),
        joinedload(Movimentacao.departamento_destino),
        joinedload(Movimentacao.cargo_origem),
        joinedload(Movimentacao.cargo_destino),
        joinedload(Movimentacao.gestor_origem),
        joinedload(Movimentacao.gestor_destino),
        joinedload(Movimentacao.centro_custo_origem),
        joinedload(Movimentacao.centro_custo_destino),
        joinedload(Movimentacao.estrutura_origem),
        joinedload(Movimentacao.estrutura_destino),
    )


def listar(
    session: Session,
    page: int = 1,
    page_size: int = 20,
    status: StatusMovimentacao | None = None,
    busca: str | None = None,
    ordenar_por: str = "dataSolicitacao",
    direcao: str = "desc",
) -> tuple[list[Movimentacao], int]:
    if ordenar_por not in CAMPOS_ORDENAVEIS:
        raise OrdenacaoInvalida(ordenar_por)

    page = max(page, 1)
    page_size = min(max(page_size, 1), PAGE_SIZE_MAXIMO)

    base = select(Movimentacao).join(Movimentacao.colaborador)
    if status is not None:
        base = base.where(Movimentacao.status == status)
    if busca:
        base = base.where(
            or_(Colaborador.matricula == busca, Colaborador.nome.ilike(f"%{busca}%"))
        )

    total = session.scalar(select(func.count()).select_from(base.subquery()))

    coluna = CAMPOS_ORDENAVEIS[ordenar_por]
    ordenacao = asc(coluna) if direcao == "asc" else desc(coluna)
    consulta = _entidades_relacionadas(base).order_by(ordenacao)
    consulta = consulta.offset((page - 1) * page_size).limit(page_size)

    itens = list(session.scalars(consulta).unique())
    return itens, total


def buscar_por_id(session: Session, movimentacao_id: int) -> Movimentacao | None:
    consulta = _entidades_relacionadas(
        select(Movimentacao).where(Movimentacao.id == movimentacao_id)
    )
    return session.scalars(consulta).unique().one_or_none()


def carregar_para_validacao(session: Session, movimentacao_id: int) -> Movimentacao | None:
    """Carga única (uma consulta SQL, via LEFT OUTER JOINs) de tudo que o
    `ValidationContext` pode precisar: a movimentação, suas entidades de
    origem/destino por tipo, e os colaboradores usados na resolução dos
    aprovadores esperados (spec §5.3.1) — colaborador.cargo/gestor,
    gestor_destino.cargo, gestor_origem, gestores de departamento e
    responsável do centro de custo de destino."""
    consulta = (
        select(Movimentacao)
        .where(Movimentacao.id == movimentacao_id)
        .options(
            joinedload(Movimentacao.colaborador).joinedload(Colaborador.cargo),
            joinedload(Movimentacao.colaborador).joinedload(Colaborador.gestor),
            joinedload(Movimentacao.departamento_origem).joinedload(Departamento.gestor),
            joinedload(Movimentacao.departamento_destino).joinedload(Departamento.gestor),
            joinedload(Movimentacao.cargo_origem),
            joinedload(Movimentacao.cargo_destino),
            joinedload(Movimentacao.gestor_origem),
            joinedload(Movimentacao.gestor_destino).joinedload(Colaborador.cargo),
            joinedload(Movimentacao.centro_custo_origem),
            joinedload(Movimentacao.centro_custo_destino).joinedload(CentroCusto.responsavel),
            joinedload(Movimentacao.estrutura_origem),
            joinedload(Movimentacao.estrutura_destino),
        )
    )
    return session.scalars(consulta).unique().one_or_none()


def existe_conflito(session: Session, colaborador_id: int, tipo, excluir_id: int) -> bool:
    """G04: existe outra movimentação do mesmo tipo, mesmo colaborador,
    `status=PENDENTE`, id diferente."""
    consulta = select(func.count()).select_from(Movimentacao).where(
        Movimentacao.colaborador_id == colaborador_id,
        Movimentacao.tipo == tipo,
        Movimentacao.status == StatusMovimentacao.PENDENTE,
        Movimentacao.id != excluir_id,
    )
    return (session.scalar(consulta) or 0) > 0


def carregar_grafo_gestores(session: Session) -> dict[int, int | None]:
    """Todos os pares (id, gestor_id) de Colaborador, em uma única consulta —
    usado para pré-carregar `cadeia_hierarquica` sem I/O por regra (TG05)."""
    consulta = select(Colaborador.id, Colaborador.gestor_id)
    return dict(session.execute(consulta).all())
