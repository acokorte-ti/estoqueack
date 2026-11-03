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
| `ORD_ST_SITUACAO` | Situação | `AB` (aberta). Domínio completo abaixo |
| `TPO_ST_CODIGO_TIPO` | Tipo da OP | OP001 |
| `ORD_DT_RECEBIMENTO` | Data prevista de recebimento | 2026-12-09 (= PRAZO da planilha) |
| `ORD_DT_ABERTURA_REAL` | Abertura | 2026-10-16 |
| `ORD_ST_ALTERNATIVO` | Código alternativo | 82355 = nº do pedido de venda (confirmado; usado quando falta a origem) |

Relacionadas: `PRO_PROG_ORDEM` (programação por operação e máquina), `PRO_MOVTOMANUF`, `PRO_ESTMOVTOMANUF` e `PRO_DEMANDA_DEP`.

### Situação da OP (`ORD_ST_SITUACAO`), mapeada em 2026-11-03 (chat BANCO E TESTES)

O domínio está no comentário da coluna no próprio Oracle. Contagem na filial 3:

| Código | Significado | OPs | No EstoqueACK |
|---|---|---|---|
| `EN` | Encerrada | 80.351 | **Bloqueia** (`OP_ENCERRADA`) |
| `CA` | Cancelada | 2.975 | **Bloqueia** (`OP_ENCERRADA`) |
| `AB` | Aberta | 1.344 | Aceita |
| `FP` | Firme planejada | 211 | Alerta `OP_NAO_ABERTA` (nenhuma tem baixa de MP nem abertura real) |
| `LB` | Liberada | 15 | Alerta `OP_NAO_ABERTA` |
| `PL` | Planejada | 1 | Alerta `OP_NAO_ABERTA` |
| `SI` | Simulada | 0 | Alerta `OP_NAO_ABERTA` |

Datas úteis: `ORD_DT_ENCERRAMENTO_REAL`, `ORD_DT_CANCELAMENTO`. Tipo da OP (`TPO_ST_CODIGO_TIPO`): `OP001` normal, `OP015`, `OP016` (para estoque, sem pedido), `OS001` (ordem de serviço).

### Cliente e pedido da OP, mapeado em 2026-11-03

```
PRO_ORDENS ─(chave org + ORD_TAB/ORD_SEQ/ORD_IN_CODIGO)→ PRO_ORIGEM (ORI_CH_TIPOORIGEM = 'D' = pedido de venda)
           ─(org + PED_SER_ST_CODIGO/PED_IN_CODIGO)→ VEN_PEDIDOVENDA ─(CLI_TAB/CLI_PAD/CLI_IN_CODIGO)→ GLO_AGENTES
cliente = GLO_AGENTES.AGN_ST_FANTASIA (ex.: 414 "ARCELORMITTAL - BELGO PIRACICABA")
```

- **Conferência:** as 79 OPs da planilha de corte desde 01/09/2026 batem 79/79 no cliente (as 2 sem cliente na planilha são OP016 de estoque, sem pedido no Mega também). Item da OP difere em 5 linhas da planilha (100100–100104, 100359, 99825): a planilha usa outro código; vai para a lista de pendências da carga.
- **Multiplicidade:** desde 2025, 8.554 OPs têm 1 origem 'D' e 37 têm 2 a 4 linhas, sempre do **mesmo** cliente. A consulta pega a de menor `ORI_IN_SEQUENCIA`.
- **Sem origem 'D':** 146 OPs abertas em 2026 (ex.: 100591). Nelas, `ORD_ST_ALTERNATIVO` é o nº do pedido (série '1'); conferido em 100591 → pedido 82402, SYLVAMO (bate com a planilha de SA). Em 3.230 OPs de 2026 o alternativo é igual ao pedido da origem.
- Consulta oficial: `consultas.ORDEM_PRODUCAO` (com o filtro `:numero` também dentro da subconsulta de origem, por desempenho).

