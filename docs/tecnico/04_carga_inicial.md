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

- **Produção (13/11):** mesma sequência com as planilhas congeladas e o saldo do Mega do dia. Com `APP_ENV=prod`, a limpeza exige também `--confirmo-producao`. Faça um backup manual antes (`deploy/backup/backup.sh`).
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
