# Estado — BANCO E TESTES

Chat **BANCO E TESTES**, braço do TÉCNICO (BACKEND 2). Escopo: fechar as definições de banco (Mega e PostgreSQL) e os testes que faltam para a implantação da Fase 1 (sem data: vale a ordem das etapas e o go/no-go). Não mexe em fluxo de tela nem em regra de negócio; o que depende de outra frente vira pedido em `PEDIDOS.md`.

Atualizado: 2026-11-12 pelo chat BANCO E TESTES (rodada de 12/11, R048, ver §5d).

## Situação em uma frase

**0008 revisada (R048, sem bloqueio) e ponta a ponta preparado para as regras v3.5–v3.9; roda depois da recarga do zero.** Parte A (Mega) e Parte B (PostgreSQL) concluídas; ponta a ponta dos 5 caminhos já rodou OK com os dados da carga e o Mega real (04/11, §5); roteiro de aceite pronto.** Critérios de go/no-go nº 2 (ensaio) e nº 3 (concorrência no PostgreSQL) atendidos; o nº 2 se repete antes do aceite e depois da recarga final.

## Resumo para cada chat

| Chat | O que precisa saber |
|---|---|
| **TÉCNICO (BACKEND 2)** | (1) A **0005 é minha** (índices + preço médio com 6 casas): migração da carga, se precisar, é a **0006** (R030). (2) **Bug de concorrência corrigido** (`7790bfd`): todo código que mexe em saldo pega o lote por `movimentos.lote_ou_404(db, id, travar=True)` e lança por `movimentos.lancar`. (3) O CI roda o pytest também no PostgreSQL (trigger real): `UPDATE`/`DELETE` em `movimento`/`auditoria` falham. (4) Mega: `docs/integracao_mega.md` |
| **FRONTEND** | R031: `avisos[]` no SA (`NF_DIFERENTE_MEGA`, `IPI_DIFERENTE_MEGA`, avisos cinza) e os mesmos códigos como ALERTA em `/sas/{id}/codigo/validar` e `/cops/{id}/enviar/validar`. R027 e R028 já atendidos |
| **FUNCIONAL** | Os dois avisos pedidos no R026 (NF e IPI) estão no ar. Nada pendente com o FUNCIONAL |
| **COORDENAÇÃO** | Rodada 1 feita na ordem pedida: Parte B → avisos R026 → Parte C. **Ponta a ponta já OK em 04/11** com a carga (§5); repetir depois da recarga final. Para o aceite faltam: §6 do roteiro (OPs/lotes com o Fabiano) e os 4 usuários reais (Eduardo) |

## 1. O que foi descoberto no Mega (validado com dados reais)

Tudo conferido do system-lab com o usuário `estoqueack_ro`, só leitura. Fonte completa: `estoqueack/docs/integracao_mega.md`.

| Assunto | Resultado | Como foi conferido |
|---|---|---|
| **Situação da OP** | Domínio no próprio Oracle: `AB` Aberta, `EN` Encerrada, `CA` Cancelada, `FP` Firme planejada, `LB` Liberada, `PL` Planejada, `SI` Simulada | Contagem na filial 3 (EN 80.351, CA 2.975, AB 1.344, FP 211, LB 15, PL 1). FP/LB/PL nunca tiveram baixa de MP |
| **Cliente e pedido da OP** | `PRO_ORDENS` → `PRO_ORIGEM` (tipo 'D') → `VEN_PEDIDOVENDA` → `GLO_AGENTES` (nome fantasia). Sem origem: o "código alternativo" da OP é o nº do pedido | **79 de 79** OPs da planilha de corte desde 01/09/2026 com o cliente batendo. 37 OPs têm 2–4 origens, sempre do mesmo cliente |
| **Estrutura da OP** | OP de material **RJ** tem o **SA** como componente (ex.: 100592 → 37983). OP de material **Itu** tem a **MP em kg** (ex.: 100410 → 5838, 80 kg) | 244 OPs com SA e 803 com MP, abertas desde 07/2026 |
| **SA (semiacabado)** | Produto "SA … - CÓD.<item>", unidade **peça**. A "carga do SA" é uma **entrada por compra na filial 13** (documento = **NF Fio Certo/Médio Vale**, ex.: 3215), seguida de transferência 13 → 3 e baixa na OP. Até maio/2026 a compra entrava direto na filial 3 | 7 SAs da planilha de 28/10/2026 (37983, 91773, 48512, 93972, 90762, 94811, 71526), todos no mesmo dia da planilha |
| **SA inativo** | Não há campo de situação: o Mega marca "INATIVO" no texto (3 de 2.997 SAs). O "39294 - INAT" é só anotação da planilha | Busca na descrição |
| **NCM / IPI / ICMS** | NCM no produto; IPI pelo NCM (`TRF_NCM`); **ICMS não existe no produto** (continua vindo do histórico) | 82081000 = 5,2 % ✓; 84669490 = 0 % ✓; **82089000: Mega 5,2 % × planilha 0,08** (avisar o Fabiano) |
| **Preço médio** | Custo médio diário de `EST_SALDOFIN` (tipo 1, filial 3) | **Bate exato** com o relatório "Inventário C.M.D." de 20/10/2026 nos 6 códigos de referência |
| **Movimentos** | O Mega altera lançamentos depois (~3 %/mês) e o estorno **some** da visão (não há linha com estorno = 'S' em 2026) | Análise por mês de inclusão, jun–nov/2026 |