### SA (semiacabado), mapeado em 2026-11-03

O SA é um produto em `EST_PRODUTOS` com descrição "SA … - CÓD.<item da peça>", **unidade PC**, `PRO_ST_DEFITEM = 'CO'`. `PRO_ST_ALTERNATIVO` às vezes traz "37983 - H13".

**Carga do SA** (validada com os 7 SAs da planilha de 28/10/2026: 37983 OP 100592, 91773 OP 100553, 48512, 93972, 90762, 94811, 71526), sempre no mesmo dia do SA na planilha:

| Ordem | Filial | Movimento | Documento |
|---|---|---|---|
| 1 | **13** | ED TPM 1 "Entrada por Compras", qtd = **peças** | **NF Fio Certo / Médio Vale** (ex.: 3215, a mesma da coluna da planilha) |
| 2 | 13 → 3 | SD TPM 77 / ED TPM 76 "Transferência entre Filiais" | NF de transferência (ex.: 3166) |
| 3 | 3 | SD TPM 13 na OP | nº da OP |

Até maio/2026 a compra (TPM 1) entrava direto na filial 3 (294 movimentos em 2026). Desde 25/03/2026, pela filial 13 (615). A confirmação aceita os dois: entrada TPM 1/76 nas filiais 3 ou 13, sem estorno, a partir da data do SA − 7 dias (`consultas.SITUACAO_SA`).

- **Inativo:** não existe coluna de situação no produto. O Mega marca no texto ("… INATIVO"; só 3 de 2.997 SAs). O "39294 - INAT" é anotação da planilha; no Mega, o 39294 está sem a marca. SA inativo nunca é confirmado e pede justificativa (`SA_INATIVO_MEGA`).
- **NCM:** `EST_PRODUTOS.NCM_IN_CODIGO`, bate com a planilha.
- **IPI:** `TRF_NCM.NCM_RE_ALIQIPI` (por NCM, em %). 82081000 = 5,2 % (planilha 0,052 ✓), 84669490 = 0 % ✓, 82089000 = 5,2 % no Mega × 0,08 na planilha (divergência para o Fabiano ver).
- **ICMS:** não fica no produto (depende da operação/UF); continua vindo do histórico do item (planilha de SA e SAs confirmados).

### Estrutura da OP (`PRO_DEMANDA_DEP`), mapeada em 2026-11-03

Demanda dependente da OP, ligada pela chave completa da OP (org + `ORD_TAB/ORD_SEQ/ORD_IN_CODIGO`). Componente em `COM_IN_CODIGO`; quantidade total em `DDE_RE_QTDE_NECESSARIA`, por peça em `DDE_RE_QTDE_UNITARIA`, baixada em `DDE_RE_QTDE_REQUISITADA`.

- **OP de material RJ:** o componente é o **SA** (1 PC por peça). Ex.: 100592 → 37983, 100553 → 91773, 100508 → 78988, 100092 → 68946. É a melhor sugestão de código de SA: o sistema usa o SA da estrutura e, se não houver, o mais recente do item (`sas.sugerir`).
- **OP de material Itu (caminho C):** o componente é a **MP** em kg. Ex.: 100410 → 5838 IMP-A8 RETO, 80 kg (4 × 20), baixado 80; 100408 → 98559 S1 35×125, 5,4 kg.
- Abertas desde 07/2026 (OP001): 244 com SA, 803 com MP, 1 sem estrutura.
- A API devolve `estrutura[]` em `GET /api/mega/op/{n}` (T07, informativo).

### Preço médio (`EST_SALDOFIN`), mapeado em 2026-11-03

