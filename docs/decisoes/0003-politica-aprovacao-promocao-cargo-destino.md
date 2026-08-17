# ADR-0003 — Política de aprovação de promoção baseada no cargo de destino (`P06`, `Cargo.aprovacao_adicional`)

**Status:** Aceita.

## Contexto

Promoções para cargos de maior responsabilidade tipicamente exigem uma camada extra de aprovação além de gestor e RH (ex.: promoção para Gerente exige aprovação de Diretoria). O desafio pedia um exemplo de regra condicionada a um atributo do domínio, sem introduzir uma política real de nenhuma organização específica.

Durante a revisão do SDD, o campo que carrega essa política foi originalmente modelado como `Cargo.nivel_aprovacao_necessaria`, um enum `GESTOR | RH | GERENCIA | DIRETORIA`. Isso foi identificado como redundante: `GESTOR` e `RH` já são exigidos incondicionalmente por `P04`/`P05` em toda promoção — declará-los de novo neste campo não adiciona informação e cria a possibilidade de um cargo "esquecer" de exigi-los (já que a leitura ingênua do enum sugeria que só o valor selecionado seria exigido).

## Decisão

- Renomear o campo para `Cargo.aprovacao_adicional`, com domínio restrito a `GERENCIA | DIRETORIA | null`.
- `null` significa "nenhuma aprovação além de gestor e RH". `GERENCIA`/`DIRETORIA` significam "esta aprovação, além de gestor e RH".
- `P06` ("Aprovação superior registrada e íntegra quando aplicável") avalia exclusivamente esse campo, com pré-condição "`P01` passou" e denominação obrigatória *Política de aprovação de promoção baseada no cargo de destino* — nunca "mecanismo de aprovação superior" em código ou documentação, para deixar explícito que é uma política de negócio nomeada, não um mecanismo técnico genérico.
- Nenhum outro tipo de movimentação consulta `aprovacao_adicional` (verificado por revisão de código e por teste de unidade em `promocao.py`).

## Consequências

- **Positivas:** o campo expressa exatamente a decisão de negócio ("há uma aprovação extra, e ela é esta"), sem duplicar `P04`/`P05`. A ausência desses valores redundantes no enum torna impossível, por construção, configurar um cargo que "esqueça" gestor ou RH.
- **Negativa:** exige uma migração de nome de campo/enum se este projeto evoluir a partir de uma versão anterior com `nivel_aprovacao_necessaria` — não é uma preocupação real aqui porque não há dado legado (MVP local, seed determinístico).
- **Extensões relacionadas, não implementadas:** `PX01`–`PX05` (políticas fictícias e configuráveis) mostram que o padrão "atributo do cargo/domínio → aprovação condicional" pode ser estendido, mas RC-06 proíbe implementá-las no MVP.
