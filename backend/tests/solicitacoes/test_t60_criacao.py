"""T-60 — criação de solicitações via API (spec.md §4). REQ-01..05."""

from app.models import EstadoAprovacao, HistoricoProcessamento, PerfilUsuario, TipoEventoProcessamento
from app.security.jwt import create_access_token
from tests.builders import (
    CargoBuilder,
    CentroCustoBuilder,
    ColaboradorBuilder,
    DepartamentoBuilder,
    UsuarioBuilder,
)


def _token(db_session, perfil, colaborador_id=None):
    usuario = UsuarioBuilder(perfil=perfil, colaborador_id=colaborador_id).build(db_session)
    db_session.commit()
    return usuario, create_access_token(usuario.id, usuario.perfil.value)[0]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _montar_subarvore(db_session):
    diretor = ColaboradorBuilder(gestor_id=None).build(db_session)
    gerente = ColaboradorBuilder(gestor_id=diretor.id).build(db_session)
    analista = ColaboradorBuilder(gestor_id=gerente.id).build(db_session)
    outsider = ColaboradorBuilder(gestor_id=None).build(db_session)
    db_session.commit()
    return diretor, gerente, analista, outsider


def test_req01_lideranca_cria_transferencia_para_subordinado_da_subarvore(client, db_session):
    diretor, _gerente, analista, _outsider = _montar_subarvore(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.LIDERANCA, colaborador_id=diretor.id)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": analista.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(token),
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["tipo"] == "TRANSFERENCIA"
    assert corpo["status"] == "AGUARDANDO_APROVACAO"


def test_req02_lideranca_nao_cria_para_objeto_fora_do_escopo(client, db_session):
    diretor, _gerente, _analista, outsider = _montar_subarvore(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.LIDERANCA, colaborador_id=diretor.id)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": outsider.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(token),
    )

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "COLABORADOR_NAO_ENCONTRADO"


def test_req03_rh_analista_cria_para_qualquer_colaborador(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    cc_destino = CentroCustoBuilder().build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.RH_ANALISTA)

    resposta = client.post(
        "/movimentacoes",
        json={
            "tipo": "MUDANCA_CENTRO_CUSTO",
            "colaboradorId": colaborador.id,
            "centroCustoDestinoId": cc_destino.id,
        },
        headers=_headers(token),
    )

    assert resposta.status_code == 201


def test_rh_gestor_nao_pode_criar_solicitacao(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    cc_destino = CentroCustoBuilder().build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.RH_GESTOR)

    resposta = client.post(
        "/movimentacoes",
        json={
            "tipo": "MUDANCA_CENTRO_CUSTO",
            "colaboradorId": colaborador.id,
            "centroCustoDestinoId": cc_destino.id,
        },
        headers=_headers(token),
    )

    assert resposta.status_code == 403


def test_req04_payload_nao_aceita_campos_derivados_pelo_backend(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={
            "tipo": "TRANSFERENCIA",
            "colaboradorId": colaborador.id,
            "departamentoDestinoId": dep_destino.id,
            "solicitanteUsuarioId": 99999,
            "status": "APROVADA",
        },
        headers=_headers(token),
    )

    assert resposta.status_code == 422


def test_req04_origem_e_solicitante_sao_derivados_pelo_backend(client, db_session):
    dep_origem = DepartamentoBuilder().build(db_session)
    colaborador = ColaboradorBuilder(departamento_id=dep_origem.id).build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": colaborador.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(token),
    )
    mov_id = resposta.json()["id"]

    from app.models import Movimentacao

    mov = db_session.get(Movimentacao, mov_id)
    assert mov.departamento_origem_id == dep_origem.id
    assert mov.solicitante_usuario_id == usuario.id


def test_req05_criacao_persiste_solicitacao_recebida(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    cargo_destino = CargoBuilder(ordem_progressao=999).build(db_session)
    db_session.commit()
    usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "PROMOCAO", "colaboradorId": colaborador.id, "cargoDestinoId": cargo_destino.id},
        headers=_headers(token),
    )
    mov_id = resposta.json()["id"]

    eventos = (
        db_session.query(HistoricoProcessamento)
        .filter_by(movimentacao_id=mov_id, tipo_evento=TipoEventoProcessamento.SOLICITACAO_RECEBIDA)
        .all()
    )
    assert len(eventos) == 1
    assert eventos[0].solicitante_usuario_id == usuario.id


