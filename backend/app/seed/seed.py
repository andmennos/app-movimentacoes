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
  REPROVADA — cobrindo solicitações aguardando aprovação (AGUARDANDO_APROVACAO),
  bloqueadas por reprovação (BLOQUEADA), aptas para processamento (PENDENTE),
  e — depois do Worker — aprovadas e reprovadas por defeito único ou múltiplo;
- ao final, o producer agenda exatamente as solicitações aptas (spec §5.3);
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
    PerfilUsuario,
    ResultadoValidacao,
    StatusMovimentacao,
    TipoAprovacao,
    TipoMovimentacao,
    Usuario,
)
from app.models import OrigemEvento, TipoEventoProcessamento
from app.processing import producer
from app.repositories import historico_processamento_repository as historico_repo
from app.security.passwords import hash_password
from app.services.movimentacao_service import montar_contexto
from app.validation.aprovacoes import exigencias_para

DADOS_DIR = Path(__file__).parent / "dados"
MATRICULA_MARCADORA = "M000001"
RNG_SEED = 20260815
DATA_BASE = datetime(2026, 8, 15, 9, 0, 0)


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
    # familia_cargo/ordem_progressao/custo_mensal_referencia/papel_lideranca
    # (T-57/T-73/RC-32/RC-33): a família "GERAL" é a trilha usada pela
    # população geral do seed (transferência, troca de gestor, centro de
    # custo, alteração de estrutura, hierarquia de gestão) — ela também
    # precisa ser granular o bastante para não oferecer, via API real, um
    # atalho de promoção Júnior->Pleno num passo só (spec RC-33/plan.md
    # §23.1). Júnior e Pleno viram trilhas de 3 níveis cada (ordem 1-3 e
    # 4-6), tal como o exemplo canônico de spec §9.1 — a chave do dicionário
    # ("junior"/"pleno") continua apontando para o nível 1 de cada
    # senioridade, preservando toda referência já existente no restante do
    # seed (hierarquia, pool geral, cenário legado de promoção).
    cargos = {
        "junior": Cargo(
            codigo="CRG-JUNIOR", nome="Analista Júnior 1", nivel=1, ativo=True, permite_gestao=False,
            familia_cargo="GERAL", ordem_progressao=1, custo_mensal_referencia=500_000,
        ),
        "junior2": Cargo(
            codigo="CRG-JUNIOR2", nome="Analista Júnior 2", nivel=2, ativo=True, permite_gestao=False,
            familia_cargo="GERAL", ordem_progressao=2, custo_mensal_referencia=600_000,
        ),
        "junior3": Cargo(
            codigo="CRG-JUNIOR3", nome="Analista Júnior 3", nivel=3, ativo=True, permite_gestao=False,
            familia_cargo="GERAL", ordem_progressao=3, custo_mensal_referencia=700_000,
        ),
        "pleno": Cargo(
            codigo="CRG-PLENO", nome="Analista Pleno 1", nivel=1, ativo=True, permite_gestao=False,
            familia_cargo="GERAL", ordem_progressao=4, custo_mensal_referencia=800_000,
        ),
        "pleno2": Cargo(
            codigo="CRG-PLENO2", nome="Analista Pleno 2", nivel=2, ativo=True, permite_gestao=False,
            familia_cargo="GERAL", ordem_progressao=5, custo_mensal_referencia=900_000,
        ),
        "pleno3": Cargo(
            codigo="CRG-PLENO3", nome="Analista Pleno 3", nivel=3, ativo=True, permite_gestao=False,
            familia_cargo="GERAL", ordem_progressao=6, custo_mensal_referencia=1_000_000,
        ),
        "senior": Cargo(
            codigo="CRG-SENIOR", nome="Analista Sênior 1", nivel=1, ativo=True, permite_gestao=True,
            familia_cargo="GERAL", ordem_progressao=7, custo_mensal_referencia=1_100_000,
        ),
        "coordenador": Cargo(
            codigo="CRG-COORD", nome="Coordenador", nivel=1, ativo=True, permite_gestao=True,
            familia_cargo="GERAL", ordem_progressao=8, custo_mensal_referencia=1_500_000,
        ),
        "gerente": Cargo(
            codigo="CRG-GERENTE",
            nome="Gerente",
            nivel=1,
            ativo=True,
            permite_gestao=True,
            aprovacao_adicional=AprovacaoAdicional.GERENCIA,
            papel_lideranca=AprovacaoAdicional.GERENCIA,
            familia_cargo="GERAL",
            ordem_progressao=9,
            custo_mensal_referencia=2_200_000,
        ),
        "diretor": Cargo(
            codigo="CRG-DIRETOR",
            nome="Diretor",
            nivel=1,
            ativo=True,
            permite_gestao=True,
            aprovacao_adicional=AprovacaoAdicional.DIRETORIA,
            papel_lideranca=AprovacaoAdicional.DIRETORIA,
            familia_cargo="GERAL",
            ordem_progressao=10,
            custo_mensal_referencia=3_200_000,
        ),
        "inativo": Cargo(
            codigo="CRG-INATIVO", nome="Cargo Descontinuado", nivel=2, ativo=False,
            familia_cargo="GERAL", ordem_progressao=11, custo_mensal_referencia=800_000,
        ),
        "sem_gestao": Cargo(
            codigo="CRG-SEMGESTAO", nome="Especialista Técnico", nivel=1, ativo=True, permite_gestao=False,
            familia_cargo="GERAL", ordem_progressao=12, custo_mensal_referencia=1_100_000,
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
    # orcamento_mensal/custo_comprometido (T-57): plumbing com saldo folgado —
    # cenários de saldo insuficiente para P09 são construídos em T-64/T-69.
    centros = {
        "a": CentroCusto(
            codigo="CC-A", nome="CC Operações", ativo=True, estrutura_id=estruturas["raiz"].id,
            orcamento_mensal=50_000_000, custo_comprometido=0,
        ),
        "b": CentroCusto(
            codigo="CC-B", nome="CC Comercial", ativo=True, estrutura_id=estruturas["filha"].id,
            orcamento_mensal=50_000_000, custo_comprometido=0,
        ),
        "c": CentroCusto(
            codigo="CC-C", nome="CC Suporte", ativo=True, estrutura_id=estruturas["outra"].id,
            orcamento_mensal=50_000_000, custo_comprometido=0,
        ),
        "d": CentroCusto(
            codigo="CC-D", nome="CC Logística", ativo=True, estrutura_id=estruturas["neta"].id,
            orcamento_mensal=50_000_000, custo_comprometido=0,
        ),
        "inativo": CentroCusto(
            codigo="CC-INATIVO", nome="CC Descontinuado", ativo=False, estrutura_id=estruturas["outra"].id,
            orcamento_mensal=0, custo_comprometido=0,
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


def _criar_usuarios_autenticaveis(
    session: Session,
    cargos: dict[str, Cargo],
    estruturas: dict[str, EstruturaOrganizacional],
    hierarquia: list[Colaborador],
) -> Usuario:
    """spec.md §2.1/RC-13/RC-52/T-88 — seis usuários de demonstração do MVP.

    `analistaRh` fica vinculado a um colaborador ativo em um departamento/CC
    de RH dedicados, com superior hierárquico próprio (`gestor_rh`) — esse
    mesmo colaborador agora também é o login autenticável `gestorRh`
    (perfil `RH_GESTOR`).

    `coordenador`/`gerente`/`diretor` reaproveitam exatamente os três
    colaboradores de gestão já criados por `_criar_hierarquia`
    (`hierarquia = [diretor, gerente, coordenador, analista]`) — mesma
    cadeia real diretor→gerente→coordenador usada em toda a demonstração de
    subárvore/BOLA, sem criar uma segunda hierarquia paralela só para login.
    `gerente`/`diretor` já carregam `Cargo.papel_lideranca=GERENCIA/DIRETORIA`
    (T-73), então autenticar com esses logins já demonstra a resolução de
    liderança concreta da promoção com aprovação adicional (T-75), sem
    inventar um terceiro perfil técnico `COORDENADOR`/`GERENTE`/`DIRETOR`
    (RC-52 — todos usam o mesmo perfil técnico `LIDERANCA`).
    """
    diretor_colab, gerente_colab, coordenador_colab, _analista_colab = hierarquia
    departamento_rh = Departamento(
        codigo="DEP-RH", nome="Recursos Humanos", ativo=True, estrutura_id=estruturas["raiz"].id
    )
    centro_custo_rh = CentroCusto(
        codigo="CC-RH", nome="CC Recursos Humanos", ativo=True, estrutura_id=estruturas["raiz"].id,
        orcamento_mensal=50_000_000, custo_comprometido=0,
    )
    session.add_all([departamento_rh, centro_custo_rh])
    session.flush()

    gestor_rh = Colaborador(
        matricula="M900001",
        nome="Gestora de RH Corporativo",
        ativo=True,
        cargo_id=cargos["gerente"].id,
        departamento_id=departamento_rh.id,
        centro_custo_id=centro_custo_rh.id,
        gestor_id=None,
        data_admissao=date(2016, 4, 1),
    )
    session.add(gestor_rh)
    session.flush()

    analista_rh = Colaborador(
        matricula="M900002",
        nome="Analista de RH Corporativo",
        ativo=True,
        cargo_id=cargos["pleno"].id,
        departamento_id=departamento_rh.id,
        centro_custo_id=centro_custo_rh.id,
        gestor_id=gestor_rh.id,
        data_admissao=date(2021, 9, 1),
    )
    session.add(analista_rh)
    session.flush()

    # spec §2.1 permite Usuario.colaborador_id nulo, mas o ADMIN decide
    # aprovações (RC-12) e `Aprovacao.aprovador_id` exige um colaborador
    # ativo válido para a integridade da engine (spec §5.3 condição 2) —
    # vincular o admin a um colaborador de si mesmo evita esse conflito sem
    # inventar regra de negócio nova, é só infraestrutura de auditoria.
    colaborador_admin = Colaborador(
        matricula="M900003",
        nome="Administrador do Sistema",
        ativo=True,
        cargo_id=cargos["diretor"].id,
        departamento_id=departamento_rh.id,
        centro_custo_id=centro_custo_rh.id,
        gestor_id=None,
        data_admissao=date(2015, 1, 1),
    )
    session.add(colaborador_admin)
    session.flush()

    departamento_rh.gestor_id = gestor_rh.id
    centro_custo_rh.responsavel_id = gestor_rh.id
    session.flush()

    usuario_admin = Usuario(
        username="admin",
        password_hash=hash_password("admin"),
        perfil=PerfilUsuario.ADMIN,
        colaborador_id=colaborador_admin.id,
        ativo=True,
        criado_em=DATA_BASE,
    )
    session.add_all(
        [
            usuario_admin,
            Usuario(
                username="analistaRh",
                password_hash=hash_password("analistaRh"),
                perfil=PerfilUsuario.RH_ANALISTA,
                colaborador_id=analista_rh.id,
                ativo=True,
                criado_em=DATA_BASE,
            ),
            Usuario(
                username="gestorRh",
                password_hash=hash_password("gestorRh"),
                perfil=PerfilUsuario.RH_GESTOR,
                colaborador_id=gestor_rh.id,
                ativo=True,
                criado_em=DATA_BASE,
            ),
            Usuario(
                username="coordenador",
                password_hash=hash_password("coordenador"),
                perfil=PerfilUsuario.LIDERANCA,
                colaborador_id=coordenador_colab.id,
                ativo=True,
                criado_em=DATA_BASE,
            ),
            Usuario(
                username="gerente",
                password_hash=hash_password("gerente"),
                perfil=PerfilUsuario.LIDERANCA,
                colaborador_id=gerente_colab.id,
                ativo=True,
                criado_em=DATA_BASE,
            ),
            Usuario(
                username="diretor",
                password_hash=hash_password("diretor"),
                perfil=PerfilUsuario.LIDERANCA,
                colaborador_id=diretor_colab.id,
                ativo=True,
                criado_em=DATA_BASE,
            ),
        ]
    )
    session.flush()
    return usuario_admin


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
    pool_ativo: list[Colaborador],
    aprovador_inativo: Colaborador,
    modo: str,
) -> None:
    """Cria as linhas de aprovação exigidas pelo tipo (nunca omitidas).

    T-76/RC-41 — fonte única: `exigencias_para` (via `montar_contexto`), a
    mesma função usada por criação/gate/decisão/integridade, não um mapa
    paralelo. Como estas movimentações têm `solicitante_usuario_id` do
    próprio `ADMIN` do seed (perfil que nunca aciona substituição — RC-07),
    o resultado é sempre a matriz-base — inclusive o bundle completo de
    `PROMOCAO` com `aprovacao_adicional` (T-75), quando aplicável.

    `modo`:
    - "aprovadas": todas APROVADA, com aprovador ativo.
    - "aguardando": a última exigida fica PENDENTE; as demais, APROVADA.
    - "reprovada": a primeira exigida fica REPROVADA, com aprovador ativo; as
      demais, APROVADA. Demonstra o gate bloqueando a movimentação sem job
      (spec §5.4, CN-Q03) — nenhum defeito de dado envolvido.
    - "integridade_quebrada": a primeira exigida fica APROVADA com aprovador
      inativo (defeito de integridade — spec §5.3).
    """
    ctx = montar_contexto(session, movimentacao)
    tipos = [TipoAprovacao(e.tipo.value) for e in exigencias_para(ctx)]

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
        session.flush()

        # spec §7.4/T-62 — toda Aprovacao decidida precisa de um evento de
        # histórico correspondente (o mesmo invariante que AprovacaoService
        # garante em decisões via API); sem isso, o seed reproduziria o bug
        # intermitente que T-62 corrigiu.
        if aprovacao.estado != EstadoAprovacao.PENDENTE:
            verbo = "aprovada" if aprovacao.estado == EstadoAprovacao.APROVADA else "reprovada"
            tipo_evento = (
                TipoEventoProcessamento.APROVACAO_CONCLUIDA
                if aprovacao.estado == EstadoAprovacao.APROVADA
                else TipoEventoProcessamento.APROVACAO_REPROVADA
            )
            historico_repo.registrar(
                session,
                movimentacao.id,
                tipo_evento,
                OrigemEvento.SISTEMA,
                f"Aprovação {tipo.value} {verbo} (dado fictício de seed).",
                aprovacao.data_decisao,
            )


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
    solicitante_usuario_id: int,
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
            data_solicitacao = DATA_BASE - timedelta(days=dia)
            movimentacao = Movimentacao(
                tipo=tipo,
                status=StatusMovimentacao.AGUARDANDO_APROVACAO,
                colaborador_id=colaborador.id,
                data_solicitacao=data_solicitacao,
                solicitante_usuario_id=solicitante_usuario_id,
                **campos,
            )
            session.add(movimentacao)
            session.flush()
            historico_repo.registrar(
                session,
                movimentacao.id,
                TipoEventoProcessamento.SOLICITACAO_RECEBIDA,
                OrigemEvento.SISTEMA,
                f"Solicitação de {tipo.value.lower()} recebida.",
                data_solicitacao,
                solicitante_usuario_id=solicitante_usuario_id,
            )

            if cenario == "aguardando":
                modo_aprovacao = "aguardando"
            elif cenario == "reprovada":
                modo_aprovacao = "reprovada"
            elif cenario == "multipla" and fabrica.rng.random() < 0.3:
                modo_aprovacao = "integridade_quebrada"
            else:
                modo_aprovacao = "aprovadas"
            _criar_aprovacoes(
                session, fabrica, movimentacao, pool_ativo, aprovador_inativo, modo_aprovacao
            )
            total_criadas += 1

    # Cenário dedicado e estável de TG05 (ciclo hierárquico), fora do laço acima
    # para não depender de mutação compartilhada da cadeia principal.
    total_criadas += _gerar_ciclo_hierarquico_dedicado(
        session, fabrica, cargos, departamentos, centros, solicitante_usuario_id
    )

    session.flush()
    return total_criadas


def _gerar_ciclo_hierarquico_dedicado(
    session, fabrica, cargos, departamentos, centros, solicitante_usuario_id
) -> int:
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

    # T-65: gestor_origem_id precisa refletir o gestor atual REAL de `a`.
    a.gestor_id = b.id
    session.flush()

    data_solicitacao = DATA_BASE - timedelta(days=200)
    movimentacao = Movimentacao(
        tipo=TipoMovimentacao.TROCA_GESTOR,
        status=StatusMovimentacao.AGUARDANDO_APROVACAO,
        colaborador_id=a.id,
        data_solicitacao=data_solicitacao,
        gestor_origem_id=b.id,
        gestor_destino_id=c.id,
        solicitante_usuario_id=solicitante_usuario_id,
    )
    session.add(movimentacao)
    session.flush()
    historico_repo.registrar(
        session,
        movimentacao.id,
        TipoEventoProcessamento.SOLICITACAO_RECEBIDA,
        OrigemEvento.SISTEMA,
        "Solicitação de troca_gestor recebida.",
        data_solicitacao,
        solicitante_usuario_id=solicitante_usuario_id,
    )
    _criar_aprovacoes(session, fabrica, movimentacao, [a, b, c], a, "aprovadas")
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
    # spec RC-33/plan.md §23.1 (T-73): junior(ordem_progressao=1) ->
    # pleno(ordem_progressao=4) NÃO é mais um passo válido — a família
    # "GERAL" agora é granular (Júnior 1/2/3 -> Pleno 1/2/3 -> ...), então o
    # par consecutivo-mesma-família usado no cenário "bem-sucedido" da massa
    # geral é junior -> junior2 (ordem 1 -> 2), não mais junior -> pleno.
    cargos = ctx["cargos"]
    colaborador.cargo_id = cargos["junior"].id
    destino = cargos["junior2"]
    if cenario == "defeito_unico":
        destino = cargos["junior"]  # mesmo cargo: P03 (ordem_progressao igual)
    elif cenario == "multipla":
        destino = cargos["inativo"]  # P02 + P03 (cargo inativo e fora de sequência)
    return {"cargo_origem_id": cargos["junior"].id, "cargo_destino_id": destino.id}


def _especificar_troca_gestor(cenario, ctx, colaborador):
    # spec §5.6/T-65: GESTOR_ORIGEM precisa ser o gestor atual REAL do
    # colaborador (colaborador.gestor_id), não um valor fixo — TG06 agora
    # reprova quando os dois não coincidem (defeito de inversão/integridade).
    # `colaborador` vem do pool (sempre com gestor_id preenchido) ou, no
    # caso raro de ser um dos próprios membros da hierarquia sem superior
    # (o diretor), cai no fallback histórico.
    hierarquia = ctx["hierarquia"]
    origem_gestor_id = colaborador.gestor_id if colaborador.gestor_id is not None else hierarquia[1].id
    destino_gestor = next((c for c in hierarquia if c.id != origem_gestor_id), hierarquia[0])
    if cenario == "defeito_unico":
        destino_gestor = colaborador  # TG04: colaborador não pode ser seu próprio gestor
    elif cenario == "multipla":
        # TG02 + TG03 simultâneos: novo gestor inativo e sem função de gestão —
        # combinação estável, sem depender de mutação da cadeia compartilhada.
        # Efeito no fluxo automático: o gate (spec §5.3) só olha o *estado*
        # das aprovações exigidas (APROVADA/PENDENTE/REPROVADA), não a
        # integridade do aprovador — então esta movimentação passa pelo gate
        # normalmente (APTO) e vai para PENDENTE + job. A integridade (o
        # responsável esperado por GESTOR_DESTINO deriva de `gestor_destino_id`
        # — spec §5.3.1 — e está inativo aqui) é responsabilidade exclusiva da
        # engine: TG06 reprova quando o Worker processa o job.
        candidato = ctx.get("gestor_inativo_sem_gestao")
        if candidato is not None:
            destino_gestor = candidato
    return {"gestor_origem_id": origem_gestor_id, "gestor_destino_id": destino_gestor.id}


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


def _criar_trilha_cargos(session: Session, prefixo: str, familia: str, custo_base: int) -> list[Cargo]:
    """spec.md §9.1 — trilha de uma família: Júnior 1/2/3 -> Pleno 1/2/3 ->
    Sênior 1, `ordem_progressao` 1..7 consecutiva. O número no nome reinicia
    a cada senioridade (deliberado — é exatamente o que P03 não pode usar)."""
    niveis = [
        ("Júnior", "JR", 1), ("Júnior", "JR", 2), ("Júnior", "JR", 3),
        ("Pleno", "PL", 1), ("Pleno", "PL", 2), ("Pleno", "PL", 3),
        ("Sênior", "SR", 1),
    ]
    cargos = []
    for ordem, (senioridade, sigla, numero) in enumerate(niveis, start=1):
        cargo = Cargo(
            codigo=f"{prefixo}-{sigla}{numero}",
            nome=f"Analista {senioridade} {familia.title()} {numero}",
            nivel=numero,
            ativo=True,
            permite_gestao=False,
            familia_cargo=familia,
            ordem_progressao=ordem,
            custo_mensal_referencia=custo_base + (ordem - 1) * 100_000,
        )
        session.add(cargo)
        cargos.append(cargo)
    session.flush()
    return cargos


def _gerar_cenarios_promocao_avancados(
    session: Session,
    fabrica: Fabrica,
    departamentos: dict[str, Departamento],
    estruturas: dict[str, EstruturaOrganizacional],
    hierarquia: list[Colaborador],
    solicitante_usuario_id: int,
) -> int:
    """spec.md §9/§10.3/T-69 — cenários dedicados e nomeados para P03/P07/
    P08/P09 com uma trilha real de duas famílias (spec §9.1), não os cargos
    genéricos usados no restante do seed. Cobre PRO-01..10 de forma
    demonstrável manualmente (cada colaborador/matrícula descreve o cenário)."""
    operacoes = _criar_trilha_cargos(session, "OPS", "OPERACOES", 500_000)
    tecnologia = _criar_trilha_cargos(session, "TEC", "TECNOLOGIA", 550_000)
    jr1, jr2, jr3, pl1, pl2, pl3, sr1 = operacoes
    _tjr1, _tjr2, _tjr3, _tpl1, tec_pl2, _tpl3, _tsr1 = tecnologia

    gestor_id = hierarquia[1].id
    dep_id = departamentos["a"].id
    # `dia` pequeno (datas recentes, perto de DATA_BASE) é proposital aqui:
    # as novas solicitações de PRO-07/PRO-08 precisam ser posteriores às
    # promoções históricas fabricadas abaixo (-60/-243 dias) para a
    # comparação de 6 meses (P08) fazer sentido cronologicamente.

    cc_folgado = CentroCusto(
        codigo="CC-ORC-FOLGADO", nome="CC Orçamento Folgado", ativo=True,
        estrutura_id=estruturas["raiz"].id, orcamento_mensal=5_000_000, custo_comprometido=0,
        responsavel_id=gestor_id,
    )
    cc_apertado = CentroCusto(
        codigo="CC-ORC-APERTADO", nome="CC Orçamento Apertado", ativo=True,
        estrutura_id=estruturas["raiz"].id, orcamento_mensal=1_000_000, custo_comprometido=950_000,
        responsavel_id=gestor_id,
    )
    session.add_all([cc_folgado, cc_apertado])
    session.flush()
    dia = 5

    def _colaborador(matricula_sufixo: str, cargo: Cargo, centro_custo_id: int) -> Colaborador:
        colaborador = Colaborador(
            matricula=f"M9001{matricula_sufixo}",
            nome=fabrica.nome(),
            ativo=True,
            cargo_id=cargo.id,
            departamento_id=dep_id,
            centro_custo_id=centro_custo_id,
            gestor_id=gestor_id,
            data_admissao=date(2019, 1, 1),
        )
        session.add(colaborador)
        session.flush()
        return colaborador

    def _promocao(colaborador: Colaborador, cargo_destino: Cargo, centro_custo_id: int) -> Movimentacao:
        nonlocal dia
        dia += 1
        data_solicitacao = DATA_BASE - timedelta(days=dia)
        movimentacao = Movimentacao(
            tipo=TipoMovimentacao.PROMOCAO,
            status=StatusMovimentacao.AGUARDANDO_APROVACAO,
            colaborador_id=colaborador.id,
            data_solicitacao=data_solicitacao,
            cargo_origem_id=colaborador.cargo_id,
            cargo_destino_id=cargo_destino.id,
            centro_custo_origem_id=centro_custo_id,
            solicitante_usuario_id=solicitante_usuario_id,
        )
        session.add(movimentacao)
        session.flush()
        historico_repo.registrar(
            session, movimentacao.id, TipoEventoProcessamento.SOLICITACAO_RECEBIDA, OrigemEvento.SISTEMA,
            "Solicitação de promocao recebida.", data_solicitacao, solicitante_usuario_id=solicitante_usuario_id,
        )
        _criar_aprovacoes(session, fabrica, movimentacao, hierarquia, hierarquia[0], "aprovadas")
        return movimentacao

    total = 0

    # PRO-01: Júnior 1 -> Júnior 2, passo consecutivo — deve ficar apta/aprovar.
    _promocao(_colaborador("01", jr1, cc_folgado.id), jr2, cc_folgado.id)
    total += 1

    # PRO-02: Júnior 1 -> Júnior 3, salto de duas posições — P03.
    _promocao(_colaborador("02", jr1, cc_folgado.id), jr3, cc_folgado.id)
    total += 1

    # PRO-03: Júnior 3 -> Pleno 1 — consecutiva apesar do número reiniciar.
    _promocao(_colaborador("03", jr3, cc_folgado.id), pl1, cc_folgado.id)
    total += 1

    # PRO-04: Júnior 3 -> Pleno 2 — pula Pleno 1 — P03.
    _promocao(_colaborador("04", jr3, cc_folgado.id), pl2, cc_folgado.id)
    total += 1

    # PRO-05: mesmo cargo (origem == destino) — P03.
    _promocao(_colaborador("05", pl1, cc_folgado.id), pl1, cc_folgado.id)
    total += 1

    # PRO-06: família diferente (OPERACOES -> TECNOLOGIA) — P07.
    _promocao(_colaborador("06", pl1, cc_folgado.id), tec_pl2, cc_folgado.id)
    total += 1

    # PRO-09: saldo insuficiente no CC apertado (delta 100_000 > saldo 50_000) — P09.
    _promocao(_colaborador("09", pl2, cc_apertado.id), pl3, cc_apertado.id)
    total += 1

    # PRO-10: mesmo delta, CC folgado — passa P09.
    _promocao(_colaborador("10", pl2, cc_folgado.id), pl3, cc_folgado.id)
    total += 1

    # PRO-07: promoção efetivada há 2 meses (< 6) — P08 reprova a nova solicitação.
    colaborador_recente = _colaborador("07", pl1, cc_folgado.id)
    historico_recente = Movimentacao(
        tipo=TipoMovimentacao.PROMOCAO,
        status=StatusMovimentacao.APROVADA,
        colaborador_id=colaborador_recente.id,
        data_solicitacao=DATA_BASE - timedelta(days=400),
        cargo_origem_id=jr3.id,
        cargo_destino_id=pl1.id,
        centro_custo_origem_id=cc_folgado.id,
        solicitante_usuario_id=solicitante_usuario_id,
        resultado_ultima_validacao=ResultadoValidacao.APROVADA,
        data_ultima_validacao=DATA_BASE - timedelta(days=60),
    )
    session.add(historico_recente)
    session.flush()
    _criar_aprovacoes(session, fabrica, historico_recente, hierarquia, hierarquia[0], "aprovadas")
    historico_repo.registrar(
        session, historico_recente.id, TipoEventoProcessamento.MOVIMENTACAO_EFETIVADA, OrigemEvento.SISTEMA,
        "Movimentação efetivada no cadastro do colaborador.", DATA_BASE - timedelta(days=60),
        solicitante_usuario_id=solicitante_usuario_id,
    )
    _promocao(colaborador_recente, pl2, cc_folgado.id)
    total += 2

    # PRO-08: promoção efetivada há 8 meses (>= 6) — não reprova P08.
    colaborador_antigo = _colaborador("08", pl1, cc_folgado.id)
    historico_antigo = Movimentacao(
        tipo=TipoMovimentacao.PROMOCAO,
        status=StatusMovimentacao.APROVADA,
        colaborador_id=colaborador_antigo.id,
        data_solicitacao=DATA_BASE - timedelta(days=400),
        cargo_origem_id=jr3.id,
        cargo_destino_id=pl1.id,
        centro_custo_origem_id=cc_folgado.id,
        solicitante_usuario_id=solicitante_usuario_id,
        resultado_ultima_validacao=ResultadoValidacao.APROVADA,
        data_ultima_validacao=DATA_BASE - timedelta(days=243),
    )
    session.add(historico_antigo)
    session.flush()
    _criar_aprovacoes(session, fabrica, historico_antigo, hierarquia, hierarquia[0], "aprovadas")
    historico_repo.registrar(
        session, historico_antigo.id, TipoEventoProcessamento.MOVIMENTACAO_EFETIVADA, OrigemEvento.SISTEMA,
        "Movimentação efetivada no cadastro do colaborador.", DATA_BASE - timedelta(days=243),
        solicitante_usuario_id=solicitante_usuario_id,
    )
    _promocao(colaborador_antigo, pl2, cc_folgado.id)
    total += 2

    # T-73/plan.md §23.1: Pleno 3 -> Sênior 1 — consecutiva na fronteira de
    # senioridade seguinte (ordem 6 -> 7), tal como Júnior 3 -> Pleno 1
    # (PRO-03) na fronteira anterior — prova que a trilha continua coerente
    # além do par já coberto por PRO-03/PRO-04. Não é o PRO-11 do catálogo
    # de spec.md §16.4 (esse é "efetivação atualiza cargo+custo
    # atomicamente", já coberto em tests/processing/test_orchestrator.py).
    _promocao(_colaborador("11", pl3, cc_folgado.id), sr1, cc_folgado.id)
    total += 1

    session.flush()
    return total


def _gerar_cenarios_bundle_adicional(
    session: Session,
    fabrica: Fabrica,
    cargos: dict[str, Cargo],
    departamentos: dict[str, Departamento],
    centros: dict[str, CentroCusto],
    hierarquia: list[Colaborador],
    solicitante_usuario_id: int,
) -> int:
    """T-75/T-79 — demonstra o bundle completo de aprovação adicional
    (hierárquica -> RH/GESTOR_RH -> GERENCIA/DIRETORIA -> GESTOR_RH_ADICIONAL)
    com a hierarquia REAL do seed (diretor/gerente/coordenador de
    `_criar_hierarquia`, com `papel_lideranca` já coerente), não builders de
    teste isolados. Cada colaborador reporta a alguém sem `papel_lideranca`
    (o próprio gestor imediato), então a liderança resolvida é sempre uma
    pessoa diferente de quem decide a etapa hierárquica — as quatro etapas
    ficam com quatro decisões distintas, sem depender da dedup de aprovador
    (RC-42, coberta à parte em tests/aprovacoes/test_t75_aprovacao_adicional.py)."""
    diretor, gerente, coordenador, _analista = hierarquia
    dep_id = departamentos["a"].id
    cc_id = centros["a"].id
    dia = 500

    def _promover(sufixo: str, cargo_origem: Cargo, cargo_destino: Cargo, gestor_direto: Colaborador) -> Movimentacao:
        nonlocal dia
        dia += 1
        colaborador = Colaborador(
            matricula=f"M9002{sufixo}",
            nome=fabrica.nome(),
            ativo=True,
            cargo_id=cargo_origem.id,
            departamento_id=dep_id,
            centro_custo_id=cc_id,
            gestor_id=gestor_direto.id,
            data_admissao=date(2019, 1, 1),
        )
        session.add(colaborador)
        session.flush()
        data_solicitacao = DATA_BASE - timedelta(days=dia)
        movimentacao = Movimentacao(
            tipo=TipoMovimentacao.PROMOCAO,
            status=StatusMovimentacao.AGUARDANDO_APROVACAO,
            colaborador_id=colaborador.id,
            data_solicitacao=data_solicitacao,
            cargo_origem_id=cargo_origem.id,
            cargo_destino_id=cargo_destino.id,
            centro_custo_origem_id=cc_id,
            solicitante_usuario_id=solicitante_usuario_id,
        )
        session.add(movimentacao)
        session.flush()
        historico_repo.registrar(
            session, movimentacao.id, TipoEventoProcessamento.SOLICITACAO_RECEBIDA, OrigemEvento.SISTEMA,
            "Solicitação de promocao recebida.", data_solicitacao, solicitante_usuario_id=solicitante_usuario_id,
        )
        _criar_aprovacoes(session, fabrica, movimentacao, hierarquia, hierarquia[0], "aprovadas")
        return movimentacao

    # M900201: coordenador(GERAL, ordem 8) -> gerente(GERAL, ordem 9,
    # aprovacao_adicional=GERENCIA). Reporta ao "coordenador" (sem papel) —
    # a liderança GERENCIA resolvida é o "gerente", uma pessoa diferente.
    _promover("01", cargos["coordenador"], cargos["gerente"], coordenador)

    # M900202: gerente(GERAL, ordem 9) -> diretor(GERAL, ordem 10,
    # aprovacao_adicional=DIRETORIA). Reporta ao "gerente" — a liderança
    # DIRETORIA resolvida é o "diretor", subindo mais um nível da cadeia.
    _promover("02", cargos["gerente"], cargos["diretor"], gerente)

    session.flush()
    return 2


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
        usuario_admin = _criar_usuarios_autenticaveis(session, cargos, estruturas, hierarquia)
        pool = _criar_pool_colaboradores(session, fabrica, cargos, departamentos, centros, hierarquia)

        total = _gerar_movimentacoes(
            session, fabrica, cargos, departamentos, centros, estruturas, hierarquia, pool, usuario_admin.id
        )
        total += _gerar_cenarios_promocao_avancados(
            session, fabrica, departamentos, estruturas, hierarquia, usuario_admin.id
        )
        total += _gerar_cenarios_bundle_adicional(
            session, fabrica, cargos, departamentos, centros, hierarquia, usuario_admin.id
        )

        session.commit()
        print(f"Seed concluído: {total} movimentações criadas.")

    resultado = producer.executar(session)
    print(
        f"Producer: {resultado.agendadas} agendada(s) para validação, "
        f"{resultado.bloqueadas} bloqueada(s) por reprovação, "
        f"{resultado.aguardando} aguardando aprovação."
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
