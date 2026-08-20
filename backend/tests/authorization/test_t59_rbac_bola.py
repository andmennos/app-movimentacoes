"""T-59 — RBAC + BOLA (spec.md §2.3/§3, RC-08..RC-12). AUTH-08..11.

`LIDERANCA` não tem login de demonstração nesta entrega (RC-13 só cria
`admin`/`analistaRh`), mas o mecanismo de escopo precisa existir e ser
testável (RC-11/tasks T-59) — os testes abaixo mintam um JWT diretamente
para um `Usuario` perfil `LIDERANCA` persistido no banco de teste, sem
depender de fluxo de login (que continua restrito aos dois perfis de demo).
"""

from datetime import date

from app.models import PerfilUsuario
from app.security.jwt import create_access_token
from app.security.permissions import scopes_do_perfil
from tests.builders import ColaboradorBuilder, MovimentacaoBuilder, UsuarioBuilder


def _token_para(db_session, perfil, colaborador_id=None):
    usuario = UsuarioBuilder(perfil=perfil, colaborador_id=colaborador_id).build(db_session)
    db_session.commit()
    token, _ = create_access_token(usuario.id, usuario.perfil.value)
    return token


def _montar_subarvore(db_session):
    """diretor -> gerente -> analista (dentro); outsider é uma árvore separada."""
    diretor = ColaboradorBuilder(gestor_id=None).build(db_session)
    gerente = ColaboradorBuilder(gestor_id=diretor.id).build(db_session)
    analista = ColaboradorBuilder(gestor_id=gerente.id).build(db_session)
    outsider = ColaboradorBuilder(gestor_id=None).build(db_session)
    db_session.commit()
    return diretor, gerente, analista, outsider


def test_auth09_rh_analista_le_tudo_sem_filtro_organizacional(client, db_session):
    _diretor, _gerente, analista, outsider = _montar_subarvore(db_session)
    MovimentacaoBuilder(colaborador_id=analista.id).build(db_session)
    MovimentacaoBuilder(colaborador_id=outsider.id).build(db_session)
    db_session.commit()

    token = _token_para(db_session, PerfilUsuario.RH_ANALISTA)
    resposta = client.get("/movimentacoes", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 200
    assert resposta.json()["total"] == 2


def test_auth09_rh_analista_nao_tem_scope_de_aprovacao():
    assert "movimentacoes:approve" not in scopes_do_perfil(PerfilUsuario.RH_ANALISTA.value)
    assert "movimentacoes:approve" in scopes_do_perfil(PerfilUsuario.ADMIN.value)
    assert "movimentacoes:approve" in scopes_do_perfil(PerfilUsuario.RH_GESTOR.value)
    assert "movimentacoes:approve" in scopes_do_perfil(PerfilUsuario.LIDERANCA.value)


def test_rh_gestor_nao_tem_scope_de_criacao():
    assert "movimentacoes:create" not in scopes_do_perfil(PerfilUsuario.RH_GESTOR.value)


def test_auth10_lideranca_nao_recebe_objeto_fora_da_subarvore_na_listagem(client, db_session):
    diretor, _gerente, analista, outsider = _montar_subarvore(db_session)
    mov_dentro = MovimentacaoBuilder(colaborador_id=analista.id).build(db_session)
    MovimentacaoBuilder(colaborador_id=outsider.id).build(db_session)
    db_session.commit()

    token = _token_para(db_session, PerfilUsuario.LIDERANCA, colaborador_id=diretor.id)
    resposta = client.get("/movimentacoes", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    assert corpo["items"][0]["id"] == mov_dentro.id


def test_lideranca_ve_movimentacao_de_si_mesma(client, db_session):
    diretor, _gerente, _analista, _outsider = _montar_subarvore(db_session)
    mov_do_lider = MovimentacaoBuilder(colaborador_id=diretor.id).build(db_session)
    db_session.commit()

    token = _token_para(db_session, PerfilUsuario.LIDERANCA, colaborador_id=diretor.id)
    resposta = client.get(f"/movimentacoes/{mov_do_lider.id}", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 200


def test_auth11_id_direto_fora_da_subarvore_retorna_404(client, db_session):
    diretor, _gerente, _analista, outsider = _montar_subarvore(db_session)
    mov_fora = MovimentacaoBuilder(colaborador_id=outsider.id).build(db_session)
    db_session.commit()

    token = _token_para(db_session, PerfilUsuario.LIDERANCA, colaborador_id=diretor.id)
    resposta = client.get(f"/movimentacoes/{mov_fora.id}", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "MOVIMENTACAO_NAO_ENCONTRADA"


def test_lideranca_sem_colaborador_vinculado_nao_ve_nada(client, db_session):
    _diretor, _gerente, analista, _outsider = _montar_subarvore(db_session)
    MovimentacaoBuilder(colaborador_id=analista.id).build(db_session)
    db_session.commit()

    token = _token_para(db_session, PerfilUsuario.LIDERANCA, colaborador_id=None)
    resposta = client.get("/movimentacoes", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 200
    assert resposta.json()["total"] == 0


def test_validar_fora_da_subarvore_retorna_404_sem_revelar_existencia(client, db_session):
    diretor, _gerente, _analista, outsider = _montar_subarvore(db_session)
    mov_fora = MovimentacaoBuilder(colaborador_id=outsider.id).build(db_session)
    db_session.commit()

    token = _token_para(db_session, PerfilUsuario.LIDERANCA, colaborador_id=diretor.id)
    resposta = client.post(
        "/validar", json={"movimentacaoId": mov_fora.id}, headers={"Authorization": f"Bearer {token}"}
    )

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "MOVIMENTACAO_NAO_ENCONTRADA"


def test_rota_de_movimentacoes_sem_token_recebe_401(client):
    resposta = client.get("/movimentacoes")
    assert resposta.status_code == 401


def test_rota_de_validar_sem_token_recebe_401(client):
    resposta = client.post("/validar", json={"movimentacaoId": 1})
    assert resposta.status_code == 401
