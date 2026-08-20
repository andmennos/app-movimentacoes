import enum


class TipoMovimentacao(str, enum.Enum):
    TRANSFERENCIA = "TRANSFERENCIA"
    PROMOCAO = "PROMOCAO"
    TROCA_GESTOR = "TROCA_GESTOR"
    MUDANCA_CENTRO_CUSTO = "MUDANCA_CENTRO_CUSTO"
    ALTERACAO_ESTRUTURA = "ALTERACAO_ESTRUTURA"


class StatusMovimentacao(str, enum.Enum):
    """spec.md RC-09/§1.1 — cinco estados de negócio.

    `AGUARDANDO_APROVACAO`/`BLOQUEADA` nunca passam pela engine.
    `PENDENTE` significa aprovações concluídas, processamento final ainda não
    concluído. `APROVADA`/`REPROVADA` só existem depois que a engine executou.
    """

    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"
    PENDENTE = "PENDENTE"
    APROVADA = "APROVADA"
    REPROVADA = "REPROVADA"
    BLOQUEADA = "BLOQUEADA"


ESTADOS_ABERTOS = (StatusMovimentacao.AGUARDANDO_APROVACAO, StatusMovimentacao.PENDENTE)
"""spec.md §7.1/plan.md §8 — estados considerados "em aberto" por G04. Estados
terminais (APROVADA/REPROVADA/BLOQUEADA) não contam como conflito."""


class ResultadoValidacao(str, enum.Enum):
    """spec.md §7.5 — resultado da engine. `AGUARDANDO_APROVACAO` deixou de
    ser resultado de validação: é status de fluxo anterior à engine."""

    APROVADA = "APROVADA"
    REPROVADA = "REPROVADA"


class OrigemExecucao(str, enum.Enum):
    AUTOMATICO = "AUTOMATICO"
    MANUAL = "MANUAL"


class OrigemEvento(str, enum.Enum):
    SISTEMA = "SISTEMA"
    AUTOMATICO = "AUTOMATICO"
    MANUAL = "MANUAL"


class TipoEventoProcessamento(str, enum.Enum):
    """spec.md §2.5 — catálogo fechado de eventos de `HistoricoProcessamento`."""

    SOLICITACAO_RECEBIDA = "SOLICITACAO_RECEBIDA"
    APROVACAO_CONCLUIDA = "APROVACAO_CONCLUIDA"
    APROVACAO_REPROVADA = "APROVACAO_REPROVADA"
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"
    PROCESSAMENTO_PENDENTE = "PROCESSAMENTO_PENDENTE"
    PROCESSAMENTO_INICIADO = "PROCESSAMENTO_INICIADO"
    VALIDACAO_REPROVADA = "VALIDACAO_REPROVADA"
    MOVIMENTACAO_EFETIVADA = "MOVIMENTACAO_EFETIVADA"
    ERRO_TECNICO = "ERRO_TECNICO"
    RETRY_AGENDADO = "RETRY_AGENDADO"
    JOB_RECUPERADO = "JOB_RECUPERADO"
    VALIDACAO_MANUAL_SOLICITADA = "VALIDACAO_MANUAL_SOLICITADA"
    VALIDACAO_MANUAL_NAO_PERMITIDA = "VALIDACAO_MANUAL_NAO_PERMITIDA"


class TipoAprovacao(str, enum.Enum):
    GESTOR_ORIGEM = "GESTOR_ORIGEM"
    GESTOR_DESTINO = "GESTOR_DESTINO"
    GESTOR_SUPERIOR = "GESTOR_SUPERIOR"
    RH = "RH"
    GESTOR_RH = "GESTOR_RH"
    GERENCIA = "GERENCIA"
    DIRETORIA = "DIRETORIA"
    GESTOR_RH_ADICIONAL = "GESTOR_RH_ADICIONAL"
    """spec.md RC-37/T-75 — anuência final de RH_GESTOR para promoções com
    `aprovacao_adicional`, tecnicamente distinta de `GESTOR_RH` (que pode já
    ter sido usado numa substituição anterior da mesma movimentação) para
    preservar `UNIQUE(movimentacao_id, tipo)`."""


class EstadoAprovacao(str, enum.Enum):
    PENDENTE = "PENDENTE"
    APROVADA = "APROVADA"
    REPROVADA = "REPROVADA"


class AprovacaoAdicional(str, enum.Enum):
    GERENCIA = "GERENCIA"
    DIRETORIA = "DIRETORIA"


class Severidade(str, enum.Enum):
    ERRO = "ERRO"


class StatusJob(str, enum.Enum):
    PENDENTE = "PENDENTE"
    PROCESSANDO = "PROCESSANDO"
    CONCLUIDO = "CONCLUIDO"
    ERRO = "ERRO"


class PerfilUsuario(str, enum.Enum):
    """spec.md §2.1/RC-13 — perfis de autenticação do MVP. Somente `ADMIN` e
    `RH_ANALISTA` têm login autenticável nesta entrega (RC-13); `RH_GESTOR` e
    `LIDERANCA` estão preparados no enum mas sem usuário de demonstração."""

    ADMIN = "ADMIN"
    RH_ANALISTA = "RH_ANALISTA"
    RH_GESTOR = "RH_GESTOR"
    LIDERANCA = "LIDERANCA"
