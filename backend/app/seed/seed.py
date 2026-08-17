"""Seed idempotente de solicitações fictícias (spec.md §12).

Representa **solicitações de movimentação recebidas de processos anteriores**
— não ações de um usuário clicando em "validar" no portal. Ao final, invoca o
producer local para agendar automaticamente as solicitações aptas; o Angular
não participa deste fluxo.

Roda como script: `python -m app.seed.seed`.

Garante:
- toda movimentação nasce com as linhas de aprovação exigidas pelo seu tipo
  — nunca ausentes (spec §5.1);
- Departamento.gestor_id e CentroCusto.responsavel_id sempre preenchidos com
  colaborador ativo (spec §5.3, restrição de seed);
- ao menos um par de estruturas ancestral/descendente (CN-A01/CN-A02);
- cadeia hierárquica de colaboradores com ao menos 3 níveis (CN-N13);
- ao menos um cargo com aprovacao_adicional=DIRETORIA (CN-N09);
- ≥100 movimentações, com aprovações distribuídas entre PENDENTE, APROVADA e
  REPROVADA — cobrindo solicitações aguardando aprovação, bloqueadas por
  reprovação, aprovadas, reprovadas por defeito único e por múltiplas
  inconsistências;
- ao final, o producer agenda exatamente as solicitações aptas (spec §5.4);
- reexecução de seed + producer não duplica movimentações nem jobs;
- nenhum dado real de pessoa ou organização.
"""

import itertools
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import (
    Aprovacao,
    AprovacaoAdicional,
    Cargo,
    CentroCusto,
    Colaborador,
    Departamento,
    EstadoAprovacao,
    EstruturaOrganizacional,
    Movimentacao,
    StatusMovimentacao,
    TipoAprovacao,
    TipoMovimentacao,
)
from app.processing import producer

DADOS_DIR = Path(__file__).parent / "dados"
MATRICULA_MARCADORA = "M000001"
RNG_SEED = 20260815
DATA_BASE = datetime(2026, 8, 15, 9, 0, 0)

# Mesma composição de app.validation.aprovacoes.EXIGENCIAS_BASE_POR_TIPO, mas
# com os enums de app.models (não os de app.validation.types) — o seed grava
# linhas de Aprovacao via ORM, então precisa do tipo de enum do modelo, não
# do enum puro usado dentro do motor de validação. Não é uma segunda decisão
# de negócio: os dois conjuntos de valores são mantidos em sincronia pelos
# testes de app.validation.aprovacoes e pelo catálogo de regras (spec §5.2).
EXIGENCIAS_POR_TIPO = {
    TipoMovimentacao.TRANSFERENCIA: [TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO],
    TipoMovimentacao.PROMOCAO: [TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.RH],
    TipoMovimentacao.TROCA_GESTOR: [TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO],
    TipoMovimentacao.MUDANCA_CENTRO_CUSTO: [TipoAprovacao.GESTOR_DESTINO],
    TipoMovimentacao.ALTERACAO_ESTRUTURA: [TipoAprovacao.GESTOR_ORIGEM],
}


