from app.validation.engine import executar
from app.validation.troca_gestor import (
    tg01_novo_gestor_existe,
    tg02_novo_gestor_ativo,
    tg03_funcao_compativel,
    tg04_nao_e_proprio_gestor,
    tg05_sem_ciclo_hierarquico,
    tg06_aprovacoes_integras,
)
from app.validation.types import NoHierarquia, TipoAprovacao
from tests.validation.factories import aprovacao_ref, cargo_ref, colaborador_ref, contexto_troca_gestor


def test_tg01_dispara_quando_novo_gestor_ausente():
    ctx = contexto_troca_gestor(gestor_destino=None)
    assert [i.codigo for i in tg01_novo_gestor_existe(ctx)] == ["TG01"]


def test_tg01_suprime_quando_novo_gestor_presente():
    assert tg01_novo_gestor_existe(contexto_troca_gestor()) == []


def test_tg02_dispara_quando_novo_gestor_inativo():
    gestor = colaborador_ref(ativo=False, cargo=cargo_ref(permite_gestao=True))
    ctx = contexto_troca_gestor(gestor_destino=gestor)
    assert [i.codigo for i in tg02_novo_gestor_ativo(ctx)] == ["TG02"]


def test_tg02_suprime_quando_novo_gestor_ativo():
    assert tg02_novo_gestor_ativo(contexto_troca_gestor()) == []


def test_tg02_precondicao_nao_avalia_sem_novo_gestor():
    ctx = contexto_troca_gestor(gestor_destino=None)
    assert tg02_novo_gestor_ativo(ctx) == []


def test_tg03_dispara_quando_cargo_sem_funcao_de_gestao():
    gestor = colaborador_ref(cargo=cargo_ref(permite_gestao=False))
    ctx = contexto_troca_gestor(gestor_destino=gestor)
    assert [i.codigo for i in tg03_funcao_compativel(ctx)] == ["TG03"]


def test_tg03_dispara_quando_cargo_ausente():
    gestor = colaborador_ref(cargo=None)
    ctx = contexto_troca_gestor(gestor_destino=gestor)
    assert [i.codigo for i in tg03_funcao_compativel(ctx)] == ["TG03"]


def test_tg03_suprime_quando_cargo_permite_gestao():
    assert tg03_funcao_compativel(contexto_troca_gestor()) == []


def test_tg04_dispara_quando_colaborador_e_seu_proprio_gestor():
    colaborador = colaborador_ref()
    ctx = contexto_troca_gestor(colaborador=colaborador, gestor_destino=colaborador)
    assert [i.codigo for i in tg04_nao_e_proprio_gestor(ctx)] == ["TG04"]


def test_tg04_suprime_quando_diferentes():
    assert tg04_nao_e_proprio_gestor(contexto_troca_gestor()) == []


def test_tg05_dispara_em_ciclo_direto_cn_n12():
    colaborador = colaborador_ref()
    gestor_destino = colaborador_ref(cargo=cargo_ref(permite_gestao=True), gestor_id=colaborador.id)
    cadeia = {gestor_destino.id: NoHierarquia(gestor_destino.id, colaborador.id)}
    ctx = contexto_troca_gestor(colaborador=colaborador, gestor_destino=gestor_destino, cadeia=cadeia)
    assert [i.codigo for i in tg05_sem_ciclo_hierarquico(ctx)] == ["TG05"]


def test_tg05_dispara_em_ciclo_indireto_3_niveis_cn_n13():
    a = colaborador_ref()
    b = colaborador_ref(gestor_id=a.id)
    c = colaborador_ref(cargo=cargo_ref(permite_gestao=True), gestor_id=b.id)
    # A quer trocar para ser gerido por C; mas C -> B -> A fecha o ciclo.
    cadeia = {
        c.id: NoHierarquia(c.id, b.id),
        b.id: NoHierarquia(b.id, a.id),
    }
    ctx = contexto_troca_gestor(colaborador=a, gestor_destino=c, cadeia=cadeia)
    assert [i.codigo for i in tg05_sem_ciclo_hierarquico(ctx)] == ["TG05"]


def test_tg05_suprime_gestor_fora_da_cadeia_cn_p03():
    assert tg05_sem_ciclo_hierarquico(contexto_troca_gestor()) == []


def test_tg05_nao_entra_em_laco_infinito_com_ciclo_preexistente_cn_n38():
    x = colaborador_ref(cargo=cargo_ref(permite_gestao=True))
    y = colaborador_ref()
    # ciclo pré-existente nos dados: x -> y -> x, sem relação com o colaborador da movimentação
    cadeia = {
        x.id: NoHierarquia(x.id, y.id),
        y.id: NoHierarquia(y.id, x.id),
    }
    colaborador_alheio = colaborador_ref()
    ctx = contexto_troca_gestor(colaborador=colaborador_alheio, gestor_destino=x, cadeia=cadeia)

    resultado = tg05_sem_ciclo_hierarquico(ctx)  # não deve lançar exceção nem travar

    assert resultado == []


def test_tg06_dispara_quando_aprovacao_ausente():
    ctx = contexto_troca_gestor(aprovacoes=[aprovacao_ref(TipoAprovacao.GESTOR_ORIGEM)])
    assert [i.codigo for i in tg06_aprovacoes_integras(ctx)] == ["TG06"]


def test_tg06_suprime_quando_integras():
    assert tg06_aprovacoes_integras(contexto_troca_gestor()) == []


def test_cnm03_multiplas_inconsistencias_troca_gestor():
    gestor = colaborador_ref(ativo=False, cargo=cargo_ref(permite_gestao=False))
    ctx = contexto_troca_gestor(
        gestor_destino=gestor,
        cadeia={gestor.id: NoHierarquia(gestor.id, None)},
        aprovacoes=[],
    )
    codigos = [i.codigo for i in executar(ctx)]
    assert "TG02" in codigos
    assert "TG03" in codigos
    assert "TG06" in codigos
