"""T-75 — aprovação adicional de promoção: liderança concreta (via
`Cargo.papel_lideranca`) + `GESTOR_RH_ADICIONAL` (spec.md §5.4/RC-36/RC-37/
RC-38), e a dedup de aprovador quando duas exigências de pessoa específica
resolvem para o mesmo colaborador (RC-42, decisão do candidato nesta
revisão — documentada em ADR-0014)."""

from app.models import AprovacaoAdicional, EstadoAprovacao, PerfilUsuario, StatusMovimentacao
from app.security.jwt import create_access_token
from app.services.exceptions import ApprovadorHierarquicoNaoResolvido
from tests.builders import CargoBuilder, ColaboradorBuilder, UsuarioBuilder


def _token(db_session, perfil, colaborador_id=None):
    usuario = UsuarioBuilder(perfil=perfil, colaborador_id=colaborador_id).build(db_session)
    db_session.commit()
    return usuario, create_access_token(usuario.id, usuario.perfil.value)[0]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _cadeia_com_lideranca(db_session):
    """diretor (papel_lideranca=DIRETORIA) <- gerente (papel_lideranca=
    GERENCIA) <- coordenador (sem papel) <- colaborador."""
    cargo_diretor = CargoBuilder(permite_gestao=True, papel_lideranca=AprovacaoAdicional.DIRETORIA).build(db_session)
    cargo_gerente = CargoBuilder(permite_gestao=True, papel_lideranca=AprovacaoAdicional.GERENCIA).build(db_session)
    cargo_coordenador = CargoBuilder(permite_gestao=True).build(db_session)
    diretor = ColaboradorBuilder(cargo_id=cargo_diretor.id, gestor_id=None).build(db_session)
    gerente = ColaboradorBuilder(cargo_id=cargo_gerente.id, gestor_id=diretor.id).build(db_session)
    coordenador = ColaboradorBuilder(cargo_id=cargo_coordenador.id, gestor_id=gerente.id).build(db_session)
    return diretor, gerente, coordenador


def _cargo_origem_destino(db_session, aprovacao_adicional):
    origem = CargoBuilder(nivel=1, ordem_progressao=1, familia_cargo="Y").build(db_session)
    destino = CargoBuilder(
        nivel=2, ordem_progressao=2, familia_cargo="Y", aprovacao_adicional=aprovacao_adicional
    ).build(db_session)
    return origem, destino


def _decidir(client, token, mov_id, tipo, decisao="APROVADA"):
    return client.post(
        f"/movimentacoes/{mov_id}/aprovacoes/{tipo}/decidir",
        json={"decisao": decisao},
        headers=_headers(token),
    )


def test_promocao_gerencia_gera_bundle_de_quatro_etapas_na_ordem_certa(client, db_session):
    """plan.md §23.3 — hierárquica -> RH/GESTOR_RH -> GERENCIA (pessoa
    concreta) -> GESTOR_RH_ADICIONAL, cada uma só decidível depois da
    anterior."""
    diretor, gerente, coordenador = _cadeia_com_lideranca(db_session)
    origem, destino = _cargo_origem_destino(db_session, AprovacaoAdicional.GERENCIA)
    colaborador = ColaboradorBuilder(cargo_id=origem.id, gestor_id=coordenador.id).build(db_session)
    db_session.commit()

    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "PROMOCAO", "colaboradorId": colaborador.id, "cargoDestinoId": destino.id},
        headers=_headers(admin_token),
    )
    assert resposta.status_code == 201, resposta.text
    mov_id = resposta.json()["id"]

    # GERENCIA ainda não deve aparecer nas pendências antes da hierárquica/RH.
    pendentes = client.get("/aprovacoes/pendentes", headers=_headers(admin_token)).json()
    tipos_pendentes = {p["tipo"] for p in pendentes if p["movimentacaoId"] == mov_id}
    assert tipos_pendentes == {"GESTOR_ORIGEM"}

    assert _decidir(client, admin_token, mov_id, "GESTOR_ORIGEM").status_code == 200

    pendentes = client.get("/aprovacoes/pendentes", headers=_headers(admin_token)).json()
    tipos_pendentes = {p["tipo"] for p in pendentes if p["movimentacaoId"] == mov_id}
    assert tipos_pendentes == {"RH"}, "GERENCIA/GESTOR_RH_ADICIONAL não podem aparecer antes de RH (RC-35)"

    assert _decidir(client, admin_token, mov_id, "RH").status_code == 200

    pendentes = client.get("/aprovacoes/pendentes", headers=_headers(admin_token)).json()
    tipos_pendentes = {p["tipo"] for p in pendentes if p["movimentacaoId"] == mov_id}
    assert tipos_pendentes == {"GERENCIA"}, "GESTOR_RH_ADICIONAL não pode aparecer antes de GERENCIA (RC-35)"

    assert _decidir(client, admin_token, mov_id, "GERENCIA").status_code == 200

    pendentes = client.get("/aprovacoes/pendentes", headers=_headers(admin_token)).json()
    tipos_pendentes = {p["tipo"] for p in pendentes if p["movimentacaoId"] == mov_id}
    assert tipos_pendentes == {"GESTOR_RH_ADICIONAL"}

    resp_decisao = _decidir(client, admin_token, mov_id, "GESTOR_RH_ADICIONAL")
    assert resp_decisao.status_code == 200

    detalhe = client.get(f"/movimentacoes/{mov_id}", headers=_headers(admin_token)).json()
    tipos_aprovados = {a["tipo"] for a in detalhe["aprovacoes"] if a["estado"] == "APROVADA"}
    assert tipos_aprovados == {"GESTOR_ORIGEM", "RH", "GERENCIA", "GESTOR_RH_ADICIONAL"}
    # a resolução de QUEM é o aprovador esperado de GERENCIA (a pessoa
    # concreta via papel_lideranca, não um perfil genérico) é verificada
    # diretamente em test_promocao_diretoria_resolve_pessoa_diferente_de_gerencia
    # e em test_auto_colapso_mesma_pessoa_satisfaz_gestor_origem_e_gerencia —
    # aqui o ADMIN decide por override (RC-12), então o aprovador persistido
    # é o próprio ADMIN, não a pessoa esperada (comportamento correto e
    # documentado do override, não uma falha de resolução).


