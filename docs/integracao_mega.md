# Integração com o ERP Mega (Oracle 19c)

## Princípios

- O acesso é **somente leitura**, com um usuário dedicado e um `SET TRANSACTION READ ONLY` em cada consulta.
- O Mega continua sendo a referência **fiscal**. O EstoqueACK é a referência de **rastreabilidade por lote**.
- **Nunca gravar direto nas tabelas do Mega.** A escrita fica reservada para o futuro (`MEGA_ESCRITA_HABILITADA=false`) e, quando for feita, deve usar o mecanismo oficial de integração do ERP.

## 1. Criar o usuário somente leitura (executar como DBA)

```sql
-- Ajuste o nome do PDB/esquema do Mega
CREATE USER estoqueack_ro IDENTIFIED BY "<senha-forte>";
GRANT CREATE SESSION TO estoqueack_ro;
-- Conceda SELECT apenas nas tabelas/visões necessárias (descobertas no passo 2):
GRANT SELECT ON <ESQUEMA_MEGA>.<TABELA_PRODUTO> TO estoqueack_ro;
GRANT SELECT ON <ESQUEMA_MEGA>.<TABELA_SALDO>   TO estoqueack_ro;
GRANT SELECT ON <ESQUEMA_MEGA>.<TABELA_OP>      TO estoqueack_ro;
-- Opcional, mas recomendado: limitar recursos
ALTER USER estoqueack_ro PROFILE <perfil_com_limites>;
```

## 2. Descobrir as tabelas reais

Os SQLs em `backend/app/integrations/mega/consultas.py` usam **nomes provisórios**. Para achar os nomes reais:

1. **Produto e saldo:** procure um código conhecido do relatório "Inventário C.M.D.", por exemplo `1698 – IMP-H13 RETO`:
   ```sql
   SELECT owner, table_name, column_name FROM all_tab_columns
    WHERE owner = '<ESQUEMA_MEGA>' AND (column_name LIKE '%SALDO%' OR column_name LIKE '%PRODUTO%');
   ```
2. **OP:** procure pela OP `100508` (item `68092`, cliente ArcelorMittal), que existe nas planilhas.
3. **SA:** procure o código `78988` ("SA PARTE/ACESSORIO (POS 1) 12X54X90MM - CÓD.68092").
4. Ajuste `consultas.py` e rode a validação: o total da consulta `SALDOS_MP` deve bater com a aba "estoque atual" de 20/10/2026.

## 3. Rede (OCI)

O ERP e o EstoqueACK ficam na OCI. O ideal é colocar as duas VMs na **mesma VCN** (ou fazer *Local Peering* entre as VCNs) e liberar, na Security List ou no NSG do Oracle, a **porta 1521 apenas a partir do IP privado da VM do EstoqueACK**. Assim, o banco do ERP não fica exposto na internet.

## 4. Ligar a integração

No `.env`:

```
MEGA_HABILITADO=true
MEGA_DSN=<ip-privado>:1521/<service_name>
MEGA_USUARIO=estoqueack_ro
MEGA_SENHA=<senha>
```

O driver é o `python-oracledb` em modo *thin*, que não precisa do Oracle Instant Client e funciona em ARM64.