Custo médio diário (R$/kg) = último `SFN_RE_VLCUSTO` com `SFN_IN_TIPOCUSTO = 1`, `CRI_IN_CODIGO = 1`, org (53, 1, **3**, 'G'). Em `EST_SALDOFIN` o `ORG_IN_CODIGO` é a **filial** (3 Itu, 13 RJ); tipo 2 é o fechamento do mês. **Bate exato** com a coluna de custo do relatório "Inventário do Tipo C.M.D." de 20/10/2026 nos 6 códigos (1698 = 7,939533; 5838 = 10,735212; 78290 = 13,305297; 87780 = 35,768154; 62622 = 11,893632; 60064 = 12,721839). Há datas inválidas no Mega (ano 8014): a consulta só usa datas anteriores a amanhã. Consulta: `consultas.PRECOS_MEDIOS_MP`.

### Sincronização (job das 6h e 13h + "Sincronizar agora"), no ar em 2026-11-03

- **Saldo + preço médio:** leitura completa (≈ 8 mil códigos, ~2 s) e troca de `mega_saldo` (só códigos com saldo ou preço).
- **Movimentos:** `MVT_IN_LANCAM` cresce com a inclusão, mas o Mega **altera** lançamentos depois (≈ 3 %/mês, ex.: NF com a data de movimento corrigida dias depois; `MVT_DT_ALTERA`) e **não há linha de estorno** com `MVT_BO_ESTORNO = 'S'` em 2026 (o estorno some da visão). Por isso cada sincronização relê a **janela** (movimento nos últimos 120 dias, ou alterado desde a véspera da última sincronização, ou lançamento novo) e **substitui** a cópia local da janela: pega inclusão, alteração e exclusão. Fora da janela, alterações entram por upsert. Consulta: `consultas.MOVIMENTOS_JANELA`.
- **Resultado real (system-lab, 2026-11-03):** 1ª carga 107.840 movimentos em 1 min 18 s; incremental 1.773 linhas em 4 s. A soma dos movimentos copiados reproduz o saldo do Mega nos 6 códigos de referência (2 códigos de 7.981 diferem, por lançamentos com data futura inválida).
- **Agendamento:** cron do system-lab a cada 5 min (`deploy/cron/estoqueack-agendador.sh` → `python -m app.jobs.agendador`). O app decide: sincroniza se passou um horário de `SYNC_MEGA_HORARIOS` (T23, padrão 06:00 e 13:00, fuso de SP) desde a última tentativa; erro tenta de novo em 30 min e avisa o Admin no sino (`SYNC_MEGA_FALHOU`); SAs "Aguardando Mega" são verificados a cada `VERIFICACAO_SA_MIN` (30). Log: `~/.local/state/estoqueack-agendador.log`.
- **API:** `POST /api/mega/sincronizar` (Estoque Itu, Análise, Admin; 409 se já houver uma rodando) e `GET /api/mega/sincronizacoes`.
- **Concorrência:** trava consultiva do PostgreSQL (`pg_try_advisory_xact_lock`), então cron e botão nunca rodam juntos.

## Permissões

Durante a descoberta, `estoqueack_ro` tem `SELECT ANY TABLE` e `SELECT ANY DICTIONARY`. O script final é **`scripts/mega/02_grants_restritos.sql`** (rodar como DBA): SELECT só em `EST_PRODUTOS`, `EST_VW_MOVIMENTOESTOQUE`, `EST_SALDOFIN`, `PRO_ORDENS`, `PRO_ORIGEM`, `PRO_DEMANDA_DEP`, `VEN_PEDIDOVENDA`, `GLO_AGENTES` e `TRF_NCM`, depois `REVOKE` dos dois privilégios amplos. As tabelas de base da visão (`EST_MOVIMENTO`, `EST_MOVPENDENTE`, `EST_PRODUTOS`, `EST_TIPOMOVTO`, `GLO_GRUPO_USUARIO`) são todas do `ACOKORTE`, então o GRANT na visão funciona sem GRANT OPTION. Depois do REVOKE, as ferramentas de descoberta (`scripts/mega/descobrir_mega.py`) deixam de enxergar o dicionário; para mapear algo novo, conceder de novo temporariamente.

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