def test_promocao_diretoria_resolve_pessoa_diferente_de_gerencia(db_session):
    """RC-38 — a liderança resolvida depende do papel exigido: GERENCIA
    resolve para "gerente", DIRETORIA para "diretor", nunca por nome."""
    from app.services.movimentacao_service import _resolver_lideranca

    diretor, gerente, coordenador = _cadeia_com_lideranca(db_session)
    colaborador = ColaboradorBuilder(gestor_id=coordenador.id).build(db_session)
    db_session.commit()

    resolvido_gerencia = _resolver_lideranca(colaborador, AprovacaoAdicional.GERENCIA)
    resolvido_diretoria = _resolver_lideranca(colaborador, AprovacaoAdicional.DIRETORIA)

    assert resolvido_gerencia.id == gerente.id
    assert resolvido_diretoria.id == diretor.id


def test_criacao_falha_409_quando_lideranca_nao_resolvida_sem_persistencia_parcial(client, db_session):
    """RC-38 — sem ninguém com papel_lideranca correspondente na cadeia, a
    criação falha explicitamente e nada fica persistido."""
    cargo_isolado = CargoBuilder(permite_gestao=True).build(db_session)  # sem papel_lideranca
    gestor_sem_papel = ColaboradorBuilder(cargo_id=cargo_isolado.id, gestor_id=None).build(db_session)
    origem, destino = _cargo_origem_destino(db_session, AprovacaoAdicional.DIRETORIA)
    colaborador = ColaboradorBuilder(cargo_id=origem.id, gestor_id=gestor_sem_papel.id).build(db_session)
    db_session.commit()

    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN)

    from app.models import Movimentacao

    total_antes = db_session.query(Movimentacao).count()

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "PROMOCAO", "colaboradorId": colaborador.id, "cargoDestinoId": destino.id},
        headers=_headers(admin_token),
    )

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "APROVADOR_HIERARQUICO_NAO_RESOLVIDO"
    # a fixture `client` de teste não replica o rollback-on-exception real de
    # app.database.get_db (só faz yield direto da sessão) — sem isso, o
    # flush() feito dentro de SolicitacaoService.criar ficaria visível nesta
    # mesma sessão mesmo sem commit. Em produção, get_db() já faz esse
    # rollback sozinho quando a exceção propaga; aqui replicamos
    # explicitamente para provar a ausência de persistência parcial.
    db_session.rollback()
    assert db_session.query(Movimentacao).count() == total_antes, "não pode haver persistência parcial"


