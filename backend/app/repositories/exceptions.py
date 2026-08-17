class OrdenacaoInvalida(Exception):
    """Levantada quando `ordenarPor` não pertence à whitelist de campos ordenáveis."""

    def __init__(self, campo: str):
        self.campo = campo
        super().__init__(f"Campo de ordenação inválido: {campo}")
