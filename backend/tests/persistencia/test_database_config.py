import tempfile
from pathlib import Path

from app.database import criar_engine


def test_foreign_keys_ativo_em_conexao_nova(engine):
    with engine.connect() as conn:
        resultado = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
    assert resultado == 1


def test_journal_mode_wal_em_arquivo():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "teste.db"
        eng = criar_engine(f"sqlite:///{caminho}")
        with eng.connect() as conn:
            modo = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        assert modo.lower() == "wal"
        eng.dispose()
