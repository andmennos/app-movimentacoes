"""T-85 — `BLOQUEADA` é terminal (spec.md RC-47). Reproduz o bug real do E2E:
DIRETORIA reprovada não pode deixar GESTOR_RH_ADICIONAL (etapa posterior,
nunca alcançada) aparecendo como "aguardando aprovação" em nenhum lugar —
nem no detalhe/timeline, nem em `/aprovacoes/pendentes`, nem como decisão
ainda aceita pela API."""

from app.models import AprovacaoAdicional, PerfilUsuario
from app.security.jwt import create_access_token
from tests.builders import CargoBuilder, ColaboradorBuilder, UsuarioBuilder


def _token(db_session, perfil, colaborador_id=None):
    usuario = UsuarioBuilder(perfil=perfil, colaborador_id=colaborador_id).build(db_session)
    db_session.commit()
    return usuario, create_access_token(usuario.id, usuario.perfil.value)[0]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _cadeia_com_lideranca(db_session):
    cargo_diretor = CargoBuilder(permite_gestao=True, papel_lideranca=AprovacaoAdicional.DIRETORIA).build(db_session)
    cargo_gerente = CargoBuilder(permite_gestao=True, papel_lideranca=AprovacaoAdicional.GERENCIA).build(db_session)
    cargo_coordenador = CargoBuilder(permite_gestao=True).build(db_session)
    diretor = ColaboradorBuilder(cargo_id=cargo_diretor.id, gestor_id=None, nome="Diretora Regina Alves").build(
        db_session
    )
    gerente = ColaboradorBuilder(cargo_id=cargo_gerente.id, gestor_id=diretor.id).build(db_session)
    coordenador = ColaboradorBuilder(cargo_id=cargo_coordenador.id, gestor_id=gerente.id).build(db_session)
    return diretor, gerente, coordenador


def _decidir(client, token, mov_id, tipo, decisao="APROVADA", justificativa=None):
    payload = {"decisao": decisao}
    if justificativa:
        payload["justificativa"] = justificativa
    return client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/{tipo}/decidir",
        json=payload,
        headers=_headers(token),
    )


