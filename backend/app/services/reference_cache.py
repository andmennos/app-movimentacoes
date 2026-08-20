"""Cache TTL local para catálogos de referência — spec.md §13/RC-29.

Só para `cargos`/`departamentos`/`centros de custo` (dados de referência
estáveis). Nunca para senha, JWT, aprovação, status/timeline de
movimentação ou qualquer decisão de autorização/BOLA (RC-29) — nada disso
passa por este módulo.

Local ao processo, não distribuído (RC-30/plan §16.1) — reinício do
processo ou escrita nesses catálogos (fora do MVP hoje) exigiria
`invalidar()`, que já existe para isso.
"""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")

_cache: dict[str, tuple[float, object]] = {}


def obter_ou_calcular(chave: str, ttl_segundos: float, calcular: Callable[[], T]) -> T:
    agora = time.monotonic()
    entrada = _cache.get(chave)
    if entrada is not None and (agora - entrada[0]) < ttl_segundos:
        return entrada[1]  # type: ignore[return-value]
    valor = calcular()
    _cache[chave] = (agora, valor)
    return valor


def invalidar(chave: str | None = None) -> None:
    if chave is None:
        _cache.clear()
    else:
        _cache.pop(chave, None)
