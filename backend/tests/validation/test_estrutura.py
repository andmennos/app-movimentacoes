from app.validation.engine import executar
from app.validation.estrutura import (
    ae01_estrutura_origem_existe,
    ae02_estrutura_origem_ativa,
    ae03_estrutura_destino_existe,
    ae04_estrutura_destino_ativa,
    ae05_origem_diferente_destino,
    ae06_aprovacoes_integras,
)
from app.validation.types import TipoAprovacao
from tests.validation.factories import aprovacao_ref, contexto_estrutura, estrutura_ref


def test_ae01_dispara_quando_origem_ausente():
    ctx = contexto_estrutura(estrutura_origem=None)
    assert [i.codigo for i in ae01_estrutura_origem_existe(ctx)] == ["AE01"]


def test_ae01_suprime_quando_presente():
    assert ae01_estrutura_origem_existe(contexto_estrutura()) == []


def test_ae02_dispara_quando_origem_inativa():
    ctx = contexto_estrutura(estrutura_origem=estrutura_ref(ativo=False))
    assert [i.codigo for i in ae02_estrutura_origem_ativa(ctx)] == ["AE02"]


def test_ae02_suprime_quando_ativa():
    assert ae02_estrutura_origem_ativa(contexto_estrutura()) == []


def test_ae02_precondicao_nao_avalia_sem_origem():
    ctx = contexto_estrutura(estrutura_origem=None)
    assert ae02_estrutura_origem_ativa(ctx) == []


def test_ae03_dispara_quando_destino_ausente():
    ctx = contexto_estrutura(estrutura_destino=None)
    assert [i.codigo for i in ae03_estrutura_destino_existe(ctx)] == ["AE03"]


def test_ae03_suprime_quando_presente():
    assert ae03_estrutura_destino_existe(contexto_estrutura()) == []


def test_ae04_dispara_quando_destino_inativa_cn_n16():
    ctx = contexto_estrutura(estrutura_destino=estrutura_ref(ativo=False))
    assert [i.codigo for i in ae04_estrutura_destino_ativa(ctx)] == ["AE04"]


def test_ae04_suprime_quando_ativa():
    assert ae04_estrutura_destino_ativa(contexto_estrutura()) == []


def test_ae05_dispara_quando_origem_igual_destino_cn_n17_ca025():
    est = estrutura_ref()
    ctx = contexto_estrutura(estrutura_origem=est, estrutura_destino=est)
    inconsistencias = ae05_origem_diferente_destino(ctx)
    assert [i.codigo for i in inconsistencias] == ["AE05"]
    assert "ciclo" not in inconsistencias[0].mensagem.lower()


def test_ae05_suprime_quando_diferentes():
    assert ae05_origem_diferente_destino(contexto_estrutura()) == []


def test_ae06_dispara_quando_aprovacao_ausente():
    ctx = contexto_estrutura(aprovacoes=[])
    assert [i.codigo for i in ae06_aprovacoes_integras(ctx)] == ["AE06"]


def test_ae06_suprime_quando_integra():
    assert ae06_aprovacoes_integras(contexto_estrutura()) == []


def test_multiplas_inconsistencias_estrutura():
    ctx = contexto_estrutura(estrutura_destino=estrutura_ref(ativo=False), aprovacoes=[])
    codigos = [i.codigo for i in executar(ctx)]
    assert "AE04" in codigos
    assert "AE06" in codigos


def test_ca028_conjunto_de_codigos_emitiveis_alteracao_estrutura():
    """CA-028 / CN-A04: o conjunto de códigos emitíveis por ALTERACAO_ESTRUTURA
    é exatamente {G01, G02, G03, G04, AE01..AE06} — 10 códigos, nenhum de ciclo.

    G01 e G02/G04 nunca disparam juntos (G02/G04 têm G01 como pré-condição),
    então a cobertura exaustiva exige dois cenários complementares.
    """
    from app.validation.types import MovimentacaoRef
    from tests.validation.factories import colaborador_ref, novo_id

    esperado = {"G01", "G02", "G03", "G04", "AE01", "AE02", "AE03", "AE04", "AE05", "AE06"}

    cenario_sem_colaborador = contexto_estrutura(
        colaborador=None,
        estrutura_origem=None,
        estrutura_destino=None,
        aprovacoes=[],
    )

    est = estrutura_ref(ativo=False)
    cenario_com_colaborador_inativo = contexto_estrutura(
        colaborador=colaborador_ref(ativo=False),
        conflito_mesmo_tipo_em_aberto=True,
        estrutura_origem=est,
        estrutura_destino=est,
        aprovacoes=[],
    )

    cenario_tipo_invalido = contexto_estrutura()
    cenario_tipo_invalido.movimentacao = MovimentacaoRef(
        id=novo_id(), tipo="LIXO", colaborador_id=cenario_tipo_invalido.colaborador.id
    )

    codigos_vistos: set[str] = set()
    for cenario in (cenario_sem_colaborador, cenario_com_colaborador_inativo, cenario_tipo_invalido):
        codigos_vistos.update(i.codigo for i in executar(cenario))

    assert codigos_vistos == esperado
