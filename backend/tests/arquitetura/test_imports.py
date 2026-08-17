"""INV-01 / V-04: `validation/` não importa ORM nem framework web.

Verificação estática (AST) dos imports de cada módulo de `app/validation/` —
não basta rodar sem erro: um import não utilizado ainda seria uma violação.
"""

import ast
from pathlib import Path

PROIBIDOS = {"sqlalchemy", "fastapi", "pydantic", "pydantic_settings", "app.models", "app.database"}

DIRETORIO_VALIDATION = Path(__file__).resolve().parent.parent.parent / "app" / "validation"


def _modulos_importados(caminho: Path) -> set[str]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    modulos = set()
    for node in ast.walk(arvore):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modulos.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modulos.add(node.module)
    return modulos


def test_validation_nao_importa_orm_nem_framework_web():
    arquivos = sorted(DIRETORIO_VALIDATION.glob("*.py"))
    assert len(arquivos) > 0

    violacoes = {}
    for arquivo in arquivos:
        modulos = _modulos_importados(arquivo)
        proibidos_usados = {
            m for m in modulos if any(m == p or m.startswith(p + ".") for p in PROIBIDOS)
        }
        if proibidos_usados:
            violacoes[arquivo.name] = proibidos_usados

    assert violacoes == {}, f"Imports proibidos encontrados em validation/: {violacoes}"


def test_validation_e_o_unico_diretorio_isento_de_orm_por_contrato():
    # Confirma que o diretório existe e contém os módulos esperados do motor.
    nomes = {p.stem for p in DIRETORIO_VALIDATION.glob("*.py")}
    esperados = {
        "types",
        "common",
        "transferencia",
        "promocao",
        "troca_gestor",
        "centro_custo",
        "estrutura",
        "aprovacoes",
        "engine",
    }
    assert esperados <= nomes
