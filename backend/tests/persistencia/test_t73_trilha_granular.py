"""T-73 — trilha granular de promoção e semântica `nivel` x `ordem_progressao`
(spec.md RC-32/RC-33, plan.md §23.1).

Cobre duas provas que os testes unitários de P03 (tests/validation/test_promocao.py)
não fazem sozinhos: (1) que a MASSA ATIVA do seed real não oferece mais o
atalho genérico Júnior->Pleno como promoção válida quando processada pelo
motor de verdade (via API + Worker); (2) que `nivel` reinicia por
senioridade enquanto `ordem_progressao` permanece sequencial na família,
tanto na trilha dedicada (`_criar_trilha_cargos`) quanto na família "GERAL"
usada pelo restante do seed.
"""

from app.models import Cargo, Colaborador, Movimentacao, PerfilUsuario, StatusMovimentacao, ValidacaoAuditoria
from app.processing import worker
from app.security.jwt import create_access_token
from app.seed.seed import seed


def _token(db_session, perfil, colaborador_id=None):
    from tests.builders import UsuarioBuilder

    usuario = UsuarioBuilder(perfil=perfil, colaborador_id=colaborador_id).build(db_session)
    db_session.commit()
    return create_access_token(usuario.id, usuario.perfil.value)[0]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _cargo_por_codigo(db_session, codigo: str) -> Cargo:
    return db_session.query(Cargo).filter_by(codigo=codigo).one()


def _codigos_reprovacao(db_session, mov: Movimentacao) -> set[str]:
    auditoria = (
        db_session.query(ValidacaoAuditoria)
        .filter_by(movimentacao_id=mov.id)
        .order_by(ValidacaoAuditoria.id.desc())
        .first()
    )
    if auditoria is None:
        return set()
    return {i.codigo_regra for i in auditoria.inconsistencias}


def test_atalho_generico_junior_para_pleno_nao_e_mais_aprovavel(client, db_session):
    """plan.md §23.1 — prova explícita, via API real + Worker real, que o
    antigo atalho `Analista Júnior -> Analista Pleno` (família "GERAL", um
    único passo) deixou de ser uma promoção válida: ordem_progressao agora
    salta de 1 para 4, então P03 reprova."""
    seed(db_session)

    cargo_junior = _cargo_por_codigo(db_session, "CRG-JUNIOR")
    cargo_pleno = _cargo_por_codigo(db_session, "CRG-PLENO")
    assert cargo_pleno.ordem_progressao != cargo_junior.ordem_progressao + 1, (
        "pré-condição do teste: o atalho só faz sentido testar se de fato não é mais consecutivo"
    )

    admin_colaborador = db_session.query(Colaborador).filter_by(cargo_id=cargo_junior.id).first()
    if admin_colaborador is None:
        from tests.builders import ColaboradorBuilder

        admin_colaborador = ColaboradorBuilder(cargo_id=cargo_junior.id).build(db_session)
        db_session.commit()

    token = _token(db_session, PerfilUsuario.ADMIN, colaborador_id=admin_colaborador.id)

    resposta = client.post(
        "/movimentacoes",
        json={"tipo": "PROMOCAO", "colaboradorId": admin_colaborador.id, "cargoDestinoId": cargo_pleno.id},
        headers=_headers(token),
    )
    assert resposta.status_code == 201
    movimentacao_id = resposta.json()["id"]

    # ADMIN decide qualquer aprovação, inclusive da própria solicitação
    # (RC-07/RC-12) — usado aqui só para destravar o gate e chegar à engine,
    # não é o objeto do teste.
    while True:
        pendentes = client.get("/aprovacoes/pendentes", headers=_headers(token)).json()
        alvo = next((p for p in pendentes if p["movimentacaoId"] == movimentacao_id), None)
        if alvo is None:
            break
        client.post(
            f"/movimentacoes/{movimentacao_id}/aprovacoes/{alvo['tipo']}/decidir",
            json={"decisao": "APROVADA"},
            headers=_headers(token),
        )

    mov = db_session.get(Movimentacao, movimentacao_id)
    db_session.refresh(mov)
    assert mov.status == StatusMovimentacao.PENDENTE

    worker.drenar_fila(db_session)
    db_session.refresh(mov)

    assert mov.status == StatusMovimentacao.REPROVADA
    assert "P03" in _codigos_reprovacao(db_session, mov)


def test_nivel_reinicia_por_senioridade_ordem_progressao_e_sequencial(db_session):
    """RC-32/V-47/PRO-13 — tanto a trilha dedicada (OPERACOES) quanto a
    família "GERAL" usada pelo resto do seed devem ter `nivel` reiniciando
    a cada senioridade, com `ordem_progressao` estritamente sequencial."""
    seed(db_session)

    trilha_ops = (
        db_session.query(Cargo)
        .filter(Cargo.familia_cargo == "OPERACOES")
        .order_by(Cargo.ordem_progressao)
        .all()
    )
    assert [c.ordem_progressao for c in trilha_ops] == [1, 2, 3, 4, 5, 6, 7]
    assert [c.nivel for c in trilha_ops] == [1, 2, 3, 1, 2, 3, 1]

    junior1 = _cargo_por_codigo(db_session, "CRG-JUNIOR")
    junior2 = _cargo_por_codigo(db_session, "CRG-JUNIOR2")
    junior3 = _cargo_por_codigo(db_session, "CRG-JUNIOR3")
    pleno1 = _cargo_por_codigo(db_session, "CRG-PLENO")
    pleno2 = _cargo_por_codigo(db_session, "CRG-PLENO2")
    pleno3 = _cargo_por_codigo(db_session, "CRG-PLENO3")

    assert [c.ordem_progressao for c in (junior1, junior2, junior3, pleno1, pleno2, pleno3)] == [1, 2, 3, 4, 5, 6]
    assert [c.nivel for c in (junior1, junior2, junior3, pleno1, pleno2, pleno3)] == [1, 2, 3, 1, 2, 3]


def test_papel_lideranca_gerente_e_diretor_coerente_com_aprovacao_adicional(db_session):
    """RC-38 — `papel_lideranca` identifica a função hierárquica usada para
    resolver a etapa GERENCIA/DIRETORIA (T-75); aqui só confirma que os
    cargos de gestão do seed carregam o discriminador certo, sem depender
    de parse de `Cargo.nome`."""
    from app.models.enums import AprovacaoAdicional

    seed(db_session)

    gerente = _cargo_por_codigo(db_session, "CRG-GERENTE")
    diretor = _cargo_por_codigo(db_session, "CRG-DIRETOR")

    assert gerente.papel_lideranca == AprovacaoAdicional.GERENCIA
    assert diretor.papel_lideranca == AprovacaoAdicional.DIRETORIA
