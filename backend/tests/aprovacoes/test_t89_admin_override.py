"""T-89 — ADMIN preserva override master; a exceção não é herdada por
RH_GESTOR/RH_ANALISTA/LIDERANCA (spec.md RC-53). E2E-17."""

from app.models import PerfilUsuario
from app.security.jwt import create_access_token
from tests.builders import ColaboradorBuilder, DepartamentoBuilder, UsuarioBuilder


def _token(db_session, perfil, colaborador_id=None):
    usuario = UsuarioBuilder(perfil=perfil, colaborador_id=colaborador_id).build(db_session)
    db_session.commit()
    return usuario, create_access_token(usuario.id, usuario.perfil.value)[0]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _subarvore_isolada(db_session):
    """Uma subárvore de liderança completamente fora de qualquer outra
    hierarquia do teste, para provar que BOLA de LIDERANCA a isola e que
    ADMIN a atravessa mesmo assim."""
    lider = ColaboradorBuilder(gestor_id=None, nome="Líder Isolado").build(db_session)
    subordinado = ColaboradorBuilder(gestor_id=lider.id, nome="Subordinado Isolado").build(db_session)
    return lider, subordinado


def test_e2e17_admin_consulta_qualquer_movimentacao_fora_de_qualquer_subarvore(client, db_session):
    _lider, subordinado = _subarvore_isolada(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()

    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN)
    criado = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": subordinado.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(admin_token),
    )
    assert criado.status_code == 201

    detalhe = client.get(f"/movimentacoes/{criado.json()['id']}", headers=_headers(admin_token))
    assert detalhe.status_code == 200


def test_e2e17_lideranca_fora_da_subarvore_recebe_404_onde_admin_recebe_200(client, db_session):
    lider_dono, subordinado = _subarvore_isolada(db_session)
    outro_lider = ColaboradorBuilder(gestor_id=None, nome="Outro Líder").build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()

    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN)
    mov_id = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": subordinado.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(admin_token),
    ).json()["id"]

    _outro, outro_token = _token(db_session, PerfilUsuario.LIDERANCA, colaborador_id=outro_lider.id)
    fora = client.get(f"/movimentacoes/{mov_id}", headers=_headers(outro_token))
    assert fora.status_code == 404
    assert fora.json()["erro"]["codigo"] == "MOVIMENTACAO_NAO_ENCONTRADA"

    _dono, dono_token = _token(db_session, PerfilUsuario.LIDERANCA, colaborador_id=lider_dono.id)
    dentro = client.get(f"/movimentacoes/{mov_id}", headers=_headers(dono_token))
    assert dentro.status_code == 200

    admin_ve = client.get(f"/movimentacoes/{mov_id}", headers=_headers(admin_token))
    assert admin_ve.status_code == 200


def test_e2e17_admin_cria_movimentacao_para_colaborador_fora_de_qualquer_subarvore(client, db_session):
    _lider, subordinado = _subarvore_isolada(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": subordinado.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(admin_token),
    )
    assert resposta.status_code == 201


def test_e2e17_admin_decide_aprovacao_de_movimentacao_fora_de_qualquer_subarvore(client, db_session):
    _lider, subordinado = _subarvore_isolada(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN)

    mov_id = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": subordinado.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(admin_token),
    ).json()["id"]

    decisao = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/RH/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(admin_token),
    )
    assert decisao.status_code == 200


def test_e2e17_admin_pode_decidir_a_propria_solicitacao(client, db_session):
    """RC-12/RC-53 — ADMIN é a única exceção que pode aprovar a própria
    solicitação; perfis comuns nunca autoaprovam (RC-07)."""
    colaborador_admin = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder(gestor_id=colaborador_admin.id).build(db_session)
    db_session.commit()
    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN, colaborador_id=colaborador_admin.id)

    mov_id = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": colaborador_admin.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(admin_token),
    ).json()["id"]

    decisao = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/GESTOR_DESTINO/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(admin_token),
    )
    assert decisao.status_code == 200


def test_override_nao_e_herdado_por_rh_gestor(client, db_session):
    """RC-53 — a exceção de override é exclusiva do ADMIN; RH_GESTOR
    continua sujeito à autorização normal por tipo/perfil esperado."""
    _lider, subordinado = _subarvore_isolada(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN)

    mov_id = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": subordinado.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(admin_token),
    ).json()["id"]

    # RH_GESTOR não é o perfil esperado de GESTOR_ORIGEM (pessoa específica) —
    # sem override, a decisão é negada mesmo enxergando a movimentação.
    _rh_gestor, rh_gestor_token = _token(db_session, PerfilUsuario.RH_GESTOR)
    negado = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/GESTOR_ORIGEM/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(rh_gestor_token),
    )
    assert negado.status_code == 403


def test_override_nao_e_herdado_por_rh_analista(client, db_session):
    """RC-53/RC-09 — RH_ANALISTA lê e cria, mas não aprova nada, nem com
    override — diferente de ADMIN."""
    colaborador = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN)
    mov_id = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": colaborador.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(admin_token),
    ).json()["id"]

    _analista, analista_token = _token(db_session, PerfilUsuario.RH_ANALISTA)
    negado = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/RH/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(analista_token),
    )
    assert negado.status_code == 403


def test_override_nao_e_herdado_por_lideranca_fora_da_subarvore(client, db_session):
    """RC-53 — LIDERANCA continua limitada à própria subárvore; só ADMIN
    atravessa qualquer departamento/subárvore."""
    _lider, subordinado = _subarvore_isolada(db_session)
    outro_lider = ColaboradorBuilder(gestor_id=None, nome="Líder Sem Relação").build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN)

    mov_id = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": subordinado.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(admin_token),
    ).json()["id"]

    _outro, outro_token = _token(db_session, PerfilUsuario.LIDERANCA, colaborador_id=outro_lider.id)
    negado = client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/GESTOR_ORIGEM/decidir",
        json={"decisao": "APROVADA"},
        headers=_headers(outro_token),
    )
    assert negado.status_code == 404
    assert negado.json()["erro"]["codigo"] == "MOVIMENTACAO_NAO_ENCONTRADA"
