"""T-61 — ApprovalPolicy dinâmica (spec.md §5). APR-01..08."""

from app.validation.aprovacoes import exigencias_para
from app.validation.types import TipoAprovacao
from tests.validation.factories import (
    colaborador_ref,
    contexto_centro_custo,
    contexto_estrutura,
    contexto_promocao,
    contexto_transferencia,
    contexto_troca_gestor,
)


def _tipos(exigencias):
    return {e.tipo for e in exigencias}


def test_apr01_perfil_comum_nunca_autoaprova_transferencia():
    """LIDERANCA como GESTOR_ORIGEM: a etapa some da matriz — nunca fica
    disponível para o próprio solicitante decidir."""
    gestor_origem = colaborador_ref()
    ctx = contexto_transferencia(
        responsaveis_derivados={"GESTOR_ORIGEM": gestor_origem, "GESTOR_DESTINO": colaborador_ref()},
        solicitante_perfil="LIDERANCA",
        solicitante_colaborador_id=gestor_origem.id,
    )
    tipos = _tipos(exigencias_para(ctx))
    assert TipoAprovacao.GESTOR_ORIGEM not in tipos
    assert tipos == {TipoAprovacao.GESTOR_DESTINO, TipoAprovacao.RH}


def test_apr02_admin_nao_aciona_substituicao_matriz_completa():
    """ADMIN como GESTOR_ORIGEM: a matriz continua completa (RC-07) — a
    exceção de autoaprovação é resolvida na autorização da decisão (T-62),
    não na composição das exigências."""
    gestor_origem = colaborador_ref()
    ctx = contexto_transferencia(
        responsaveis_derivados={"GESTOR_ORIGEM": gestor_origem, "GESTOR_DESTINO": colaborador_ref()},
        solicitante_perfil="ADMIN",
        solicitante_colaborador_id=gestor_origem.id,
    )
    tipos = _tipos(exigencias_para(ctx))
    assert tipos == {TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO, TipoAprovacao.RH}


def test_apr03_transferencia_solicitada_por_gestor_origem_exige_destino_e_rh():
    gestor_origem = colaborador_ref()
    ctx = contexto_transferencia(
        responsaveis_derivados={"GESTOR_ORIGEM": gestor_origem, "GESTOR_DESTINO": colaborador_ref()},
        solicitante_perfil="LIDERANCA",
        solicitante_colaborador_id=gestor_origem.id,
    )
    assert _tipos(exigencias_para(ctx)) == {TipoAprovacao.GESTOR_DESTINO, TipoAprovacao.RH}


def test_apr04_transferencia_solicitada_por_gestor_destino_exige_origem_e_rh():
    gestor_destino = colaborador_ref()
    ctx = contexto_transferencia(
        responsaveis_derivados={"GESTOR_ORIGEM": colaborador_ref(), "GESTOR_DESTINO": gestor_destino},
        solicitante_perfil="LIDERANCA",
        solicitante_colaborador_id=gestor_destino.id,
    )
    assert _tipos(exigencias_para(ctx)) == {TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.RH}


def test_apr05_rh_analista_solicitante_substitui_rh_por_gestor_rh_transferencia():
    ctx = contexto_transferencia(solicitante_perfil="RH_ANALISTA", solicitante_colaborador_id=None)
    tipos = _tipos(exigencias_para(ctx))
    assert TipoAprovacao.RH not in tipos
    assert tipos == {TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO, TipoAprovacao.GESTOR_RH}


def test_rh_analista_substitui_rh_por_gestor_rh_troca_gestor():
    ctx = contexto_troca_gestor(solicitante_perfil="RH_ANALISTA")
    tipos = _tipos(exigencias_para(ctx))
    assert tipos == {TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO, TipoAprovacao.GESTOR_RH}


def test_rh_analista_substitui_rh_por_gestor_rh_centro_custo():
    ctx = contexto_centro_custo(solicitante_perfil="RH_ANALISTA")
    tipos = _tipos(exigencias_para(ctx))
    assert tipos == {TipoAprovacao.GESTOR_DESTINO, TipoAprovacao.GESTOR_RH}


def test_rh_analista_substitui_rh_por_gestor_rh_estrutura():
    ctx = contexto_estrutura(solicitante_perfil="RH_ANALISTA")
    tipos = _tipos(exigencias_para(ctx))
    assert tipos == {TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_RH}


