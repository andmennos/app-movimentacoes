class MovimentacaoNaoEncontrada(Exception):
    def __init__(self, movimentacao_id: int):
        self.movimentacao_id = movimentacao_id
        super().__init__(f"Movimentação {movimentacao_id} não encontrada")
