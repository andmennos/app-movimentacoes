from app.validation.engine import executar
from tests.validation.factories import (
    contexto_centro_custo,
    contexto_estrutura,
    contexto_promocao,
    contexto_transferencia,
    contexto_troca_gestor,
)


def test_contextos_base_validam_sem_inconsistencias():
    for construir in (
        contexto_transferencia,
        contexto_promocao,
        contexto_troca_gestor,
        contexto_centro_custo,
        contexto_estrutura,
    ):
        ctx = construir()
        assert executar(ctx) == []
