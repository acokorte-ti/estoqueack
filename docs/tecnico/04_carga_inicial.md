# Carga inicial das planilhas (T25)

Criado em 2026-11-03 pelo TÉCNICO (BACKEND 2). Código: `backend/app/carga/`. Especificação: §10.

## 1. Como rodar (system-lab)

As planilhas **nunca** entram no repositório (é público). Ficam em `~/estoqueack-carga/planilhas/<data>/` no servidor (pasta 700, arquivos 600). Os relatórios ficam em `~/estoqueack-carga/relatorios/` e uma cópia vai para `Documents\projeto-controle_mp\carga\relatorios\` no PC do Eduardo.

```bash
# 1) enviar as planilhas (do PC do Eduardo, uma conexão)
scp "ESTOQUE 2026.xlsx" "Materia Prima Geral 20out.xlsx" "CONTROLE DE CORTE - RIO DE JANEIRO.xlsx" \
    "ATUAL_PLANILHA_CADASTRO PRODUTOS SEMI ACABADO .xlsx" system-lab:estoqueack-carga/planilhas/2026-11-03/

# 2) no system-lab, em ~/apps/estoqueack: copiar para dentro do container da API
docker compose exec -T api mkdir -p /tmp/carga/planilhas /tmp/carga/relatorios
docker cp ~/estoqueack-carga/planilhas/2026-11-03/. estoqueack-api-1:/tmp/carga/planilhas/
docker compose exec -T -u 0 api chown -R app /tmp/carga

# 3) antes: saldo do Mega atualizado ("Sincronizar agora" na tela ou POST /api/mega/sincronizar)

# 4) prévia (não grava nada)
docker compose exec -T api python -m app.carga --pasta /tmp/carga/planilhas --saida /tmp/carga/relatorios

# 5) gravar (limpa os dados operacionais e recarrega; re-executável)
docker compose exec -T api python -m app.carga --pasta /tmp/carga/planilhas --saida /tmp/carga/relatorios --importar --limpar

