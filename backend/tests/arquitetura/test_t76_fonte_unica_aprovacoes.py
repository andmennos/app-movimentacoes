"""T-76/RC-41 — a política de aprovações (`app.validation.aprovacoes.
exigencias_para`) é fonte única também no seed: nenhum módulo mantém um
mapa `TipoMovimentacao -> [TipoAprovacao, ...]` paralelo. Verificação
estática (AST), não só comportamental — um mapa paralelo que hoje
coincidiria por acaso com a política real ainda seria uma violação (ele
divergiria silenciosamente na próxima mudança de regra)."""

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent / "app"
SEED_MODULE = APP_DIR / "seed" / "seed.py"


def _nomes_de_atribuicoes_top_level(caminho: Path) -> set[str]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    nomes = set()
    for node in arvore.body:  # só top-level — não entra em função/classe
        if isinstance(node, ast.Assign):
            for alvo in node.targets:
                if isinstance(alvo, ast.Name):
                    nomes.add(alvo.id)
    return nomes


def test_seed_nao_define_mapa_paralelo_de_exigencias_de_aprovacao():
    nomes = _nomes_de_atribuicoes_top_level(SEED_MODULE)
    suspeitos = {n for n in nomes if "EXIGENCIA" in n.upper()}
    assert suspeitos == set(), (
        f"app/seed/seed.py define {suspeitos} — mapa paralelo de aprovações proibido (RC-41); "
        "use app.validation.aprovacoes.exigencias_para via montar_contexto"
    )


def test_seed_usa_exigencias_para_como_fonte_unica():
    fonte = SEED_MODULE.read_text(encoding="utf-8")
    assert "from app.validation.aprovacoes import exigencias_para" in fonte
    assert "exigencias_para(ctx)" in fonte
