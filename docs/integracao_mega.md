# Integração com o ERP Mega (Oracle 19c)

Mapeamento feito em 29/10/2026 pelo chat TÉCNICO, conectado do system-lab com o usuário `estoqueack_ro`, só em leitura.

## Princípios

- O acesso é **somente leitura**, com o usuário `estoqueack_ro` e `SET TRANSACTION READ ONLY` em toda sessão.
- O Mega é a referência **fiscal**. O EstoqueACK é a referência de **rastreabilidade por lote**.
- **Nada é gravado direto nas tabelas do Mega.** A escrita está reservada para o futuro (`MEGA_ESCRITA_HABILITADA=false`) e, quando vier, deve usar o mecanismo oficial do ERP.

## Ambiente

| Item | Valor |
|---|---|
| Banco | Oracle Database 19c Standard Edition 2, num DB System da OCI |
| Endereço | IP privado `10.0.0.235`, porta 1521, VCN `vcnmegaxt` |
| Serviço / PDB | `dbmegaxt_pdb1.sub08032113590.vcnmegaxt.oraclevcn.com` / `DBMEGAXT_PDB1` |
| Esquema do Mega | `ACOKORTE` (cerca de 10.100 tabelas, prefixadas por módulo) |
| Criptografia | **Native Network Encryption obrigatória.** O driver tem de rodar em modo *thick*, com Oracle Instant Client 19 (`scripts/mega/Dockerfile.mapeamento`). O modo *thin* é recusado com DPY-3001 |
| Acesso de rede | A partir do **system-lab** (172.16.0.249, VCN própria com rota para 10.0.0.0/24). Pelo PC do Eduardo, via VPN site-to-site, a sessão cai depois de 60 s (ORA-03135), provavelmente por MTU |
| Filial Itu | `FIL_IN_CODIGO = 3` ("00003 - AÇOKORTE - MATRIZ"); organização `ORG_IN_CODIGO = 2` |

## Prefixos dos módulos

| Prefixo | Módulo |
|---|---|
| `EST_` | Estoque e compras: produtos, movimentos, recebimento |
| `PRO_` | Produção: ordens de produção, programação, apontamentos |
| `MAN_` | Apontamentos de manufatura |
| `VEN_` | Vendas |
| `DW_`, `DWMV_` | Visões e *materialized views* de BI |

## Objetos mapeados

### Produto: `ACOKORTE.EST_PRODUTOS` (cerca de 95 mil linhas)

| Coluna | Significado | Exemplo (1698) |
|---|---|---|
| `PRO_IN_CODIGO` | Código do item | 1698 |
| `PRO_ST_DESCRICAO` | Descrição | IMP-H13 RETO |
| `UNI_ST_UNIDADE` | Unidade | KG |
| `PRO_ST_DEFITEM` | Definição do item | `MP` (matéria-prima) |
| `GRU_IN_CODIGO` | Grupo | 986 ("000986 - Aço") |
| `NCM_IN_CODIGO` | NCM | 72285000 |
| `PRO_RE_PESOESPECIFICO` | **Peso específico (densidade)** | **7.9** |
| `PRO_DT_INCLUSAO` / `PRO_DT_ALTERACAO` | Datas | 2010-09-23 / 2026-10-16 |

Uma visão mais simples também existe: `DW_ADM_PRODUTOS` (`CODIGO`, `DESCRICAO`, `ID_UNIDADE`, `DEFINICAO`).

### Movimentos de estoque: `ACOKORTE.EST_VW_MOVIMENTOESTOQUE`

Essa visão é a base de `EST_MOVIMENTO`, que tem cerca de 407 mil linhas. **Resposta à P01: sim, os movimentos podem ser lidos.**