# 6) trazer o relatório
docker cp estoqueack-api-1:/tmp/carga/relatorios/. ~/estoqueack-carga/relatorios/
```

- **Produção (dia da implantação):** mesma sequência com as planilhas congeladas e o saldo do Mega do dia. Com `APP_ENV=prod`, a limpeza exige também `--confirmo-producao`. Faça um backup manual antes (`deploy/backup/backup.sh`).
- **Estrutura mudou:** se alguma aba ou coluna não estiver onde estava em 28/10–03/11, a carga **para** (código de saída 2) e diz o que mudou. Não adaptar sem falar com a COORDENAÇÃO.
- **Limpeza:** `TRUNCATE` das tabelas operacionais (lotes, movimentos, solicitações, cortes, COPs, NFs, SAs, entradas, reservas, notas, paridade, notificações, catálogo de itens e contêineres). Ficam: usuários, auditoria, ligas, equivalências, parâmetros e o cache do Mega. Tudo numa transação: se der erro, nada muda. Cada carga grava um registro `CARGA_INICIAL` na auditoria.

## 2. O que vira o quê

| Origem | Vira |
|---|---|
| Estoque Geral (591 linhas) | Catálogo `item_mp` (código Mega, comprimento fixado, clientes/uso). Observações com "reservado / não usar / somente…" viram **restrição** nos lotes do item (a revisar). "SUBSTITUÍDO POR …" vira `substituido_por` quando o substituto é encontrado |
| ESTOQUE 2026 (210 linhas) | 1 lote **RJ no Rio** por linha: saldo inicial = PESO INICIAL; cada consumo = `SAIDA_CORTE_RJ` com OP e data do comentário (ano inferido: o mais recente ≤ hoje). Confere com TOTAL EM ESTOQUE (AN) |
| HISTORICO | Notas nos lotes ativos (entrada por barra). Contêiner + material que não está mais na ESTOQUE 2026 vira **lote esgotado** (entrada, sucata e baixa "saídas anteriores ao sistema"), só para consulta e para ligar o histórico de cortes |
| Estoque Geral, coluna RJ em Itu | 1 lote **RJ em Itu** por item, origem não identificada [P07] |
| Saldo do Mega (`mega_saldo`, sincronização) | 1 lote **Estoque Mega** por código com saldo, origem não identificada; código RETO = lote RETO. Só códigos do Estoque Geral ou com liga de aço conhecida (bronze, rolamento, inox… ficam de fora, listados) |
| ESTOQUE 2026 × Estoque Geral | **Paridade RJ ↔ CM** (`paridade_rj`, sempre "a confirmar"): mesma bitola e mesma família de liga (1.2344→H13, A8 MOD→A8, 1.2379→D2). Sem par: sugere bitola até 2 mm de diferença |
| Controle de Corte (810 linhas) | Solicitações com a situação da planilha (Concluída, Em trânsito, Enviada = fila RJ, Material insuficiente, Cancelada), cortes (PESO2, ou o consumo da ESTOQUE 2026 com a mesma OP + contêiner) e COPs ("COP 598"). O movimento da ESTOQUE 2026 é ligado ao corte pela OP + contêiner |
| Planilha de SA (2016–2026, 8.293 linhas) | SAs `CARGA` confirmados (base da sugestão de código por item); NF, R$ e demais colunas em `dados_extra` |

## 3. Relatório (Excel)

Abas: **Resumo** (contagens e pendências por tipo), **Conferência** (a–d), **Pendências** (tipo, gravidade, descrição, sugestão, arquivo/aba/linha/célula), **Paridade RJ x CM** (com colunas para o Fabiano confirmar e corrigir), **Lotes**, **Solicitações** e **Ligas novas**.

Gravidade: **BLOQUEIA** (a linha não entra), **REVISAR** (entra, mas o Fabiano confere) e **INFO**.

## 4. Conferência

- (a) soma dos lotes do Estoque Mega por código × saldo do Mega (tolerância 5 kg), feita no banco depois de gravar;
- (b) total RJ no Rio × ESTOQUE 2026 (linha a linha e total) e, como informação, × Estoque Geral;
- (c) total RJ em Itu × Estoque Geral;
- (d) solicitações, cortes, COPs e SAs importados × linhas das planilhas (as diferenças estão nas pendências).

## 5. Paridade RJ × Itu e arquivo de correções (2026-11-11, R049, P28, P29)

- **Paridade:** o lote RJ (no Rio e em Itu) entra **sem código do Mega**. A carga só classifica cada material RJ contra as linhas de Itu (Estoque Geral com código) pela chave `medidas.chave_material`: liga (1.2344 = H13, 1.2379 = D2; MOD é outra liga), formato, seção, comprimento informado (com faixa) e múltiplo. Linha da ESTOQUE 2026 sem comprimento usa o comprimento do HISTORICO do mesmo contêiner (P29). Relatório: abas "Paridade RJ x Itu", "Comprimento do HISTORICO" e "Correções aplicadas".
- **Estoque Geral:** qualquer `Materia Prima Geral*.xlsx` na pasta (um só).
- **Correções respondidas que a planilha não vai receber:** arquivo JSON **fora do repositório** (no PC: `Documents\projeto-controle_mp\carga\correcoes_carga.json`; no servidor, junto das planilhas), passado com `--correcoes`:

```json
{ "origem_reto": [ { "linha_descricao": "<descrição da linha RETO no Estoque Geral>",
                     "origem_planilha": "<medida de origem como está no comentário>",
                     "origem_correta": "<medida correta>", "kg": 0, "fonte": "<quem respondeu e quando>" } ] }
```

  `kg` é opcional (sem ele, vale para qualquer parcela com essa origem). Cada correção aplicada vai para a nota do lote, para a pendência `CORRECAO_APLICADA` e para a aba "Correções aplicadas". Arquivo ilegível → a carga para (código 2).

- **Tipos novos (spec v3.11 §10.9 B, 2026-11-17; código em `app/carga/correcoes.py`).** Correção que não casa com a planilha → `CORRECAO_NAO_APLICADA` (BLOQUEIA: a gravação é recusada). A planilha não muda: o valor original vai para a nota do lote.

```json
{ "leitura": [ { "aba": "ESTOQUE 2026 | HISTORICO | CONTROLE DE CORTE | SA",
                 "linhas": [90, "252-269"], "conteiner": "CTxx" ou ["CTxx", "CTyy"],
                 "descricao_planilha": "<texto inteiro>", "contem": "<regex; no SA, MATERIAL + DIMENSÃO>",
                 "liga_planilha": "1.2746", "liga_correta": "H13",          (troca só a liga no texto)
                 "descricao_correta": "<texto novo>", "conteiner_correto": "CTzz", "nota": "<vai para o lote>",
                 "esperado": 6, "fonte": "<quem confirmou e quando>" } ],
  "consumo_sem_op": [ { "celula": "J163", "op_planilha": 989123, "fonte": "…" } ],     (op_planilha null = "OP -")
  "paridade_manual": [ { "descricao_rj": "<material da ESTOQUE 2026>", "codigo_itu": 0,
                         "descricao_itu": "<descrição do código no Estoque Geral>", "fonte": "…" } ],
  "avisos": [ { "aba": "Estoque Geral | ESTOQUE 2026", "linha": 0, "descricao_planilha": "…",
                "texto": "<pergunta em aberto>", "fonte": "…" } ],
  "corte_planilha1": [ { "linha": 0, "op": 0, "conteiner": "<CT>", "fonte": "…" } ] }
