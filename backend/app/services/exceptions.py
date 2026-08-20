class MovimentacaoNaoEncontrada(Exception):
    def __init__(self, movimentacao_id: int):
        self.movimentacao_id = movimentacao_id
        super().__init__(f"Movimentação {movimentacao_id} não encontrada")


class ValidacaoManualNaoPermitida(Exception):
    """spec.md §8.3 — a validação manual não pôde executar: aprovação
    pendente/reprovada (gate reavaliado no clique) ou solicitação já
    terminal. Carrega os impedimentos atuais para a resposta 409."""

    def __init__(self, impedimentos):
        self.impedimentos = impedimentos
        super().__init__("Validação manual não permitida nesta situação.")


class ValidacaoEmAndamento(Exception):
    """spec.md §8.3 — já existe um job `PROCESSANDO` saudável para esta
    movimentação (Worker ou outra chamada manual já está processando)."""

    def __init__(self):
        super().__init__("Já existe uma validação em andamento para esta movimentação.")


class FalhaTecnicaValidacao(Exception):
    """Falha técnica durante o processamento manual — o orquestrador já
    tratou o retry/erro do job internamente; isto só sinaliza 500 ao
    chamador HTTP."""

    def __init__(self):
        super().__init__("Falha técnica ao processar a validação.")


class CredenciaisInvalidas(Exception):
    """spec.md §12.1 — resposta genérica: não revela se o username existe."""

    def __init__(self):
        super().__init__("Usuário ou senha inválidos.")


class LoginBloqueado(Exception):
    """spec.md §12.3/RC-25 — IP em janela de bloqueio de força bruta."""

    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        super().__init__("Muitas tentativas de login. Tente novamente mais tarde.")


class TokenInvalidoOuExpirado(Exception):
    def __init__(self):
        super().__init__("Token inválido ou expirado.")


class AcessoNegado(Exception):
    """spec.md §2.3 — falha de autorização funcional (escopo do perfil)."""

    def __init__(self, mensagem: str = "Acesso negado."):
        super().__init__(mensagem)


class ColaboradorNaoEncontrado(Exception):
    """spec.md §3.2/RC-16 — usada tanto para colaborador inexistente quanto
    para colaborador fora do escopo BOLA do solicitante: a resposta é a
    mesma (404), sem revelar qual dos dois casos ocorreu."""

    def __init__(self, colaborador_id: int):
        self.colaborador_id = colaborador_id
        super().__init__(f"Colaborador {colaborador_id} não encontrado")


class AprovacaoNaoEncontrada(Exception):
    """spec.md §6.2 — a movimentação existe (e está no escopo) mas não exige
    esta etapa de aprovação (ou o tipo não é reconhecido)."""

    def __init__(self, movimentacao_id: int, tipo: str):
        self.movimentacao_id = movimentacao_id
        self.tipo = tipo
        super().__init__(f"Aprovação {tipo} não é exigida para a movimentação {movimentacao_id}")


class AprovacaoJaDecidida(Exception):
    """spec.md §6.2 item 6 — dupla decisão é rejeitada."""

    def __init__(self):
        super().__init__("Esta aprovação já foi decidida.")


class AprovacaoForaDeOrdem(Exception):
    """spec.md §5.4 — uma etapa posterior de PROMOCAO não pode ser decidida
    antes da etapa anterior obrigatória estar APROVADA."""

    def __init__(self):
        super().__init__("Etapa anterior obrigatória ainda não foi aprovada.")


class MovimentacaoNaoAguardandoAprovacao(Exception):
    """spec.md RC-47/T-85 — `BLOQUEADA` é terminal: assim que qualquer etapa
    exigida é reprovada, o workflow de aprovação encerra e nenhuma outra
    etapa (mesmo `PENDENTE`, nunca alcançada) é mais decidível — mesma
    proteção para os demais estados fora de `AGUARDANDO_APROVACAO`
    (`PENDENTE`/`APROVADA`/`REPROVADA` já passaram da fase de aprovação)."""

    def __init__(self):
        super().__init__("Esta movimentação não está mais aguardando aprovação.")


class ApprovadorHierarquicoNaoResolvido(Exception):
    """spec.md RC-38/T-75 — a política exige uma etapa GERENCIA/DIRETORIA
    (pessoa concreta, via `Cargo.papel_lideranca`) mas ninguém na cadeia de
    `gestor_id` do colaborador ocupa esse papel. A criação/ativação do
    workflow falha explicitamente, sem persistência parcial."""

    def __init__(self, papel: str):
        self.papel = papel
        super().__init__(f"Nenhum aprovador de {papel} foi encontrado na cadeia hierárquica.")


class ReferenciaNaoEncontrada(Exception):
    """spec.md §4.2 — destino informado (departamento/cargo/centro de custo)
    não existe. Diferente de BOLA: catálogos de referência não têm escopo
    organizacional (spec §3.3), então não há ambiguidade a esconder aqui."""

    def __init__(self, recurso: str, recurso_id: int):
        self.recurso = recurso
        self.recurso_id = recurso_id
        super().__init__(f"{recurso} {recurso_id} não encontrado(a)")
