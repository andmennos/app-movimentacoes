import itertools

_contador = itertools.count(1)


def proximo() -> int:
    return next(_contador)