| Coluna | Significado |
|---|---|
| `FIL_IN_CODIGO` | Filial (3 = Itu) |
| `MVT_IN_LANCAM` | ID do lançamento (chave para sincronização incremental) |
| `MVT_DT_MOVIMENTO`, `MVT_DT_DOCUMENTO`, `MVT_DT_INCLUSAO` | Datas |
| `MVT_ST_ENTRSAIDA` | `ED` = entrada, `SD` = saída |
| `TPM_IN_CODIGO` / `TPM_ST_DESCRICAO` | Tipo de movimento (tabela abaixo) |
| `MVT_ST_NUMDOC` | Nº do documento. **Nas requisições para OP, é o número da OP** |
| `PRO_IN_CODIGO`, `PRO_ST_DESCRICAO` | Produto |
| `MVT_RE_QUANTIDADE` | Quantidade (kg para MP), sempre positiva; o sinal vem de `MVT_ST_ENTRSAIDA` |
| `PRO_IN_CODIGODEST`, `MVT_RE_QUANTIDADEDEST` | Produto e quantidade de destino (transferências) |
| `MVT_BO_ESTORNO` | `S`/`N` |
| `USU_IN_INCLUSAO` | Usuário do Mega que lançou |

Tipos de movimento encontrados no código 1698 (H13 RETO), filial 3:

| TPM | E/S | Descrição | Uso no EstoqueACK |
|---|---|---|---|
| 13 | SD | Requisição Materiais Ordem de Produção | **Baixa de MP na OP** (`MVT_ST_NUMDOC` = OP) |
| 36 | ED | Entrada - Transfer. de Produto | Entrada no código RETO a partir do código original |
| 35 | SD | Saída - Transfer. de Produto | Saída do código original na transferência |
| 69 / 70 | ED / SD | Entrada / Saída por Transferência Dimensional | Transferência entre códigos por mudança de dimensão |
| 75 | SD | Saída para Sucata | Sucata |
| 2 / 4 | ED / SD | Entrada / Saída por Ajuste de Inventário | Ajustes |
| 45 | ED | Entrada de Saldo Inicial | Carga inicial |
| 27 | SD | Requisição para Consumo | Consumo fora de OP |
| 9 | ED | Recebimento Ordem de Produção | — |

**Atenção:** `MVT_ST_NUMDOC` também guarda número de NF em outros tipos. Por exemplo, existe uma "Saída por Venda" com o documento 100508, que é o mesmo número de uma OP. Por isso, a busca por OP precisa sempre **filtrar `TPM_IN_CODIGO = 13`**.

### Saldo

O saldo físico de um código, numa data, é a soma dos movimentos:

```sql
SELECT SUM(DECODE(MVT_ST_ENTRSAIDA,'ED',1,'SD',-1,0) * MVT_RE_QUANTIDADE)
  FROM ACOKORTE.EST_VW_MOVIMENTOESTOQUE
 WHERE PRO_IN_CODIGO = :codigo AND FIL_IN_CODIGO = 3 AND MVT_DT_MOVIMENTO < :data_corte
```

Validado contra o relatório "Inventário do Tipo C.M.D." de 20/10/2026 (aba "estoque atual"): a diferença foi **0,000 kg** nos 6 códigos testados.

| Código | Descrição | Movimentos até 20/10 | Relatório |
|---|---|---|---|
| 1698 | IMP-H13 RETO | 2.240,042 | 2.240,042 |
| 87780 | IMP-A8 5,50X315X4600MM | 4.900,000 | 4.900 |
| 62622 | IMP-DIN 1.2746 RETO | 5.253,790 | 5.253,79 |
| 78290 | IMP-H13 24X62MM | 5.198,000 | 5.198 |
| 5838 | IMP-A8 RETO | 631,500 | 631,5 |
| 60064 | IMP-H13 110X600MM | 2.722,000 | 2.722 |

`EST_SALDOFIN` guarda **custo** por dia (`SFN_RE_VLCUSTO`), não quantidade. `EST_VW_SALDOQTDE` tem entradas e saídas por dia.

### Ordem de produção: `ACOKORTE.PRO_ORDENS` (cerca de 87 mil linhas)