```

  `corte_planilha1` (2026-11-17, R063, [proposta, P37(a)]): só essas linhas da aba "Planilha1" do Controle de Corte são lidas (o resto da aba continua fora) e entram como solicitação **concluída** (corte no RJ, recebido), ligada ao SA da mesma OP e contêiner; a liberação não tem movimento (saldo não muda). OP/contêiner que não casam → `CORRECAO_NAO_APLICADA` (bloqueia).
- **Prazo sem ano (2026-11-17, R065(1)):** PRAZO do Controle de Corte mais de 180 dias **antes** da DATA SOLICITADA → mesmo dia/mês do ano seguinte (pendência INFO `PRAZO_ANO_CORRIGIDO`); até 180 dias antes fica como está. Planilhas de 17/11: 18 linhas (2 abertas na Fila RJ, 16 concluídas).
- **`CONSUMO_EM_OUTRO_MATERIAL`** (REVISAR, 2026-11-17): o consumo da OP na ESTOQUE 2026 está em outro material do mesmo contêiner que o do Controle de Corte (a liberação fica no lote do Corte, a baixa no outro). Corrigir com `leitura` na aba CONTROLE DE CORTE (`descricao_correta` + `conteiner_correto`), como a OP da P37(b).

  Filtros de `leitura` somam (todos têm de casar); `esperado` = quantas linhas têm de casar. `paridade_manual` (P34(a)): o lote RJ mantém a própria medida e o item ganha `item_mp.paridade_item_id` (migração 0009) = item do código de Itu, que a T04/T07 usam só para agrupar. `avisos` não muda nada: vira pendência `PENDENTE_USUARIO` e nota do lote.
- **O que a carga faz sozinha (§10.9 A):** contêiner do Controle de Corte pelo da ESTOQUE 2026 + SA da mesma OP (`CONTEINER_CORRIGIDO`; se discordam, fica o do Corte: `CONTEINER_DISCORDANTE`; resposta do usuário para um caso = correção `leitura` com `conteiner_correto` nas linhas do Corte e do SA, ex.: pendências de 18/11 item 14, Eduardo, 2026-11-19); corte dividido como a ESTOQUE 2026 mostra quando o peso do Corte = soma das partes (`CORTE_DIVIDIDO`); peso inicial = ENTRADA do HISTORICO, com `AJUSTE_INVENTARIO` "saídas anteriores a 2026" em 31/12/2025 até o PESO INICIAL da ESTOQUE 2026 (conferência "(b) saldo de abertura"); sem HISTORICO, PESO INICIAL + `PESO_INICIAL_SEM_PACKING_LIST`; restrição das colunas RJ gravada em `item_mp.restricao_uso` (item RJ criado sem lote se preciso; todo lote novo do item herda, `movimentos.criar_lote`); faixa da seção (`500~610`) ou lista com "/" (`13x510/560/610`, Eduardo, 2026-11-19) pelo maior valor, com a escrita da planilha na nota do lote (no redondo, `ØNxM` é Ø × comprimento: faixa/lista depois do Ø é do comprimento). Abas do relatório: "Contêiner do Corte (B05)", "Corte dividido (B07)", "Peso inicial (B08)", "Restrições no item (B09)", "Em aberto (avisos)".

```bash
docker compose exec -T api python -m app.carga --pasta /tmp/carga/planilhas --saida /tmp/carga/relatorios \
    --correcoes /tmp/carga/correcoes_carga.json
```

