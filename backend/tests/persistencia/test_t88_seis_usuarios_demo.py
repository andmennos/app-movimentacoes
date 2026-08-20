"""T-88 — seis usuários de demonstração no seed (spec.md RC-52). E2E-16."""

from app.models import AprovacaoAdicional, Cargo, PerfilUsuario, Usuario
from app.security.passwords import verify_password
from app.seed.seed import seed


def test_e2e16_seis_logins_de_demonstracao_autenticam_com_seus_perfis(db_session):
    seed(db_session)

    esperados = {
        "admin": (PerfilUsuario.ADMIN, "admin"),
        "analistaRh": (PerfilUsuario.RH_ANALISTA, "analistaRh"),
        "gestorRh": (PerfilUsuario.RH_GESTOR, "gestorRh"),
        "coordenador": (PerfilUsuario.LIDERANCA, "coordenador"),
        "gerente": (PerfilUsuario.LIDERANCA, "gerente"),
        "diretor": (PerfilUsuario.LIDERANCA, "diretor"),
    }

    for username, (perfil_esperado, senha) in esperados.items():
        usuario = db_session.query(Usuario).filter_by(username=username).one()
        assert usuario.perfil == perfil_esperado
        assert usuario.ativo is True
        assert usuario.password_hash != senha, f"{username}: senha não pode estar em texto puro"
        assert verify_password(senha, usuario.password_hash)
        assert usuario.colaborador_id is not None, f"{username}: precisa de colaborador vinculado"


def test_gerente_vinculado_a_cargo_papel_lideranca_gerencia(db_session):
    seed(db_session)
    usuario = db_session.query(Usuario).filter_by(username="gerente").one()
    cargo = db_session.get(Cargo, usuario.colaborador.cargo_id)
    assert cargo.papel_lideranca == AprovacaoAdicional.GERENCIA


def test_diretor_vinculado_a_cargo_papel_lideranca_diretoria(db_session):
    seed(db_session)
    usuario = db_session.query(Usuario).filter_by(username="diretor").one()
    cargo = db_session.get(Cargo, usuario.colaborador.cargo_id)
    assert cargo.papel_lideranca == AprovacaoAdicional.DIRETORIA


def test_hierarquia_demonstravel_coordenador_esta_na_subarvore_do_diretor(db_session):
    seed(db_session)
    diretor = db_session.query(Usuario).filter_by(username="diretor").one().colaborador
    gerente = db_session.query(Usuario).filter_by(username="gerente").one().colaborador
    coordenador = db_session.query(Usuario).filter_by(username="coordenador").one().colaborador

    assert gerente.gestor_id == diretor.id
    assert coordenador.gestor_id == gerente.id


def test_nao_cria_perfis_novos_por_cargo(db_session):
    """spec.md RC-52 — coordenador/gerente/diretor usam o mesmo perfil
    técnico LIDERANCA; não existe PerfilUsuario.COORDENADOR/GERENTE/DIRETOR."""
    valores = {p.value for p in PerfilUsuario}
    assert valores == {"ADMIN", "RH_ANALISTA", "RH_GESTOR", "LIDERANCA"}


def test_seed_2x_nao_duplica_os_seis_usuarios(db_session):
    seed(db_session)
    seed(db_session)

    for username in ["admin", "analistaRh", "gestorRh", "coordenador", "gerente", "diretor"]:
        assert db_session.query(Usuario).filter_by(username=username).count() == 1


def _login(client, username, password):
    resposta = client.post("/auth/login", json={"username": username, "password": password})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["accessToken"]


def test_t89_bola_coordenador_gerente_diretor_aninhada(client, db_session):
    """T-89/plan.md §24.8 — usando os logins reais do seed: a subárvore
    visível cresce coordenador ⊂ gerente ⊂ diretor, com o mesmo colaborador
    coordenador presente em todas."""
    seed(db_session)
    db_session.commit()

    coordenador_id = db_session.query(Usuario).filter_by(username="coordenador").one().colaborador_id
    diretor_id = db_session.query(Usuario).filter_by(username="diretor").one().colaborador_id

    token_coordenador = _login(client, "coordenador", "coordenador")
    token_gerente = _login(client, "gerente", "gerente")
    token_diretor = _login(client, "diretor", "diretor")

    ids_coordenador = {c["id"] for c in client.get("/colaboradores", headers={"Authorization": f"Bearer {token_coordenador}"}).json()}
    ids_gerente = {c["id"] for c in client.get("/colaboradores", headers={"Authorization": f"Bearer {token_gerente}"}).json()}
    ids_diretor = {c["id"] for c in client.get("/colaboradores", headers={"Authorization": f"Bearer {token_diretor}"}).json()}

    assert ids_coordenador <= ids_gerente <= ids_diretor
    assert coordenador_id in ids_coordenador
    assert diretor_id not in ids_coordenador
    assert diretor_id in ids_diretor