## 2. O que mudou no sistema (código no ar na homologação)

| Commit | O quê |
|---|---|
| `ded65ac` | Cliente e pedido da OP; situações da OP: **EN/CA bloqueiam** (`OP_ENCERRADA`), **SI/PL/FP/LB avisam** (`OP_NAO_ABERTA`, novo) |
| `2a5f11e` | Confirmação do SA pela carga real (peças, filial 13/3); SA inativo pede justificativa (`SA_INATIVO_MEGA`, novo); código inexistente avisa (`SA_NAO_ENCONTRADO_MEGA`, novo); NCM/IPI preenchidos do Mega ao confirmar |
| `64039f6` | Estrutura da OP em `GET /api/mega/op/{n}` (`estrutura[]`); **código de SA sugerido vem 1º da estrutura da OP** e, se não houver, do histórico do item |
| `7852704` | **Sincronização com o Mega**: saldo + preço médio + movimentos; migração **0004**; agendamento 06h/13h e verificação de SA a cada 30 min; `POST /api/mega/sincronizar`; `GET /api/mega/sincronizacoes` |
| `3a5f2af`, `9e1f94b`, `a253cfa` | Documentação, contrato §10.1, script de GRANTs, correção do contrato de `/lotes/compativeis` (`{ itens, total }`, pergunta do FRONTEND) |
| `3f2b1ca` | Correção do teste de horário que deixou o CI vermelho (R029) |

### API (o que o FRONTEND usa)

- `GET /api/mega/op/{n}`: novos `pedido`, `cliente_codigo`, `tipo` (OP001, OP016 estoque, OS001…), `cliente` preenchido, `situacao_descricao` para todos os códigos, `estrutura[]` (`codigo, descricao, tipo SA|MP|OUTRO, um, qtd_necessaria, qtd_unitaria, qtd_requisitada`; `null` se falhar).
- `POST /api/mega/sincronizar` (Estoque Itu, Análise, Admin; `409` se já houver uma rodando) e `GET /api/mega/sincronizacoes` (`ultima_ok`, `itens[]`).
- Códigos novos de ocorrência: `OP_NAO_ABERTA` (ALERTA), `SA_INATIVO_MEGA` (CIENCIA), `SA_NAO_ENCONTRADO_MEGA` (ALERTA).
- Aviso novo no sino: `SYNC_MEGA_FALHOU` (Admin).

### Banco do EstoqueACK (PostgreSQL)

- **Migração 0004** (aplicada na homologação): `mega_saldo` + `preco_medio_data`, `um`, `peso_especifico`; `mega_movimento` + `incluido_em`, `alterado_em`, `usuario_mega`; índices `ix_mega_movimento_codigo_data` e `ix_sync_mega_tipo_situacao`.
- 1ª carga dos movimentos do Mega: **107.840** linhas (1 min 18 s). Incremental: ~1.800 linhas em **4 s**. A soma dos movimentos copiados reproduz o saldo do Mega nos códigos de referência.