| Coluna | Significado | OP 100508 |
|---|---|---|
| `ORD_IN_CODIGO` | Nº da OP | 100508 |
| `FIL_IN_CODIGO` | Filial | 3 |
| `PRO_IN_CODIGO` | Item a produzir | 68092 (confere com a planilha de corte) |
| `ORD_RE_QTDE_ORDEM` | Quantidade | 128 (confere) |
| `ORD_ST_SITUACAO` | Situação | `AB` (aberta). Códigos de encerrada e cancelada **a confirmar** |
| `TPO_ST_CODIGO_TIPO` | Tipo da OP | OP001 |
| `ORD_DT_RECEBIMENTO` | Data prevista de recebimento | 2026-12-09 (= PRAZO da planilha) |
| `ORD_DT_ABERTURA_REAL` | Abertura | 2026-10-16 |
| `ORD_ST_ALTERNATIVO` | Código alternativo | 82355 (provável vínculo com pedido/demanda, **a confirmar**) |

Relacionadas: `PRO_PROG_ORDEM` (programação por operação e máquina), `PRO_MOVTOMANUF`, `PRO_ESTMOVTOMANUF` e `PRO_DEMANDA_DEP`.

### Ainda a mapear

- **Cliente da OP:** via pedido de venda ou demanda (`ORD_ST_ALTERNATIVO`?, módulo `VEN_`).
- **Códigos de situação da OP** (encerrada e cancelada).
- **SA:** o SA é um produto em `EST_PRODUTOS` (descrição "SA ..."). É preciso confirmar a carga de saldo, provavelmente uma entrada (ED) no código do SA.
- **MP prevista na estrutura da OP:** informativa.

## Permissões

Durante a descoberta, `estoqueack_ro` tem `SELECT ANY TABLE` e `SELECT ANY DICTIONARY`. **Depois de mapear os itens acima**, trocar por GRANTs restritos (executar como DBA):

```sql
GRANT SELECT ON ACOKORTE.EST_PRODUTOS            TO estoqueack_ro;
GRANT SELECT ON ACOKORTE.EST_VW_MOVIMENTOESTOQUE TO estoqueack_ro;
GRANT SELECT ON ACOKORTE.PRO_ORDENS              TO estoqueack_ro;
-- + tabelas de cliente/pedido e o que mais for mapeado
REVOKE SELECT ANY TABLE      FROM estoqueack_ro;
REVOKE SELECT ANY DICTIONARY FROM estoqueack_ro;
```

Observação: `GRANT SELECT` numa visão de outro esquema só funciona se o dono (`ACOKORTE`) tiver os privilégios sobre as tabelas de base com `GRANT OPTION`. Se der erro, liberar as tabelas de base (`EST_MOVIMENTO` e as que a visão usar).

## Desempenho

- Consultas no dicionário (`ALL_TAB_COLUMNS` juntado com comentários) são **lentas** nesse banco. Evitar em produção.
- Filtrar sempre por `FIL_IN_CODIGO = 3` e, nos movimentos, por `PRO_IN_CODIGO` ou por faixa de `MVT_IN_LANCAM` / data.
- **Sincronização incremental:** guardar o maior `MVT_IN_LANCAM` lido e buscar só os maiores. Estornos e alterações vêm por `MVT_DT_ALTERA`.

## Ferramentas

Em `scripts/mega/`:

| Arquivo | Função |
|---|---|
| `01_criar_usuario_leitura.sql` | Cria o usuário somente leitura |
| `Dockerfile.mapeamento` | Container com Instant Client 19 |
| `testar_conexao.py` | Testa a conexão |
| `descobrir_mega.py`, `descrever_mega.py` | Descoberta de tabelas |
| `validar_mega.py`, `validar_saldo_op.py` | Validação de saldo e de OP |
| `ver_op.py` | Mostra uma OP |
| `diagnostico_conexao.py` | Diagnóstico de rede |

As credenciais ficam em `.mega_ro`, arquivo ignorado pelo Git.
