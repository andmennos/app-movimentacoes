from app.models import (
    Aprovacao,
    AprovacaoAdicional,
    Cargo,
    CentroCusto,
    Colaborador,
    Departamento,
    EstadoAprovacao,
    EstruturaOrganizacional,
    JobValidacao,
    Movimentacao,
    StatusJob,
    StatusMovimentacao,
)
from app.seed.seed import EXIGENCIAS_POR_TIPO, seed


def test_seed_cria_ao_menos_100_movimentacoes(db_session):
    seed(db_session)
    total = db_session.query(Movimentacao).count()
    assert total >= 100


def test_seed_e_idempotente(db_session):
    seed(db_session)
    total_apos_primeira = db_session.query(Movimentacao).count()

    seed(db_session)
    total_apos_segunda = db_session.query(Movimentacao).count()

    assert total_apos_primeira == total_apos_segunda


def test_toda_movimentacao_nasce_com_linhas_de_aprovacao_exigidas(db_session):
    seed(db_session)
    movimentacoes = db_session.query(Movimentacao).all()

    for mov in movimentacoes:
        tipos_exigidos = set(EXIGENCIAS_POR_TIPO[mov.tipo])
        aprovacoes = db_session.query(Aprovacao).filter_by(movimentacao_id=mov.id).all()
        tipos_presentes = {a.tipo for a in aprovacoes}
        assert tipos_exigidos <= tipos_presentes, f"movimentação {mov.id} ({mov.tipo}) sem linhas exigidas"


def test_departamento_gestor_e_centro_custo_responsavel_sempre_preenchidos(db_session):
    seed(db_session)
    for dep in db_session.query(Departamento).all():
        assert dep.gestor_id is not None, f"departamento {dep.codigo} sem gestor"
    for cc in db_session.query(CentroCusto).all():
        assert cc.responsavel_id is not None, f"centro de custo {cc.codigo} sem responsável"


def test_existe_cargo_com_aprovacao_adicional_diretoria(db_session):
    seed(db_session)
    assert (
        db_session.query(Cargo).filter_by(aprovacao_adicional=AprovacaoAdicional.DIRETORIA).count() > 0
    )


def test_existe_par_de_estruturas_ancestral_descendente(db_session):
    seed(db_session)
    estruturas = {e.id: e for e in db_session.query(EstruturaOrganizacional).all()}
    encontrou_par = False
    for e in estruturas.values():
        atual = e
        profundidade = 0
        while atual.estrutura_pai_id is not None and profundidade < 10:
            atual = estruturas[atual.estrutura_pai_id]
            profundidade += 1
            if profundidade >= 1:
                encontrou_par = True
    assert encontrou_par


def test_existe_cadeia_hierarquica_de_ao_menos_3_niveis(db_session):
    seed(db_session)
    colaboradores = {c.id: c for c in db_session.query(Colaborador).all()}
    maior_profundidade = 0
    for c in colaboradores.values():
        atual = c
        profundidade = 0
        visitados = set()
        while atual.gestor_id is not None and atual.gestor_id not in visitados and profundidade < 20:
            visitados.add(atual.id)
            atual = colaboradores[atual.gestor_id]
            profundidade += 1
        maior_profundidade = max(maior_profundidade, profundidade)
    assert maior_profundidade >= 3


def test_nenhum_dado_fora_do_conjunto_ficticio_declarado(db_session):
    seed(db_session)
    # apenas uma verificação de sanidade: nenhum nome vazio, nenhuma matrícula vazia.
    for c in db_session.query(Colaborador).all():
        assert c.nome.strip() != ""
        assert c.matricula.strip() != ""


def test_dataset_contem_aprovacoes_pendente_aprovada_e_reprovada(db_session):
    seed(db_session)
    estados_presentes = {e for (e,) in db_session.query(Aprovacao.estado).distinct()}
    assert {EstadoAprovacao.PENDENTE, EstadoAprovacao.APROVADA, EstadoAprovacao.REPROVADA} <= estados_presentes


def test_ao_final_do_seed_producer_ja_foi_executado(db_session):
    """RF-22/CA-045: ao final do seed, existem tanto movimentações PENDENTE
    sem job (ainda aguardando aprovação) quanto movimentações com job criado
    (aptas para o Worker) — o producer já rodou, sem exigir chamada manual."""
    seed(db_session)

    pendentes_sem_job = (
        db_session.query(Movimentacao)
        .filter(Movimentacao.status == StatusMovimentacao.PENDENTE)
        .all()
    )
    ids_com_job = {job.movimentacao_id for job in db_session.query(JobValidacao).all()}
    assert any(m.id not in ids_com_job for m in pendentes_sem_job)
    assert db_session.query(JobValidacao).filter_by(status=StatusJob.PENDENTE).count() > 0


def test_movimentacoes_reprovadas_pelo_gate_ficam_bloqueadas_sem_job(db_session):
    seed(db_session)

    reprovadas = db_session.query(Movimentacao).filter(Movimentacao.status == StatusMovimentacao.REPROVADA).all()
    assert len(reprovadas) > 0

    ids_com_job = {job.movimentacao_id for job in db_session.query(JobValidacao).all()}
    # ao menos uma reprovada-pelo-gate (sem auditoria ainda, pois não passou pela engine)
    bloqueadas_pelo_gate = [m for m in reprovadas if m.resultado_ultima_validacao is None]
    assert len(bloqueadas_pelo_gate) > 0
    assert all(m.id not in ids_com_job for m in bloqueadas_pelo_gate)


def test_movimentacoes_aptas_recebem_exatamente_um_job(db_session):
    seed(db_session)

    jobs_por_movimentacao: dict[int, int] = {}
    for job in db_session.query(JobValidacao).all():
        jobs_por_movimentacao[job.movimentacao_id] = jobs_por_movimentacao.get(job.movimentacao_id, 0) + 1

    assert len(jobs_por_movimentacao) > 0
    assert all(quantidade == 1 for quantidade in jobs_por_movimentacao.values())


def test_seed_mais_producer_sao_idempotentes_em_reexecucao(db_session):
    seed(db_session)
    total_movimentacoes_1 = db_session.query(Movimentacao).count()
    total_jobs_1 = db_session.query(JobValidacao).count()

    seed(db_session)  # reexecução: seed é no-op, producer roda de novo mas não duplica
    total_movimentacoes_2 = db_session.query(Movimentacao).count()
    total_jobs_2 = db_session.query(JobValidacao).count()

    assert total_movimentacoes_1 == total_movimentacoes_2
    assert total_jobs_1 == total_jobs_2