### Servidor (system-lab)

- Cron novo do usuário `ubuntu`, a cada 5 min: `deploy/cron/estoqueack-agendador.sh` (log em `~/.local/state/estoqueack-agendador.log`). O próprio sistema decide a hora pelos parâmetros da T23 (`SYNC_MEGA_HORARIOS` = 06:00,13:00; `VERIFICACAO_SA_MIN` = 30). A sincronização das **13h de 03/11 rodou sozinha (OK)**.
- Ferramenta de diagnóstico: `~/estoqueack-mapeamento/q.sh sql/<arquivo>.sql`.

### Acesso ao Mega (Oracle)

- **GRANTs restritos aplicados pelo Eduardo (DBA) em 2026-11-03** (`scripts/mega/02_grants_restritos.sql`): o `estoqueack_ro` tem só `CREATE SESSION` e SELECT em `EST_PRODUTOS`, `EST_VW_MOVIMENTOESTOQUE`, `EST_SALDOFIN`, `PRO_ORDENS`, `PRO_ORIGEM`, `PRO_DEMANDA_DEP`, `VEN_PEDIDOVENDA`, `GLO_AGENTES`, `TRF_NCM`. Conferido depois: tudo funciona; qualquer outra tabela dá ORA-00942.
- Para mapear algo novo no Mega é preciso liberar o objeto (ou o acesso amplo) de novo, temporariamente.

## 2b. Parte B — PostgreSQL de verdade (2026-11-03/04)

| Commit | O quê |
|---|---|
| `7790bfd` | **pytest também no PostgreSQL** (CI e local): o esquema é criado **pelas migrações** (com o trigger) e cada teste começa com as tabelas vazias. Teste de **models = migrações** (achou 1 índice que só existia na 0001; corrigido no model). Teste do **trigger**: `UPDATE`/`DELETE` em `movimento` e `auditoria` falham. **Teste de 2 cortes simultâneos** no mesmo lote (1.000 kg, dois cortes de 600 kg): **achou um bug real** — os dois passavam (1.200 kg saindo), porque o `SELECT … FOR UPDATE` devolvia o objeto já carregado na sessão com o saldo velho. **Corrigido** com `populate_existing` em `lote_ou_404` e nos `obter(travar=True)` (solicitação, COP, SA). Agora o 2º recebe 400 e o saldo fica 400 kg = soma dos movimentos. Migração **0005**: índices das telas (movimentos do lote, lotes por situação, fila RJ por situação/prazo, reserva por lote, sugestão de SA, contador do sino) e `mega_saldo.preco_medio` com 6 casas |
| `b3c885f` | **Teste de volume** (`VOLUME=1`, PostgreSQL): 1.000 lotes, 16 mil movimentos, 8.300 SAs, 800 solicitações, 2.000 avisos. Todas as telas principais abaixo de **0,2 s** (T04 170 ms, T09 170 ms, T07 compatíveis 123 ms, T08 89 ms, o resto < 40 ms) |
| `dffd85a` | Avisos do R026 (v3.1): `NF_DIFERENTE_MEGA` e `IPI_DIFERENTE_MEGA` (T14, prévia do código e envio do COP) |
| `ceebed5` | **Matriz perfil × tela** (§4.1) testada endpoint por endpoint nos 4 perfis (23 ações): bate 100 % com a especificação. Estados de borda: lote dividido (vale o estágio menos avançado), estorno do corte volta a Enviada (e nada é apagado), trocar OP depois do SA confirmado avisa "ajuste o SA no Mega" |
| `8573155` | **Ponta a ponta** dos 5 caminhos (`app/jobs/e2e_caminhos.py` + `deploy/e2e/rodar_e2e.sh`) e **roteiro de aceite** (`docs/tecnico/03_roteiro_aceite.md`) |

Migração sobe/desce/sobe (0001 → 0005) conferida no PostgreSQL 16 local e no CI.

## 3. Testes