def test_e2e05_e2e06_e2e07_diretoria_reprovada_bloqueia_terminalmente(client, db_session):
    _diretor, _gerente, coordenador = _cadeia_com_lideranca(db_session)
    origem = CargoBuilder(nivel=1, ordem_progressao=1, familia_cargo="Z").build(db_session)
    destino = CargoBuilder(
        nivel=2, ordem_progressao=2, familia_cargo="Z", aprovacao_adicional=AprovacaoAdicional.DIRETORIA
    ).build(db_session)
    colaborador = ColaboradorBuilder(cargo_id=origem.id, gestor_id=coordenador.id).build(db_session)
    # ADMIN decide tudo (RC-12/RC-53) — vincula a um colaborador nomeado
    # só para que a mensagem "reprovada por <nome>" seja determinística
    # neste teste (o `aprovador_id` persistido é sempre o do decisor real,
    # não o do aprovador esperado pela política — RC-12).
    admin_colaborador = ColaboradorBuilder(nome="Admin Teste").build(db_session)
    db_session.commit()

    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN, colaborador_id=admin_colaborador.id)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "PROMOCAO", "colaboradorId": colaborador.id, "cargoDestinoId": destino.id},
        headers=_headers(admin_token),
    )
    assert resposta.status_code == 201, resposta.text
    mov_id = resposta.json()["id"]

    assert _decidir(client, admin_token, mov_id, "GESTOR_ORIGEM").status_code == 200
    assert _decidir(client, admin_token, mov_id, "RH").status_code == 200

    # DIRETORIA reprovada por quem — GESTOR_RH_ADICIONAL (a última etapa do
    # bundle) fica PENDENTE no banco para sempre: nunca foi e nunca será
    # decidida, porque a ordem sequencial nunca a libera depois de BLOQUEADA.
    reprovacao = _decidir(client, admin_token, mov_id, "DIRETORIA", decisao="REPROVADA", justificativa="orçamento")
    assert reprovacao.status_code == 200
    assert reprovacao.json()["movimentacaoStatus"] == "BLOQUEADA"

    detalhe = client.get(f"/movimentacoes/{mov_id}", headers=_headers(admin_token)).json()
    assert detalhe["status"] == "BLOQUEADA"

    # E2E-06 — detalhe mostra a reprovação real como causa final, nunca uma
    # etapa posterior "aguardando".
    assert detalhe["motivoResumo"] == f"Bloqueada: DIRETORIA reprovada por {admin_colaborador.nome}."
    assert detalhe["impedimentos"] == [
        {
            "origem": "APROVACAO",
            "codigo": "APROVACAO_REPROVADA",
            "mensagem": f"Aprovação DIRETORIA reprovada por {admin_colaborador.nome}.",
        }
    ]
    assert not any("GESTOR_RH_ADICIONAL" in i["mensagem"] for i in detalhe["impedimentos"])
    # nenhum evento fictício de "aguardando" para a etapa nunca alcançada —
    # o único evento gerado pelo bloqueio é a reprovação real.
    assert not any("GESTOR_RH_ADICIONAL" in e["mensagem"] for e in detalhe["historicoProcessamento"])

    # E2E-07 — BLOQUEADA nunca aparece em /aprovacoes/pendentes, nem a etapa
    # já reprovada nem a nunca alcançada.
    pendentes = client.get("/aprovacoes/pendentes", headers=_headers(admin_token)).json()
    assert not any(p["movimentacaoId"] == mov_id for p in pendentes)

    # a etapa nunca alcançada continua tecnicamente PENDENTE no banco, mas a
    # API rejeita decidi-la — o workflow de aprovação já encerrou.
    tentativa_tardia = _decidir(client, admin_token, mov_id, "GESTOR_RH_ADICIONAL")
    assert tentativa_tardia.status_code == 409
    assert tentativa_tardia.json()["erro"]["codigo"] == "MOVIMENTACAO_NAO_AGUARDANDO_APROVACAO"


def test_reprovacao_em_etapa_inicial_de_transferencia_tambem_e_terminal(client, db_session):
    """Regressão fora do bundle de promoção: mesmo com etapas de mesma ordem
    (TRANSFERENCIA — GESTOR_ORIGEM/GESTOR_DESTINO/RH todas ordem 1), uma
    reprovação bloqueia as demais também, mesmo as "paralelas"."""
    from tests.builders import DepartamentoBuilder

    colaborador = ColaboradorBuilder().build(db_session)
    dep_destino = DepartamentoBuilder().build(db_session)
    db_session.commit()
    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "TRANSFERENCIA", "colaboradorId": colaborador.id, "departamentoDestinoId": dep_destino.id},
        headers=_headers(admin_token),
    )
    mov_id = resposta.json()["id"]

    reprovacao = _decidir(client, admin_token, mov_id, "GESTOR_ORIGEM", decisao="REPROVADA")
    assert reprovacao.status_code == 200
    assert reprovacao.json()["movimentacaoStatus"] == "BLOQUEADA"

    tentativa = _decidir(client, admin_token, mov_id, "GESTOR_DESTINO")
    assert tentativa.status_code == 409
    assert tentativa.json()["erro"]["codigo"] == "MOVIMENTACAO_NAO_AGUARDANDO_APROVACAO"

    detalhe = client.get(f"/movimentacoes/{mov_id}", headers=_headers(admin_token)).json()
    assert len(detalhe["impedimentos"]) == 1
    assert detalhe["impedimentos"][0]["codigo"] == "APROVACAO_REPROVADA"
    assert detalhe["impedimentos"][0]["mensagem"].startswith("Aprovação GESTOR_ORIGEM reprovada")
    assert not any(i["codigo"] == "APROVACAO_PENDENTE" for i in detalhe["impedimentos"])