def test_auto_colapso_mesma_pessoa_satisfaz_gestor_origem_e_gerencia(client, db_session):
    """RC-42 — quando GESTOR_ORIGEM e GERENCIA resolvem para a mesma pessoa
    real (o colaborador reporta diretamente ao "gerente"), uma única
    decisão real satisfaz as duas, sem segundo clique — mas a auditoria
    preserva as duas linhas de Aprovacao."""
    diretor, gerente, _coordenador = _cadeia_com_lideranca(db_session)
    origem, destino = _cargo_origem_destino(db_session, AprovacaoAdicional.GERENCIA)
    # gestor_id = gerente.id diretamente: GESTOR_ORIGEM e GERENCIA resolvem
    # para a mesma pessoa (gerente).
    colaborador = ColaboradorBuilder(cargo_id=origem.id, gestor_id=gerente.id).build(db_session)
    db_session.commit()

    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN)
    # o "gerente" decide como si mesmo (não via override do ADMIN) — é
    # exatamente essa identidade real que precisa coincidir nas duas etapas.
    _gerente_usuario, gerente_token = _token(db_session, PerfilUsuario.ADMIN, colaborador_id=gerente.id)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "PROMOCAO", "colaboradorId": colaborador.id, "cargoDestinoId": destino.id},
        headers=_headers(admin_token),
    )
    assert resposta.status_code == 201, resposta.text
    mov_id = resposta.json()["id"]

    assert _decidir(client, gerente_token, mov_id, "GESTOR_ORIGEM").status_code == 200
    assert _decidir(client, admin_token, mov_id, "RH").status_code == 200

    detalhe = client.get(f"/movimentacoes/{mov_id}", headers=_headers(admin_token)).json()
    aprovacao_gerencia = next(a for a in detalhe["aprovacoes"] if a["tipo"] == "GERENCIA")
    assert aprovacao_gerencia["estado"] == "APROVADA", "auto-satisfeita sem decisão explícita"
    assert aprovacao_gerencia["aprovador"]["id"] == gerente.id

    # a linha continua existindo separadamente — a auditoria não apaga a
    # informação de que havia duas exigências distintas.
    tipos = [a["tipo"] for a in detalhe["aprovacoes"]]
    assert tipos.count("GESTOR_ORIGEM") == 1
    assert tipos.count("GERENCIA") == 1

    from app.models import Movimentacao

    mov = db_session.get(Movimentacao, mov_id)
    db_session.refresh(mov)
    eventos = client.get(f"/movimentacoes/{mov_id}", headers=_headers(admin_token)).json()["historicoProcessamento"]
    assert any("satisfeita automaticamente" in e["mensagem"] for e in eventos)

    # só falta GESTOR_RH_ADICIONAL (perfil) — nunca auto-satisfeito por
    # coincidência de ator.
    assert _decidir(client, admin_token, mov_id, "GESTOR_RH_ADICIONAL").status_code == 200
    detalhe = client.get(f"/movimentacoes/{mov_id}", headers=_headers(admin_token)).json()
    assert detalhe["status"] in ("PENDENTE", "APROVADA")


def test_rh_e_gestor_rh_adicional_sao_etapas_por_perfil_nunca_deduplicadas(client, db_session):
    """RC-42 — etapas por perfil (RH/GESTOR_RH/GESTOR_RH_ADICIONAL) exigem
    decisão explícita sempre, mesmo quando o mesmo ator (ex.: ADMIN) decide
    as duas — não são deduplicadas só por coincidência de ator."""
    diretor, gerente, coordenador = _cadeia_com_lideranca(db_session)
    origem, destino = _cargo_origem_destino(db_session, AprovacaoAdicional.GERENCIA)
    colaborador = ColaboradorBuilder(cargo_id=origem.id, gestor_id=coordenador.id).build(db_session)
    db_session.commit()

    _admin, admin_token = _token(db_session, PerfilUsuario.ADMIN)
    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "PROMOCAO", "colaboradorId": colaborador.id, "cargoDestinoId": destino.id},
        headers=_headers(admin_token),
    )
    mov_id = resposta.json()["id"]

    assert _decidir(client, admin_token, mov_id, "GESTOR_ORIGEM").status_code == 200
    assert _decidir(client, admin_token, mov_id, "RH").status_code == 200

    detalhe = client.get(f"/movimentacoes/{mov_id}", headers=_headers(admin_token)).json()
    aprovacao_rh = next(a for a in detalhe["aprovacoes"] if a["tipo"] == "RH")
    assert aprovacao_rh["estado"] == "APROVADA"
    aprovacao_gestor_rh_adicional = next(
        (a for a in detalhe["aprovacoes"] if a["tipo"] == "GESTOR_RH_ADICIONAL"), None
    )
    # GERENCIA ainda pendente (ordem 3) — GESTOR_RH_ADICIONAL (ordem 4) nem
    # deveria estar decidível ainda, e certamente não foi auto-satisfeito
    # só porque ADMIN decidiu RH.
    assert aprovacao_gestor_rh_adicional is None or aprovacao_gestor_rh_adicional["estado"] == "PENDENTE"