- **2026-11-04: 118 testes passando no PostgreSQL** (inclui o ensaio do ponta a ponta; o teste de volume roda sob demanda com `VOLUME=1`), rodando em SQLite **e** em PostgreSQL no CI. Antes: 103 testes automáticos passando (eram 86) e lint limpo. O teste de horário da sincronização dependia da hora do dia (falhava depois das 13h); isso deixou o CI vermelho a partir do `a253cfa` (R029) e foi corrigido no `3f2b1ca` (CI verde de novo). Novos: `test_mega_op.py` (situações, cliente/pedido, estrutura, sugestão de SA), `test_sync_mega.py` (saldo/preço, janela com alteração e exclusão, falha avisando o Admin, horários 06h/13h, perfis do botão) e casos novos em `test_fluxo_cop_sa.py` (SA inativo, inexistente, NCM/IPI).
- Conferência real no system-lab com o gateway do Mega antes e depois dos GRANTs.

## 4. Pedidos abertos por este chat

| ID | Para | Assunto | Situação |
|---|---|---|---|
| R026 | FUNCIONAL | FP/LB bloqueiam ou só avisam? Sugestão de SA pela estrutura; SA inativo; IPI da planilha | RESPONDIDO (v3.1); os dois avisos pedidos (NF e IPI) **feitos** no `dffd85a` |
| R030 | TÉCNICO | 0005 é minha (carga → 0006); bug de concorrência corrigido e a regra `lote_ou_404(travar=True)` + `lancar`; pytest no PostgreSQL | ABERTO |
| R031 | FRONTEND | `avisos[]` do SA e os códigos `NF_DIFERENTE_MEGA` / `IPI_DIFERENTE_MEGA` | ABERTO |
| R027 | FRONTEND | Campos novos da OP e códigos novos | RESPONDIDO pelo FRONTEND (`8772e6b`) |
| R028 | FRONTEND | "Sincronizar agora" e "Mega atualizado em …" | RESPONDIDO pelo FRONTEND (`21cdec9`, no topo do Painel) |
| R029 | (FRONTEND → TÉCNICO) | CI vermelho desde `a253cfa` | RESPONDIDO: era o teste de horário deste chat; corrigido no `3f2b1ca` |

## 5. Ponta a ponta com dados reais — **1º ensaio OK em 2026-11-04** (sem data-alvo)

A carga T25 já estava na homologação (1.137 lotes, 2.144 movimentos, 8.293 SAs). Rodei `deploy/e2e/rodar_e2e.sh`: copia o banco da homologação para `estoqueack_e2e`, roda os 5 caminhos pela API com o **Mega real** e apaga a cópia (o banco em uso não é tocado).

| Caminho | OP real | Lote da carga | Resultado |
|---|---|---|---|
| A — corte no RJ | 100592 | L-000185 (RJ no Rio) | **OK**: Enviada → Cortada → COP → SA confirmado no Mega → NF → Em trânsito → **Concluída** (0,9 s) |
| B — peça inteira | 100553 | L-000180 (RJ no Rio) | **OK**: … → recebida vira lote RJ em Itu → corte em Itu com sobra fora da bitola (lote RETO L-001139) → **Concluída** |
| B2 — RJ em Itu | 100550 | L-000730 (RJ em Itu) | **OK**: corte em Itu gera linha de SA; SA confirmado; NF só fiscal |
| C — material Mega | 100687 | L-000958 (Estoque Mega) | **OK**: "Baixar 11,0 kg do código 71928 na OP 100687. Transferir 4,0 kg do código 71928 para o código 72801 (IMP-HGNi06 RETO)." |
| D — entrada NF RJ | — | lote novo L-001141 | **OK**; NF repetida bloqueada |
| Conferência final | | todos os 1.141 lotes | **0 saldo negativo; saldo = soma dos movimentos em 100 % dos lotes** |

Os SAs das OPs 100592/100553/100550 foram confirmados **pelo Mega de verdade** (entrada na filial 13 de 28/10): nenhuma confirmação simulada foi necessária. Relatório: `~/.local/state/estoqueack-e2e-20261104-0725.json` (system-lab). No 1º disparo, o B2 parou porque o roteiro escolheu uma OP de material Itu (sem SA); a escolha das OPs passou a olhar a estrutura no Mega (`c10b975`).

## 5b. Rodada 2 da COORDENAÇÃO (2026-11-04)

