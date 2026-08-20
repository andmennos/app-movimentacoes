"""Rate limiting geral local — spec.md §12.4/§14.2. Segunda camada de
defesa, em memória, por processo único (RC-27): não é proteção contra DDoS
volumétrico nem é distribuído — reinício do processo limpa o estado (ao
contrário do lockout de login, persistido em `SecurityLockout`).

Relógio monotônico (plan §14.2) — imune a ajustes de hora do sistema.
Janela deslizante simples: uma lista de timestamps por chave, podada a cada
checagem. Custo limitado ao próprio limite (nunca mais que `limite` entradas
por chave).
"""

from __future__ import annotations

import time
from collections import defaultdict

_JANELA_SEGUNDOS = 60.0
_janelas: dict[str, list[float]] = defaultdict(list)


def verificar_e_registrar(chave: str, limite: int) -> tuple[bool, int]:
    """Retorna `(permitido, retry_after_segundos)`. Registra a tentativa
    somente quando permitida (tentativas bloqueadas não contam)."""
    agora = time.monotonic()
    marcas = _janelas[chave]
    corte = agora - _JANELA_SEGUNDOS
    while marcas and marcas[0] < corte:
        marcas.pop(0)

    if len(marcas) >= limite:
        retry_after = max(1, int(_JANELA_SEGUNDOS - (agora - marcas[0])) + 1)
        return False, retry_after

    marcas.append(agora)
    return True, 0


def resetar() -> None:
    """Uso exclusivo de testes — evita vazamento de estado entre casos."""
    _janelas.clear()
