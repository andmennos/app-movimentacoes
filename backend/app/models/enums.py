import enum


class TipoMovimentacao(str, enum.Enum):
    TRANSFERENCIA = "TRANSFERENCIA"
    PROMOCAO = "PROMOCAO"
    TROCA_GESTOR = "TROCA_GESTOR"
    MUDANCA_CENTRO_CUSTO = "MUDANCA_CENTRO_CUSTO"
    ALTERACAO_ESTRUTURA = "ALTERACAO_ESTRUTURA"


class StatusMovimentacao(str, enum.Enum):
    PENDENTE = "PENDENTE"
    APROVADA = "APROVADA"
    REPROVADA = "REPROVADA"


class ResultadoValidacao(str, enum.Enum):
    APROVADA = "APROVADA"
    REPROVADA = "REPROVADA"
    AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO"


class TipoAprovacao(str, enum.Enum):
    GESTOR_ORIGEM = "GESTOR_ORIGEM"
    GESTOR_DESTINO = "GESTOR_DESTINO"
    RH = "RH"
    GERENCIA = "GERENCIA"
    DIRETORIA = "DIRETORIA"


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