| Item | Situação |
|---|---|
| **Roteiro de implantação** | Pronto: `estoqueack/docs/tecnico/06_implantacao.md` — congelamento das planilhas em D-1 18:00, congelamento de código de D-1 18:00 a D 18:00, em D 06:15 pausa dos crons → backup (local + externo) → versão/migrações → `APP_ENV=prod` → planilhas no servidor → Sincronizar agora → prévia → carga `--confirmo-producao` → conferência (a)–(d) + `deploy/implantacao/conferir.sh` + Fabiano confere 3 lotes → smoke test (inclui o ponta a ponta numa cópia do banco carregado) → liberação 08:00. **Rollback** em dois níveis (antes da liberação: não libera; depois: critérios objetivos e `deploy/implantacao/movimentos_desde.sh` gera o CSV do que foi lançado no sistema para voltar às planilhas congeladas). Divisão de tarefas proposta ao TÉCNICO no **R034** (`054e618`) |
| **Backup fora do servidor (go/no-go nº 4)** | Scripts prontos e ensaiados com um Object Storage simulado (`803e1c9`): `copia_externa.sh` (PAR **só de escrita**, sha256 no objeto), `testar_restauracao_externa.sh` (baixa o mais recente do bucket, confere o sha256 e restaura num PostgreSQL temporário). **Falta o Eduardo no console da OCI** (≈ 15 min): bucket privado `estoqueack-backup`, política do ciclo de vida, regras de ciclo de vida (diário 40 dias, mensal 400), regra de retenção de 35 dias e os 2 PARs, e deixar as URLs em `Documents\projeto-controle_mp\segredos\par_backup.txt` (fora do repositório). Passo a passo: `estoqueack/docs/tecnico/05_backup_externo.md` §2. Depois eu instalo e testo (§3 do mesmo documento) |
| **Testes da T16 mínima** | Aguardando a API do TÉCNICO (ainda não commitada) |
| **E2E e aceite** | Sem data; ver §6 |

## 5c. Rodada da auditoria de 06/11 (2026-11-06)

| Item | Resultado |
|---|---|
| **Revisão da migração 0007** (R042) | Sobe/desce limpo; `movimento`/`auditoria` (trigger de imutabilidade) não são tocadas; `criado_pela_t15` tem `server_default false`. **Pontos para o TÉCNICO (pedido R044):** (1) não há índice único parcial em `pendencia_mega (codigo) WHERE tipo='ENTRADA' AND situacao='ABERTA'`: "uma ABERTA por código" depende só do código (duas sincronizações simultâneas poderiam criar duas); (2) `situacao`, `motivo` sem CHECK (só `tipo` tem); (3) `justificativa` obrigatória na DESCARTADA só na API; (4) a diferença explicada nunca vence: se o Mega estorna a NF depois do "Não é entrada", a conciliação mostra `MEGA_MENOR` com explicada 1.450 e diferença não explicada −1.450 (comportamento seguro, coberto por teste) |
| **Bitola de origem** (`origem_ref["bitola_origem"]`) | Texto livre agrupado por igualdade exata no domínio (`reto_por_origem`): "IMP-D2 25X610MM" e "imp-d2 25x610mm" virariam duas linhas; o filtro da tela normaliza (`_norm_medida`), o agrupamento não. Sem índice (JSON): ok no volume atual |
| **Testes novos** | `test_auditoria_0611_banco.py` (carga sintética: RETO do RJ em Itu D2 1.100 kg e DC53 1.022 kg quebrados em sub-lotes, soma = célula, tipo RETO, saldo = soma dos movimentos, aba por origem) e `test_modelo_diferenca_explicada_revisao_banco` em `test_t15_reto_origem_p10.py`. Já cobertos pelo TÉCNICO e conferidos: Ø/RED/ROUND N×M redondo, solicitação parcial em material insuficiente, T15 (criar lote, não é entrada, reabrir) e P10. suíte inteira verde no SQLite local (0 falhas, ruff limpo); PostgreSQL no CI |
| **Datas-prazo** | Retiradas de `03_roteiro_aceite.md`, `06_implantacao.md` (renomeado de `06_implantacao_13_11.md`), `deploy/implantacao/` e deste arquivo. PARs de 13/11/2027 (`05_backup_externo.md`) mantidos |
| **Recarga** | Não rodada (fica para depois da etapa de correção) |

