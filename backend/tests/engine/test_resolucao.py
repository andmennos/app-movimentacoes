from app.validation.engine import resolver_resultado
from app.validation.types import Inconsistencia, ResultadoValidacao


def test_sem_inconsistencias_retorna_aprovada():
    assert resolver_resultado([]) == ResultadoValidacao.APROVADA


def test_com_inconsistencias_retorna_reprovada():
    inconsistencias = [Inconsistencia("T05", "Departamento de origem e destino são iguais")]
    assert resolver_resultado(inconsistencias) == ResultadoValidacao.REPROVADA


def test_multiplas_inconsistencias_ainda_assim_retorna_reprovada():
    inconsistencias = [
        Inconsistencia("G02", "Colaborador não está ativo"),
        Inconsistencia("T04", "Departamento de destino não está ativo"),
    ]
    assert resolver_resultado(inconsistencias) == ResultadoValidacao.REPROVADA
