from datetime import datetime

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    ESTADOS_ABERTOS,
    CentroCusto,
    Colaborador,
    Departamento,
    Movimentacao,
    StatusMovimentacao,
    TipoMovimentacao,
)

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
        joinedload(Movimentacao.solicitante),
    )


def listar(
    session: Session,
    page: int = 1,
    page_size: int = 20,
    status: StatusMovimentacao | None = None,
    busca: str | None = None,
    ordenar_por: str = "dataSolicitacao",
    direcao: str = "desc",
    colaborador_ids_permitidos: set[int] | None = None,
) -> tuple[list[Movimentacao], int]:
    """`colaborador_ids_permitidos` aplica BOLA (spec §3.1/plan §7.3) antes
    de `count`/paginação — `None` significa sem filtro (ADMIN/RH_ANALISTA/
    RH_GESTOR); um conjunto (mesmo vazio) restringe à subárvore de LIDERANCA."""
    if ordenar_por not in CAMPOS_ORDENAVEIS:
        raise OrdenacaoInvalida(ordenar_por)

    page = max(page, 1)
    page_size = min(max(page_size, 1), PAGE_SIZE_MAXIMO)

    base = select(Movimentacao).join(Movimentacao.colaborador)
    if status is not None:
        base = base.where(Movimentacao.status == status)
    if busca:
        # RC-46 — termo numérico também filtra por ID da movimentação, sem
        # substituir a busca textual por matrícula/nome (todos os critérios
        # valem juntos, como um OR).
        filtros = [Colaborador.matricula == busca, Colaborador.nome.ilike(f"%{busca}%")]
        if busca.isdigit():
            filtros.append(Movimentacao.id == int(busca))
        base = base.where(or_(*filtros))
    if colaborador_ids_permitidos is not None:
        base = base.where(Movimentacao.colaborador_id.in_(colaborador_ids_permitidos))

    total = session.scalar(select(func.count()).select_from(base.subquery()))

    coluna = CAMPOS_ORDENAVEIS[ordenar_por]
    ordenacao = asc(coluna) if direcao == "asc" else desc(coluna)
    # RF-04/RNF-09: desempate determinístico por id — sem isso, empates no
    # campo ordenado podem mudar de página em página (CN-Q21).
    desempate = asc(Movimentacao.id) if direcao == "asc" else desc(Movimentacao.id)
    consulta = _entidades_relacionadas(base).order_by(ordenacao, desempate)
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
    """G04: existe outra movimentação do mesmo tipo, mesmo colaborador, em um
    estado **aberto** (`AGUARDANDO_APROVACAO` ou `PENDENTE` — spec.md §7.1),
    id diferente. Estados terminais (`APROVADA`/`REPROVADA`/`BLOQUEADA`) não
    contam como conflito."""
    consulta = select(func.count()).select_from(Movimentacao).where(
        Movimentacao.colaborador_id == colaborador_id,
        Movimentacao.tipo == tipo,
        Movimentacao.status.in_(ESTADOS_ABERTOS),
        Movimentacao.id != excluir_id,
    )
    return (session.scalar(consulta) or 0) > 0


def listar_aguardando_aprovacao(
    session: Session, colaborador_ids_permitidos: set[int] | None = None, busca: str | None = None
) -> list[Movimentacao]:
    """spec.md §6.1/RC-51 — candidatas para `GET /aprovacoes/pendentes`: toda
    movimentação `AGUARDANDO_APROVACAO` dentro do escopo BOLA do usuário,
    opcionalmente filtrada por `busca` (ID numérico, matrícula ou nome do
    colaborador — mesmo critério de RC-46). Sem paginação (volume esperado é
    baixo no MVP — spec §15 5.000/dia)."""
    consulta = select(Movimentacao).where(Movimentacao.status == StatusMovimentacao.AGUARDANDO_APROVACAO)
    if colaborador_ids_permitidos is not None:
        consulta = consulta.where(Movimentacao.colaborador_id.in_(colaborador_ids_permitidos))
    if busca:
        consulta = consulta.join(Movimentacao.colaborador)
        filtros = [Colaborador.matricula == busca, Colaborador.nome.ilike(f"%{busca}%")]
        if busca.isdigit():
            filtros.append(Movimentacao.id == int(busca))
        consulta = consulta.where(or_(*filtros))
    consulta = _entidades_relacionadas(consulta).order_by(Movimentacao.id.asc())
    return list(session.scalars(consulta).unique())


def buscar_data_ultima_promocao_aprovada(
    session: Session, colaborador_id: int, excluir_movimentacao_id: int
) -> datetime | None:
    """spec.md §9.3/§11.1 — data de efetivação (`data_ultima_validacao`) da
    promoção `APROVADA` mais recente do colaborador, para P08 (6 meses).
    `None` se nunca houve promoção efetivada."""
    consulta = (
        select(Movimentacao.data_ultima_validacao)
        .where(
            Movimentacao.colaborador_id == colaborador_id,
            Movimentacao.tipo == TipoMovimentacao.PROMOCAO,
            Movimentacao.status == StatusMovimentacao.APROVADA,
            Movimentacao.id != excluir_movimentacao_id,
        )
        .order_by(Movimentacao.data_ultima_validacao.desc())
        .limit(1)
    )
    return session.scalar(consulta)


def carregar_grafo_gestores(session: Session) -> dict[int, int | None]:
    """Todos os pares (id, gestor_id) de Colaborador, em uma única consulta —
    usado para pré-carregar `cadeia_hierarquica` sem I/O por regra (TG05)."""
    consulta = select(Colaborador.id, Colaborador.gestor_id)
    return dict(session.execute(consulta).all())