## 5d. Rodada de 12/11 (R048)

**No ar:** migração **0008** revisada no PostgreSQL 16 (local, `pgserver`): sobe/desce/sobe limpo; com 3 ENTRADA ABERTA do mesmo código antes, fica só a MIN(id) e as outras viram ENCERRADA; depois, 2ª ABERTA do código = `UniqueViolation`, situação/motivo fora da lista = `CheckViolation`; DIVERGENCIA e DESCARTADA não são afetadas; triggers de `movimento`/`auditoria` intactos; `consumo_misto` NOT NULL default false nas duas tabelas. **Homologação** (só leitura): alembic 0008, índice e 3 CHECKs presentes, 9 ABERTA + 10 ENCERRADA, 0 duplicada, 0 ENCERRADA sem data, parâmetros 8 e 7; 1.145 lotes, 0 negativo, saldo = soma dos movimentos em 100 %; **198 lotes RJ com código do Mega** (carga antiga, some na recarga do zero). Suíte inteira verde em SQLite e no PostgreSQL local.

**Testes novos** (`backend/tests/test_banco_r048.py`, dados fictícios): 1.2379 = D2 e 1.2344 = H13 na mesma linha, bitola/comprimento diferente separa; CR8MOD e A8 MOD em linha própria; múltiplo ≠ comprimento com o mesmo número; limites exatos 8 %/5 % (domínio e T13 com lote RJ em Itu inteiro, RETO RJ em Itu e Estoque Mega); T10 peça inteira com `BARRA_MAIS_LEVE_QUE_PECA` (só aviso, grava) e sem tolerância na barra pesada; consumo misto na ordem RJ → Itu, terceira solicitação sem marca avisa, corte em Itu sem marca não é escondido; entrada NF do RJ na bitola de um código do Mega cria item sem código e a sugestão põe os dois na mesma linha; carga pela linha de comando com `--correcoes` (ilegível/inexistente para com código 2; com escrita diferente aplica, grava nota e aba do relatório; kg diferente não aplica), RETO DC53 sem lote-pai mesmo com candidato único. 1 xfail: P28(1) "mesma liga não pede estou ciente" (R053).

**Ponta a ponta preparado (não rodado):** `app/jobs/e2e_caminhos.py` passa a conferir 8 % no B (só prévias: 7 % passa, 9 % pede com "8 %"), consumo misto no B2 (corte marcado; prévia da solicitação ao RJ da mesma OP com e sem a marca), lote do D sem código do Mega e, na conferência final, `lotes_rj_com_codigo_mega = 0` (entra no OK). Ensaio com Mega falso no pytest verde. Roteiro de aceite atualizado (8 %/5 %, consumo misto, barra mais leve, RJ sem código).

**Pedido aberto:** R053 ao TÉCNICO (P28(1) ciência, tabela de equivalências fixa, comprimento na entrada NF, correção não aplicada em silêncio, detalhes da 0008).

## 6. Próximos passos deste chat

0. **Depois da recarga do zero** (espera o ok do Eduardo e do Fabiano na paridade): rodar `deploy/e2e/rodar_e2e.sh` (uma conexão) e mostrar a tabela dos 5 caminhos + conferência (inclui 0 lote RJ com código).
1. **Backup externo:** assim que o Eduardo criar o bucket e os PARs, instalar, rodar o 1º envio, o teste de restauração a partir do bucket e a prova de que o PAR de escrita não apaga; marcar o go/no-go nº 4.
2. **Testes da T16 mínima** quando a API sair (diferença por código Mega × soma dos lotes > 5 kg; perfis; volume).
3. **Repetir o ponta a ponta** depois da recarga final: `deploy/e2e/rodar_e2e.sh` (≈ 1 min).
4. **Aceite:** `estoqueack/docs/tecnico/03_roteiro_aceite.md`. Falta o §6 (OPs/lotes) com o Fabiano antes do aceite e os 4 usuários reais (Eduardo).
5. **Implantação:** executar a minha parte do roteiro (06_implantacao.md) depois da resposta do TÉCNICO no R034.
6. Acompanhar R030, R031 e R034.

