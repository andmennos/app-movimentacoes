"""T-68 — medição real de p50/p95 (spec.md §13/plan.md §18). Roda o seed
completo em um SQLite de arquivo temporário e mede `GET /movimentacoes`
(paginado, várias páginas/filtros) e `GET /movimentacoes/{id}` via
`TestClient` — mede a camada de aplicação real (queries + serialização),
que é onde o custo computacional do MVP realmente vive; overhead de rede
localhost é desprezível para a meta de <2s.

Uso: `python -m scripts.benchmark_performance` (a partir de `backend/`).
"""

from __future__ import annotations

import statistics
import tempfile
import time
from pathlib import Path


def _percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, int(round(p * (len(ordenados) - 1))))
    return ordenados[indice]


def main() -> None:
    import os

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "benchmark.db"
        # Precisa ser setado ANTES de qualquer import de app.* — `Settings()`
        # (pydantic-settings) só lê a variável de ambiente na construção,
        # que acontece na primeira vez que `app.config` é importado.
        os.environ["DATABASE_PATH"] = str(db_path)

        from app.config import settings
        from app.database import Base, SessionLocal, engine
        from app.seed.seed import seed

        # O benchmark mede latência de endpoint, não rate limiting (T-67,
        # testado separadamente) — sobe os limites para não interferir.
        settings.rate_limit_read_per_minute = 1_000_000
        settings.rate_limit_write_per_minute = 1_000_000

        Base.metadata.create_all(engine)
        session = SessionLocal()
        try:
            seed(session)
        finally:
            session.close()

        from fastapi.testclient import TestClient

        from app.main import app
        from app.models import PerfilUsuario
        from app.security.jwt import create_access_token

        session = SessionLocal()
        try:
            from app.repositories import usuario_repository

            admin = usuario_repository.buscar_por_username(session, "admin")
            token, _ = create_access_token(admin.id, PerfilUsuario.ADMIN.value)
        finally:
            session.close()

        headers = {"Authorization": f"Bearer {token}"}

        with TestClient(app) as client:
            listagem_tempos: list[float] = []
            for pagina in range(1, 8):
                for status in (None, "APROVADA", "REPROVADA", "AGUARDANDO_APROVACAO", "BLOQUEADA", "PENDENTE"):
                    params = {"page": pagina, "pageSize": 20}
                    if status:
                        params["status"] = status
                    inicio = time.perf_counter()
                    resposta = client.get("/movimentacoes", params=params, headers=headers)
                    listagem_tempos.append(time.perf_counter() - inicio)
                    assert resposta.status_code == 200, resposta.text

            primeira_pagina = client.get("/movimentacoes", params={"pageSize": 100}, headers=headers).json()
            ids = [item["id"] for item in primeira_pagina["items"]]

            detalhe_tempos: list[float] = []
            for movimentacao_id in ids:
                inicio = time.perf_counter()
                resposta = client.get(f"/movimentacoes/{movimentacao_id}", headers=headers)
                detalhe_tempos.append(time.perf_counter() - inicio)
                assert resposta.status_code == 200, resposta.text

        print(f"Total de movimentações no seed: {primeira_pagina['total']}")
        print()
        print(f"GET /movimentacoes ({len(listagem_tempos)} chamadas):")
        print(f"  p50 = {_percentil(listagem_tempos, 0.50) * 1000:.1f} ms")
        print(f"  p95 = {_percentil(listagem_tempos, 0.95) * 1000:.1f} ms")
        print(f"  max = {max(listagem_tempos) * 1000:.1f} ms")
        print()
        print(f"GET /movimentacoes/{{id}} ({len(detalhe_tempos)} chamadas):")
        print(f"  p50 = {_percentil(detalhe_tempos, 0.50) * 1000:.1f} ms")
        print(f"  p95 = {_percentil(detalhe_tempos, 0.95) * 1000:.1f} ms")
        print(f"  max = {max(detalhe_tempos) * 1000:.1f} ms")

        engine.dispose()


if __name__ == "__main__":
    main()
