# ADR 0003: Estoque por lote, com movimentos imutáveis

Status: aceito em 28/10/2026.

## Decisão

- O estoque é controlado por **lote** (contêiner + item de MP).
- Toda sobra que sai da bitola original vira um lote **RETO filho** (`lote_pai_id`), e a origem é herdada.
- O saldo do lote é mantido em `saldo_kg`, com `CHECK (saldo_kg >= 0)`, e atualizado na mesma transação do movimento.
- As tabelas `movimento` e `auditoria` são **somente inclusão**: um trigger no PostgreSQL bloqueia UPDATE e DELETE. Correção é feita sempre por estorno.
- Os três estoques são filtros sobre (planta fiscal, local físico): ITU/ITU = Mega, RJ/RJ = RJ no Rio, RJ/ITU = RJ em Itu.

## Consequências

Consultas como "kg de H13 RETO por bitola e contêiner de origem" passam a ser exatas a partir da implantação. O saldo legado sem origem entra como lote `origem_identificada = false`.