## 7. Em andamento / fora do repositório (2026-11-05, migração para o Claude Code)

- **Repositório:** tudo deste chat está commitado e no `origin/main` (último: `054e618`). Nada pendente de commit.
- **Em andamento (aguardando outros):** backup externo (Eduardo criar bucket + 2 PARs no console, `docs/tecnico/05_backup_externo.md` §2; depois instalar e testar, §3); testes da T16 mínima (API do TÉCNICO ainda não saiu); R034 (TÉCNICO confirmar divisão do roteiro de implantação); R030/R031 abertos; repetir ponta a ponta após a recarga do R032; aceite.
- **Só no servidor (system-lab), fora do repo:** `~/estoqueack-mapeamento/q.py` + `q.sh` + `sql/*.sql` (runner de consultas ao Mega usado no mapeamento; com os GRANTs restritos o dicionário não é mais visível); crontab com `deploy/cron/estoqueack-agendador.sh` (a cada 5 min); relatórios `~/.local/state/estoqueack-e2e-*.json`.
- **Só no sandbox (some ao reiniciar):** PostgreSQL 16 de teste via `pip install pgserver` em `/tmp/pgv` + `/tmp/bt/rodar_pg.sh`. No Claude Code, rodar os testes no PostgreSQL com `TEST_DATABASE_URL=postgresql+psycopg://… pytest` (banco apagado).
- **Datas:** não há data-alvo. Os roteiros (`03_roteiro_aceite.md`, `06_implantacao.md`) usam D-1/D e valem como **ordem de etapas e go/no-go**; a data real entra só quando o Eduardo marcar.

## 8. Instruções permanentes desta frente

1. **Consultas ao Mega:** sempre a query **completa**, pronta para copiar; diagnóstico vai **no chat**, não em arquivo; no PL/SQL Developer **sem linha em branco** no meio do comando; ligar dados por **OP + data**, olhar o recorte recente e mostrar exemplos reais antes de concluir. Mega é **só leitura**; GRANT/REVOKE o Eduardo roda como DBA (mandar script pronto).
2. **Servidor:** eu executo no system-lab (não mandar comandos para o Eduardo colar, exceto DBA Oracle e console M365/OCI). **Uma** sessão SSH (Snort bloqueia várias); se der erro, parar e explicar, não insistir. Na sessão: `git --no-pager`, **sem `sleep` longo** (a saída atrasa e parece travar); esperar fora e ler com `read_process_output`.
3. **Git:** nunca `git add -A`/`.`; só arquivos explícitos e `git status --short --untracked-files=all` antes; commit/push pelo Windows com o `.github_token` (o git no sandbox prende `index.lock`). Há outros chats mexendo na mesma pasta: não commitar arquivos deles. `git update-index --chmod=+x` para scripts.
4. **Segredos:** nunca em `estoqueack\` (repo público) nem no chat; URLs de PAR/senhas vão por arquivo em `Documents\projeto-controle_mp\segredos\` e eu copio para o servidor. Planilhas nunca no repo.
5. **Banco:** nunca editar migração já aplicada (a próxima é a **0006**); todo código que mexe em saldo usa `movimentos.lote_ou_404(travar=True)` + `movimentos.lancar`; `movimento`/`auditoria` são só-inclusão (correção por estorno). Testes que testam trava/trigger só valem no PostgreSQL.
6. **Testes na homologação:** ponta a ponta só em **cópia** do banco (`deploy/e2e/rodar_e2e.sh`, nome `_e2e`); apagar só o que eu criar. Teste não pode depender da hora do dia (já derrubou o CI uma vez, R029).
7. **Planos sem prazo:** organizar por ordem de etapas e critérios de go/no-go, sem "até dia X".
8. **Coordenação:** ao terminar cada parte, atualizar este ESTADO, `DECISOES.md` (com data e "chat BANCO E TESTES"), `PEDIDOS.md` e `00_RETOMAR_PROJETO.md`; mudou campo da API → pedido ao FRONTEND; regra de negócio → pedido ao FUNCIONAL.