def test_criacao_gera_aprovacoes_pendentes_do_tipo(client, db_session):
    from app.models import Aprovacao, TipoAprovacao

    colaborador = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": colaborador.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(token),
    )
    mov_id = resposta.json()["id"]

    aprovacoes = db_session.query(Aprovacao).filter_by(movimentacao_id=mov_id).all()
    tipos = {a.tipo for a in aprovacoes}
    assert tipos == {TipoAprovacao.GESTOR_ORIGEM, TipoAprovacao.GESTOR_DESTINO, TipoAprovacao.RH}
    assert all(a.estado == EstadoAprovacao.PENDENTE for a in aprovacoes)


def test_referencia_destino_inexistente_retorna_404(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": colaborador.id, "departamentoDestinoId": 999999},
        headers=_headers(token),
    )

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "REFERENCIA_NAO_ENCONTRADA"


def test_e2e08_post_troca_gestor_deriva_origem_do_gestor_atual(client, db_session):
    """spec.md RC-48/T-86 — a origem (`gestorOrigem`) nunca vem do payload."""
    from app.models import Movimentacao

    gestor_atual = ColaboradorBuilder().build(db_session)
    novo_gestor = ColaboradorBuilder().build(db_session)
    colaborador = ColaboradorBuilder(gestor_id=gestor_atual.id).build(db_session)
    db_session.commit()
    usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "TROCA_GESTOR", "colaboradorId": colaborador.id, "gestorDestinoId": novo_gestor.id},
        headers=_headers(token),
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["tipo"] == "TROCA_GESTOR"
    assert corpo["status"] == "AGUARDANDO_APROVACAO"

    mov = db_session.get(Movimentacao, corpo["id"])
    assert mov.gestor_origem_id == gestor_atual.id
    assert mov.gestor_destino_id == novo_gestor.id
    assert mov.solicitante_usuario_id == usuario.id


def test_e2e09_post_alteracao_estrutura_deriva_origem_da_estrutura_atual(client, db_session):
    from app.models import EstruturaOrganizacional, Movimentacao

    estrutura_origem = EstruturaOrganizacional(codigo="EST-ORIG-T86", nome="Origem", ativo=True, nivel=1)
    estrutura_destino = EstruturaOrganizacional(codigo="EST-DEST-T86", nome="Destino", ativo=True, nivel=1)
    db_session.add_all([estrutura_origem, estrutura_destino])
    db_session.flush()
    colaborador = ColaboradorBuilder(estrutura_id=estrutura_origem.id).build(db_session)
    db_session.commit()
    usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={
            "tipo": "ALTERACAO_ESTRUTURA",
            "colaboradorId": colaborador.id,
            "estruturaDestinoId": estrutura_destino.id,
        },
        headers=_headers(token),
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["tipo"] == "ALTERACAO_ESTRUTURA"

    mov = db_session.get(Movimentacao, corpo["id"])
    assert mov.estrutura_origem_id == estrutura_origem.id
    assert mov.estrutura_destino_id == estrutura_destino.id
    assert mov.solicitante_usuario_id == usuario.id


def test_troca_gestor_payload_nao_aceita_gestor_origem_forjado(client, db_session):
    gestor_atual = ColaboradorBuilder().build(db_session)
    outro_gestor = ColaboradorBuilder().build(db_session)
    novo_gestor = ColaboradorBuilder().build(db_session)
    colaborador = ColaboradorBuilder(gestor_id=gestor_atual.id).build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={
            "tipo": "TROCA_GESTOR",
            "colaboradorId": colaborador.id,
            "gestorDestinoId": novo_gestor.id,
            "gestorOrigemId": outro_gestor.id,
        },
        headers=_headers(token),
    )

    assert resposta.status_code == 422


def test_troca_gestor_destino_inexistente_retorna_404(client, db_session):
    colaborador = ColaboradorBuilder().build(db_session)
    db_session.commit()
    _usuario, token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "TROCA_GESTOR", "colaboradorId": colaborador.id, "gestorDestinoId": 999999},
        headers=_headers(token),
    )

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "REFERENCIA_NAO_ENCONTRADA"


def test_criar_movimentacao_sem_token_recebe_401(client):
    resposta = client.post(
        "/movimentacoes", json={"tipo": "TRANSFERENCIA", "colaboradorId": 1, "departamentoDestinoId": 1}
    )
    assert resposta.status_code == 401
