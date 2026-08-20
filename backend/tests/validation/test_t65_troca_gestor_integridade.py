"""T-65 — troca de gestor: integridade do aprovador (spec.md §10.4).
TG-APR-01..03."""

from app.validation.engine import executar
from app.validation.troca_gestor import tg05_sem_ciclo_hierarquico, tg06_aprovacoes_integras
from tests.validation.factories import aprovacao_ref, colaborador_ref, contexto_troca_gestor
from app.validation.types import EstadoAprovacao, NoHierarquia, TipoAprovacao


def test_tg_apr01_wesley_origem_larissa_destino_integra():
    wesley = colaborador_ref()  # gestor atual
    larissa = colaborador_ref()  # novo gestor proposto
    ctx = contexto_troca_gestor(gestor_origem=wesley, gestor_destino=larissa)
    assert tg06_aprovacoes_integras(ctx) == []


def test_tg_apr02_inversao_falha_integridade_tg06():
    """Campos gestor_origem_id/gestor_destino_id trocados (Larissa aparece
    como GESTOR_ORIGEM, Wesley como GESTOR_DESTINO) — o colaborador
    continua tendo Wesley como gestor real: TG06 reprova a inversão."""
    wesley = colaborador_ref()
    larissa = colaborador_ref(cargo=None)
    colaborador = colaborador_ref(gestor_id=wesley.id)
    ctx = contexto_troca_gestor(colaborador=colaborador, gestor_origem=larissa, gestor_destino=wesley)

    codigos = [i.codigo for i in tg06_aprovacoes_integras(ctx)]
    assert "TG06" in codigos


def test_tg_apr03_tg05_continua_exclusivo_de_ciclo_hierarquico():
    """TG05 não reprova uma inversão simples (sem ciclo) — só quando o novo
    gestor proposto está, de fato, na própria cadeia descendente."""
    wesley = colaborador_ref()
    larissa = colaborador_ref()
    colaborador = colaborador_ref(gestor_id=wesley.id)
    ctx_invertido = contexto_troca_gestor(colaborador=colaborador, gestor_origem=larissa, gestor_destino=wesley)
    assert tg05_sem_ciclo_hierarquico(ctx_invertido) == []

    # Ciclo genuíno: novo gestor proposto é subordinado do próprio colaborador.
    subordinado_do_colaborador = colaborador_ref()
    ctx_ciclo = contexto_troca_gestor(
        colaborador=colaborador,
        gestor_origem=wesley,
        gestor_destino=subordinado_do_colaborador,
        cadeia={subordinado_do_colaborador.id: NoHierarquia(subordinado_do_colaborador.id, colaborador.id)},
    )
    codigos_ciclo = [i.codigo for i in tg05_sem_ciclo_hierarquico(ctx_ciclo)]
    assert codigos_ciclo == ["TG05"]


def test_engine_reprova_inversao_sob_tg06_nao_tg05():
    wesley = colaborador_ref()
    larissa = colaborador_ref(cargo=None)
    colaborador = colaborador_ref(gestor_id=wesley.id)
    ctx = contexto_troca_gestor(colaborador=colaborador, gestor_origem=larissa, gestor_destino=wesley)

    codigos = [i.codigo for i in executar(ctx)]
    assert "TG06" in codigos
    assert "TG05" not in codigos