def test_apr06_promocao_rh_tem_ordem_apos_hierarquica():
    ctx = contexto_promocao(
        responsaveis_derivados={"GESTOR_ORIGEM": colaborador_ref(), "GESTOR_SUPERIOR": None},
    )
    exigencias = exigencias_para(ctx)
    hierarquica = next(e for e in exigencias if e.tipo == TipoAprovacao.GESTOR_ORIGEM)
    rh = next(e for e in exigencias if e.tipo == TipoAprovacao.RH)
    assert hierarquica.ordem < rh.ordem


def test_apr07_gestor_solicitante_de_promocao_e_substituido_pelo_superior():
    gestor_atual = colaborador_ref()
    superior = colaborador_ref()
    ctx = contexto_promocao(
        responsaveis_derivados={"GESTOR_ORIGEM": gestor_atual, "GESTOR_SUPERIOR": None},
        solicitante_perfil="LIDERANCA",
        solicitante_colaborador_id=gestor_atual.id,
        solicitante_superior_colaborador_id=superior.id,
    )
    exigencias = exigencias_para(ctx)
    tipos = _tipos(exigencias)
    assert TipoAprovacao.GESTOR_ORIGEM not in tipos
    assert TipoAprovacao.GESTOR_SUPERIOR in tipos
    assert TipoAprovacao.RH in tipos
    hierarquica = next(e for e in exigencias if e.tipo == TipoAprovacao.GESTOR_SUPERIOR)
    assert hierarquica.ordem == 1


def test_apr08_solicitante_topo_sem_superior_usa_rh_gestor_sem_segunda_etapa_rh():
    gestor_atual = colaborador_ref()
    ctx = contexto_promocao(
        responsaveis_derivados={"GESTOR_ORIGEM": gestor_atual, "GESTOR_SUPERIOR": None},
        solicitante_perfil="LIDERANCA",
        solicitante_colaborador_id=gestor_atual.id,
        solicitante_superior_colaborador_id=None,
    )
    exigencias = exigencias_para(ctx)
    assert len(exigencias) == 1
    assert exigencias[0].tipo == TipoAprovacao.GESTOR_RH
    assert exigencias[0].perfil_esperado == "RH_GESTOR"


def test_promocao_rh_analista_mantem_gestor_atual_e_troca_rh_por_gestor_rh():
    gestor_atual = colaborador_ref()
    ctx = contexto_promocao(
        responsaveis_derivados={"GESTOR_ORIGEM": gestor_atual, "GESTOR_SUPERIOR": None},
        solicitante_perfil="RH_ANALISTA",
        solicitante_colaborador_id=None,
    )
    tipos = _tipos(exigencias_para(ctx))
    assert tipos == {TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_RH}


def test_troca_gestor_solicitante_e_gestor_origem_remove_propria_etapa():
    gestor_origem = colaborador_ref()
    ctx = contexto_troca_gestor(
        responsaveis_derivados={"GESTOR_ORIGEM": gestor_origem, "GESTOR_DESTINO": colaborador_ref()},
        solicitante_perfil="LIDERANCA",
        solicitante_colaborador_id=gestor_origem.id,
    )
    assert _tipos(exigencias_para(ctx)) == {TipoAprovacao.GESTOR_DESTINO, TipoAprovacao.RH}


def test_centro_custo_solicitante_e_responsavel_destino_so_exige_rh():
    responsavel = colaborador_ref()
    ctx = contexto_centro_custo(
        responsaveis_derivados={"GESTOR_DESTINO": responsavel},
        solicitante_perfil="LIDERANCA",
        solicitante_colaborador_id=responsavel.id,
    )
    assert _tipos(exigencias_para(ctx)) == {TipoAprovacao.RH}


def test_estrutura_solicitante_e_gestor_origem_so_exige_rh():
    gestor_origem = colaborador_ref()
    ctx = contexto_estrutura(
        responsaveis_derivados={"GESTOR_ORIGEM": gestor_origem},
        solicitante_perfil="LIDERANCA",
        solicitante_colaborador_id=gestor_origem.id,
    )
    assert _tipos(exigencias_para(ctx)) == {TipoAprovacao.RH}


def test_sem_solicitante_usa_matriz_base_completa():
    """Movimentações sem `solicitante_usuario_id` (dados históricos do seed
    pré-autenticação) sempre recebem a matriz-base, sem substituição."""
    ctx = contexto_transferencia()
    assert _tipos(exigencias_para(ctx)) == {
        TipoAprovacao.GESTOR_ORIGEM,
        TipoAprovacao.GESTOR_DESTINO,
        TipoAprovacao.RH,
    }
