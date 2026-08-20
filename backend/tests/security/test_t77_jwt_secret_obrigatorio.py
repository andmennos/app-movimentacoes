"""T-77/RC-39/SEC-01 — `JWT_SECRET` não tem fallback funcional hardcoded:
sem ele (nem no ambiente, nem em `.env`), a construção de `Settings()` falha
explicitamente — o processo não sobe silenciosamente com um segredo
previsível. Roda em subprocesso porque `app.config.settings` já é um
singleton importado por toda a suíte com o segredo de teste do
`conftest.py`; testar o caminho de falha exige um processo Python novo,
sem essa variável no ambiente."""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def test_settings_falha_sem_jwt_secret_configurado():
    env = os.environ.copy()
    env.pop("JWT_SECRET", None)

    # `_env_file=None` desliga a leitura de backend/.env para esta
    # instância específica (pydantic-settings) — a máquina que roda o teste
    # pode ter um backend/.env real de desenvolvimento; sem esse override o
    # teste dependeria de removê-lo do disco, o que seria destrutivo.
    codigo = "from app.config import Settings; Settings(_env_file=None)"
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert resultado.returncode != 0, "Settings() deveria falhar sem JWT_SECRET configurado"
    saida = (resultado.stderr + resultado.stdout).lower()
    assert "jwt_secret" in saida
    assert "validationerror" in saida or "field required" in saida


def test_settings_funciona_com_jwt_secret_no_ambiente():
    env = os.environ.copy()
    env["JWT_SECRET"] = "um-segredo-qualquer-so-para-este-subprocesso-de-teste"

    codigo = "from app.config import Settings; s = Settings(_env_file=None); print('ok:', bool(s.jwt_secret))"
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert resultado.returncode == 0, resultado.stderr
    assert "ok: True" in resultado.stdout