class Fabrica:
    """Agrupa geradores determinísticos de nomes/códigos para o seed."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        conteudo = json.loads((DADOS_DIR / "nomes.json").read_text(encoding="utf-8"))
        self.primeiros = conteudo["primeiros_nomes"]
        self.sobrenomes = conteudo["sobrenomes"]
        self._matricula = itertools.count(2)  # M000001 é reservada à matrícula marcadora
        self._codigo = itertools.count(1)

    def nome(self) -> str:
        return f"{self.rng.choice(self.primeiros)} {self.rng.choice(self.sobrenomes)}"

    def matricula(self) -> str:
        return f"M{next(self._matricula):06d}"

    def codigo(self, prefixo: str) -> str:
        return f"{prefixo}{next(self._codigo):04d}"


def _ja_semeado(session: Session) -> bool:
    return session.query(Colaborador).filter_by(matricula=MATRICULA_MARCADORA).first() is not None


def _criar_estruturas(session: Session) -> dict[str, EstruturaOrganizacional]:
    raiz = EstruturaOrganizacional(codigo="EST-RAIZ", nome="Diretoria Executiva", ativo=True, nivel=1)
    session.add(raiz)
    session.flush()

    filha = EstruturaOrganizacional(
        codigo="EST-FILHA", nome="Superintendência Regional", ativo=True, nivel=2, estrutura_pai_id=raiz.id
    )
    session.add(filha)
    session.flush()

    neta = EstruturaOrganizacional(
        codigo="EST-NETA", nome="Unidade Operacional", ativo=True, nivel=3, estrutura_pai_id=filha.id
    )
    outra = EstruturaOrganizacional(codigo="EST-OUTRA", nome="Núcleo de Suporte", ativo=True, nivel=1)
    inativa = EstruturaOrganizacional(
        codigo="EST-INATIVA", nome="Unidade Descontinuada", ativo=False, nivel=1
    )
    session.add_all([neta, outra, inativa])
    session.flush()

    return {"raiz": raiz, "filha": filha, "neta": neta, "outra": outra, "inativa": inativa}


def _criar_cargos(session: Session) -> dict[str, Cargo]:
    cargos = {
        "junior": Cargo(codigo="CRG-JUNIOR", nome="Analista Júnior", nivel=1, ativo=True, permite_gestao=False),
        "pleno": Cargo(codigo="CRG-PLENO", nome="Analista Pleno", nivel=2, ativo=True, permite_gestao=False),
        "senior": Cargo(codigo="CRG-SENIOR", nome="Analista Sênior", nivel=3, ativo=True, permite_gestao=True),
        "coordenador": Cargo(
            codigo="CRG-COORD", nome="Coordenador", nivel=4, ativo=True, permite_gestao=True
        ),
        "gerente": Cargo(
            codigo="CRG-GERENTE",
            nome="Gerente",
            nivel=5,
            ativo=True,
            permite_gestao=True,
            aprovacao_adicional=AprovacaoAdicional.GERENCIA,
        ),
        "diretor": Cargo(
            codigo="CRG-DIRETOR",
            nome="Diretor",
            nivel=6,
            ativo=True,
            permite_gestao=True,
            aprovacao_adicional=AprovacaoAdicional.DIRETORIA,
        ),
        "inativo": Cargo(codigo="CRG-INATIVO", nome="Cargo Descontinuado", nivel=2, ativo=False),
        "sem_gestao": Cargo(
            codigo="CRG-SEMGESTAO", nome="Especialista Técnico", nivel=3, ativo=True, permite_gestao=False
        ),
    }
    session.add_all(cargos.values())
    session.flush()
    return cargos


def _criar_departamentos_e_centros(
    session: Session, estruturas: dict[str, EstruturaOrganizacional]
) -> tuple[dict[str, Departamento], dict[str, CentroCusto]]:
    departamentos = {
        "a": Departamento(codigo="DEP-A", nome="Operações", ativo=True, estrutura_id=estruturas["raiz"].id),
        "b": Departamento(
            codigo="DEP-B", nome="Comercial", ativo=True, estrutura_id=estruturas["filha"].id
        ),
        "c": Departamento(codigo="DEP-C", nome="Suporte", ativo=True, estrutura_id=estruturas["outra"].id),
        "d": Departamento(codigo="DEP-D", nome="Logística", ativo=True, estrutura_id=estruturas["neta"].id),
        "inativo": Departamento(
            codigo="DEP-INATIVO", nome="Departamento Descontinuado", ativo=False, estrutura_id=estruturas["outra"].id
        ),
    }
    centros = {
        "a": CentroCusto(codigo="CC-A", nome="CC Operações", ativo=True, estrutura_id=estruturas["raiz"].id),
        "b": CentroCusto(codigo="CC-B", nome="CC Comercial", ativo=True, estrutura_id=estruturas["filha"].id),
        "c": CentroCusto(codigo="CC-C", nome="CC Suporte", ativo=True, estrutura_id=estruturas["outra"].id),
        "d": CentroCusto(codigo="CC-D", nome="CC Logística", ativo=True, estrutura_id=estruturas["neta"].id),
        "inativo": CentroCusto(
            codigo="CC-INATIVO", nome="CC Descontinuado", ativo=False, estrutura_id=estruturas["outra"].id
        ),
    }
    session.add_all([*departamentos.values(), *centros.values()])
    session.flush()
    return departamentos, centros


def _criar_hierarquia(
    session: Session,
    fabrica: Fabrica,
    cargos: dict[str, Cargo],
    departamentos: dict[str, Departamento],
    centros: dict[str, CentroCusto],
) -> list[Colaborador]:
    """Cria a cadeia diretor → gerente → coordenador → analista (4 níveis)
    usada como espinha dorsal de gestão e para sustentar CN-N13."""
    diretor = Colaborador(
        matricula=MATRICULA_MARCADORA,
        nome=fabrica.nome(),
        ativo=True,
        cargo_id=cargos["diretor"].id,
        departamento_id=departamentos["a"].id,
        centro_custo_id=centros["a"].id,
        gestor_id=None,
        data_admissao=date(2015, 3, 1),
    )
    session.add(diretor)
    session.flush()

    gerente = Colaborador(
        matricula=fabrica.matricula(),
        nome=fabrica.nome(),
        ativo=True,
        cargo_id=cargos["gerente"].id,
        departamento_id=departamentos["a"].id,
        centro_custo_id=centros["a"].id,
        gestor_id=diretor.id,
        data_admissao=date(2017, 5, 10),
    )
    session.add(gerente)
    session.flush()

    coordenador = Colaborador(
        matricula=fabrica.matricula(),
        nome=fabrica.nome(),
        ativo=True,
        cargo_id=cargos["coordenador"].id,
        departamento_id=departamentos["b"].id,
        centro_custo_id=centros["b"].id,
        gestor_id=gerente.id,
        data_admissao=date(2019, 8, 20),
    )
    session.add(coordenador)
    session.flush()

    analista = Colaborador(
        matricula=fabrica.matricula(),
        nome=fabrica.nome(),
        ativo=True,
        cargo_id=cargos["pleno"].id,
        departamento_id=departamentos["b"].id,
        centro_custo_id=centros["b"].id,
        gestor_id=coordenador.id,
        data_admissao=date(2021, 2, 1),
    )
    session.add(analista)
    session.flush()

    departamentos["a"].gestor_id = diretor.id
    departamentos["b"].gestor_id = gerente.id
    departamentos["c"].gestor_id = gerente.id
    departamentos["d"].gestor_id = coordenador.id
    departamentos["inativo"].gestor_id = coordenador.id
    centros["a"].responsavel_id = diretor.id
    centros["b"].responsavel_id = gerente.id
    centros["c"].responsavel_id = gerente.id
    centros["d"].responsavel_id = coordenador.id
    centros["inativo"].responsavel_id = coordenador.id
    session.flush()

    return [diretor, gerente, coordenador, analista]


def _criar_pool_colaboradores(
    session: Session,
    fabrica: Fabrica,
    cargos: dict[str, Cargo],
    departamentos: dict[str, Departamento],
    centros: dict[str, CentroCusto],
    hierarquia: list[Colaborador],
    quantidade: int = 60,
) -> list[Colaborador]:
    cargos_normais = [cargos["junior"], cargos["pleno"], cargos["senior"], cargos["coordenador"]]
    departamentos_normais = [departamentos["a"], departamentos["b"], departamentos["c"], departamentos["d"]]
    centros_normais = [centros["a"], centros["b"], centros["c"], centros["d"]]
    gestores_possiveis = hierarquia

    pool = []
    for i in range(quantidade):
        ativo = fabrica.rng.random() > 0.1
        colaborador = Colaborador(
            matricula=fabrica.matricula(),
            nome=fabrica.nome(),
            ativo=ativo,
            cargo_id=fabrica.rng.choice(cargos_normais).id,
            departamento_id=fabrica.rng.choice(departamentos_normais).id,
            centro_custo_id=fabrica.rng.choice(centros_normais).id,
            gestor_id=fabrica.rng.choice(gestores_possiveis).id,
            data_admissao=date(2018, 1, 1) + timedelta(days=fabrica.rng.randint(0, 2500)),
        )
        session.add(colaborador)
        pool.append(colaborador)
    session.flush()
    return pool


def _criar_aprovacoes(
    session: Session,
    fabrica: Fabrica,
    movimentacao: Movimentacao,
    cargos: dict[str, Cargo],
    pool_ativo: list[Colaborador],
    aprovador_inativo: Colaborador,
    modo: str,
) -> None:
    """Cria as linhas de aprovação exigidas pelo tipo (nunca omitidas).

    `modo`:
    - "aprovadas": todas APROVADA, com aprovador ativo.
    - "aguardando": a última exigida fica PENDENTE; as demais, APROVADA.
    - "reprovada": a primeira exigida fica REPROVADA, com aprovador ativo; as
      demais, APROVADA. Demonstra o gate bloqueando a movimentação sem job
      (spec §5.4, CN-Q03) — nenhum defeito de dado envolvido.
    - "integridade_quebrada": a primeira exigida fica APROVADA com aprovador
      inativo (defeito de integridade — spec §5.3).
    """
    tipos = list(EXIGENCIAS_POR_TIPO[movimentacao.tipo])
    if movimentacao.tipo == TipoMovimentacao.PROMOCAO and movimentacao.cargo_destino_id is not None:
        cargo_destino = session.get(Cargo, movimentacao.cargo_destino_id)
        if cargo_destino is not None and cargo_destino.aprovacao_adicional is not None:
            tipos.append(TipoAprovacao(cargo_destino.aprovacao_adicional.value))

    for indice, tipo in enumerate(tipos):
        if modo == "aguardando" and indice == len(tipos) - 1:
            aprovacao = Aprovacao(
                movimentacao_id=movimentacao.id,
                tipo=tipo,
                estado=EstadoAprovacao.PENDENTE,
                aprovador_id=None,
                data_decisao=None,
            )
        elif modo == "reprovada" and indice == 0:
            aprovacao = Aprovacao(
                movimentacao_id=movimentacao.id,
                tipo=tipo,
                estado=EstadoAprovacao.REPROVADA,
                aprovador_id=fabrica.rng.choice(pool_ativo).id,
                data_decisao=movimentacao.data_solicitacao + timedelta(days=1),
                justificativa="Reprovada na etapa de aprovação (cenário fictício de seed).",
            )
        elif modo == "integridade_quebrada" and indice == 0:
            aprovacao = Aprovacao(
                movimentacao_id=movimentacao.id,
                tipo=tipo,
                estado=EstadoAprovacao.APROVADA,
                aprovador_id=aprovador_inativo.id,
                data_decisao=movimentacao.data_solicitacao + timedelta(days=1),
            )
        else:
            aprovacao = Aprovacao(
                movimentacao_id=movimentacao.id,
                tipo=tipo,
                estado=EstadoAprovacao.APROVADA,
                aprovador_id=fabrica.rng.choice(pool_ativo).id,
                data_decisao=movimentacao.data_solicitacao + timedelta(days=1),
            )
        session.add(aprovacao)


def _colaborador_valido(fabrica, pool_ativo):
    return fabrica.rng.choice(pool_ativo)


def _gerar_movimentacoes(
    session: Session,
    fabrica: Fabrica,
    cargos: dict[str, Cargo],
    departamentos: dict[str, Departamento],
    centros: dict[str, CentroCusto],
    estruturas: dict[str, EstruturaOrganizacional],
    hierarquia: list[Colaborador],
    pool: list[Colaborador],
) -> int:
    pool_ativo = [c for c in pool if c.ativo] + hierarquia
    pool_inativo = [c for c in pool if not c.ativo]
    aprovador_inativo = pool_inativo[0] if pool_inativo else pool_ativo[0]
    gestor_inativo_sem_gestao = next(
        (c for c in pool_inativo if c.cargo_id in (cargos["junior"].id, cargos["pleno"].id)), None
    )

    ctx = dict(
        cargos=cargos,
        departamentos=departamentos,
        centros=centros,
        estruturas=estruturas,
        hierarquia=hierarquia,
        gestor_inativo_sem_gestao=gestor_inativo_sem_gestao,
    )

    cenarios = ["aprovada", "aguardando", "reprovada", "defeito_unico", "multipla"] * 5  # 25 por tipo
    total_criadas = 0
    dia = 0

    especificacoes = {
        TipoMovimentacao.TRANSFERENCIA: _especificar_transferencia,
        TipoMovimentacao.PROMOCAO: _especificar_promocao,
        TipoMovimentacao.TROCA_GESTOR: _especificar_troca_gestor,
        TipoMovimentacao.MUDANCA_CENTRO_CUSTO: _especificar_centro_custo,
        TipoMovimentacao.ALTERACAO_ESTRUTURA: _especificar_estrutura,
    }

    tipos_com_colaborador_inativo_na_multipla = {
        TipoMovimentacao.TRANSFERENCIA,
        TipoMovimentacao.MUDANCA_CENTRO_CUSTO,
        TipoMovimentacao.ALTERACAO_ESTRUTURA,
    }

    for tipo, especificar in especificacoes.items():
        for cenario in cenarios:
            # Nunca reaproveita um colaborador do pool ativo mutando seu
            # `.ativo` — esse objeto pode ser sorteado como aprovador de
            # OUTRA movimentação mais adiante, contaminando cenários que
            # deveriam ficar íntegros. Cenários "múltipla" que precisam de um
            # colaborador inativo sorteiam diretamente do pool já inativo.
            if cenario == "multipla" and tipo in tipos_com_colaborador_inativo_na_multipla and pool_inativo:
                colaborador = fabrica.rng.choice(pool_inativo)
            else:
                colaborador = _colaborador_valido(fabrica, pool_ativo)
            campos = especificar(cenario, ctx, colaborador)
            dia += 1
            movimentacao = Movimentacao(
                tipo=tipo,
                status=StatusMovimentacao.PENDENTE,
                colaborador_id=colaborador.id,
                data_solicitacao=DATA_BASE - timedelta(days=dia),
                **campos,
            )
            session.add(movimentacao)
            session.flush()

            if cenario == "aguardando":
                modo_aprovacao = "aguardando"
            elif cenario == "reprovada":
                modo_aprovacao = "reprovada"
            elif cenario == "multipla" and fabrica.rng.random() < 0.3:
                modo_aprovacao = "integridade_quebrada"
            else:
                modo_aprovacao = "aprovadas"
            _criar_aprovacoes(
                session, fabrica, movimentacao, cargos, pool_ativo, aprovador_inativo, modo_aprovacao
            )
            total_criadas += 1

    # Cenário dedicado e estável de TG05 (ciclo hierárquico), fora do laço acima
    # para não depender de mutação compartilhada da cadeia principal.
    total_criadas += _gerar_ciclo_hierarquico_dedicado(session, fabrica, cargos, departamentos, centros)

    session.flush()
    return total_criadas


def _gerar_ciclo_hierarquico_dedicado(session, fabrica, cargos, departamentos, centros) -> int:
    """Cria uma mini-cadeia isolada (A gestor de B, B gestor de C) e uma
    TROCA_GESTOR que tentaria tornar C gestor de A — ciclo indireto de 3 níveis,
    sustentando CN-N12/CN-N13 de forma isolada e permanente."""
    a = Colaborador(
        matricula=fabrica.matricula(),
        nome=fabrica.nome(),
        ativo=True,
        cargo_id=cargos["coordenador"].id,
        departamento_id=departamentos["c"].id,
        centro_custo_id=centros["c"].id,
        gestor_id=None,
        data_admissao=date(2020, 1, 1),
    )
    session.add(a)
    session.flush()
    b = Colaborador(
        matricula=fabrica.matricula(),
        nome=fabrica.nome(),
        ativo=True,
        cargo_id=cargos["senior"].id,
        departamento_id=departamentos["c"].id,
        centro_custo_id=centros["c"].id,
        gestor_id=a.id,
        data_admissao=date(2020, 6, 1),
    )
    session.add(b)
    session.flush()
    c = Colaborador(
        matricula=fabrica.matricula(),
        nome=fabrica.nome(),
        ativo=True,
        cargo_id=cargos["pleno"].id,
        departamento_id=departamentos["c"].id,
        centro_custo_id=centros["c"].id,
        gestor_id=b.id,
        data_admissao=date(2021, 1, 1),
    )
    session.add(c)
    session.flush()

    movimentacao = Movimentacao(
        tipo=TipoMovimentacao.TROCA_GESTOR,
        status=StatusMovimentacao.PENDENTE,
        colaborador_id=a.id,
        data_solicitacao=DATA_BASE - timedelta(days=200),
        gestor_origem_id=b.id,
        gestor_destino_id=c.id,
    )
    session.add(movimentacao)
    session.flush()
    _criar_aprovacoes(session, fabrica, movimentacao, cargos, [a, b, c], a, "aprovadas")
    return 1


def _especificar_transferencia(cenario, ctx, colaborador):
    # Nos cenários "multipla", o chamador já sorteou `colaborador` do pool
    # inativo (spec G02) — aqui só resta acrescentar o segundo defeito (T04).
    departamentos = ctx["departamentos"]
    origem, destino = departamentos["a"], departamentos["b"]
    if cenario in ("defeito_unico", "multipla"):
        destino = departamentos["inativo"]
    return {"departamento_origem_id": origem.id, "departamento_destino_id": destino.id}


def _especificar_promocao(cenario, ctx, colaborador):
    cargos = ctx["cargos"]
    colaborador.cargo_id = cargos["junior"].id
    destino = cargos["senior"]
    if cenario == "defeito_unico":
        destino = cargos["junior"]  # mesmo nível: P03
    elif cenario == "multipla":
        destino = cargos["inativo"]  # P02 + P03 (nível igual, cargo também inativo)
    return {"cargo_origem_id": cargos["junior"].id, "cargo_destino_id": destino.id}


def _especificar_troca_gestor(cenario, ctx, colaborador):
    hierarquia = ctx["hierarquia"]
    origem_gestor = hierarquia[1]
    destino_gestor = hierarquia[2]
    if cenario == "defeito_unico":
        destino_gestor = colaborador  # TG04: colaborador não pode ser seu próprio gestor
    elif cenario == "multipla":
        # TG02 + TG03 simultâneos: novo gestor inativo e sem função de gestão —
        # combinação estável, sem depender de mutação da cadeia compartilhada.
        # Efeito colateral esperado no fluxo automático: como GESTOR_DESTINO
        # deriva exatamente de `gestor_destino_id` (spec §5.3.1), o próprio
        # responsável esperado da aprovação fica inativo — o gate classifica
        # isso como ANOMALO (spec §5.4), não como REPROVADA/APTA. É o
        # comportamento correto: um dado assim quebrado não deve ser mascarado
        # como se tivesse passado por uma decisão normal de aprovação.
        candidato = ctx.get("gestor_inativo_sem_gestao")
        if candidato is not None:
            destino_gestor = candidato
    return {"gestor_origem_id": origem_gestor.id, "gestor_destino_id": destino_gestor.id}


def _especificar_centro_custo(cenario, ctx, colaborador):
    # Idem transferência: "multipla" já recebe colaborador inativo do chamador.
    centros = ctx["centros"]
    origem, destino = centros["a"], centros["b"]
    if cenario == "defeito_unico":
        destino = centros["a"]  # CC05: origem == destino
    elif cenario == "multipla":
        destino = centros["inativo"]
    return {"centro_custo_origem_id": origem.id, "centro_custo_destino_id": destino.id}


def _especificar_estrutura(cenario, ctx, colaborador):
    # Idem transferência: "multipla" já recebe colaborador inativo do chamador.
    estruturas = ctx["estruturas"]
    origem, destino = estruturas["outra"], estruturas["raiz"]
    if cenario == "defeito_unico":
        destino = estruturas["outra"]  # AE05: origem == destino
    elif cenario == "multipla":
        destino = estruturas["inativa"]
    return {"estrutura_origem_id": origem.id, "estrutura_destino_id": destino.id}


def seed(session: Session) -> None:
    """Cria as solicitações fictícias (se ainda não existirem) e, em seguida,
    executa o producer local — sempre, mesmo quando o seed em si é um no-op —
    para garantir que solicitações aptas sejam agendadas (spec §12, fluxo de
    demonstração). O producer já é idempotente por conta própria (CA-043),
    então reexecutar `seed()` nunca duplica movimentações nem jobs.
    """
    if _ja_semeado(session):
        print("Seed já executado anteriormente — nada a fazer (idempotente).")
    else:
        rng = random.Random(RNG_SEED)
        fabrica = Fabrica(rng)

        estruturas = _criar_estruturas(session)
        cargos = _criar_cargos(session)
        departamentos, centros = _criar_departamentos_e_centros(session, estruturas)
        hierarquia = _criar_hierarquia(session, fabrica, cargos, departamentos, centros)
        pool = _criar_pool_colaboradores(session, fabrica, cargos, departamentos, centros, hierarquia)

        total = _gerar_movimentacoes(
            session, fabrica, cargos, departamentos, centros, estruturas, hierarquia, pool
        )

        session.commit()
        print(f"Seed concluído: {total} movimentações criadas.")

    resultado = producer.executar(session)
    print(
        f"Producer: {resultado.agendadas} agendada(s) para validação, "
        f"{resultado.bloqueadas} bloqueada(s) por reprovação, "
        f"{resultado.aguardando} aguardando aprovação, "
        f"{resultado.anomalas} anômala(s) (integridade)."
    )


def main() -> None:
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        seed(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
