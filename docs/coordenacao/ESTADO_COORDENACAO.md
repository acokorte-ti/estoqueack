# Estado — COORDENAÇÃO (arquiteto-chefe)

Chat COORDENAÇÃO ("MegaEngenheiro"). Atualizado 2026-11-04 (depois da rodada 2). Validado pelo Eduardo.

> **Sem prazo fixo (decisão do Eduardo, 2026-11-04).** Não existe data alvo nem marcos com data. O que vale é a **ordem** abaixo; a implantação acontece quando os critérios de go/no-go (§4) estiverem atendidos e o Eduardo liberar. Documentos que citam 13/11 (ex.: roteiro de implantação) leem "dia da implantação".

## 1. Ordem até a implantação

| # | Etapa | Dono | Situação |
|---|---|---|---|
| 1 | Carga T25 na homologação, re-executável, com conferência | TÉCNICO | ✅ feito |
| 2 | Telas do fluxo (T07–T14) | FRONTEND | ✅ feito |
| 3 | Parte B (PostgreSQL, concorrência, trigger) | BANCO E TESTES | ✅ feito |
| 4 | Telas de apoio T04, T05, T06, T17, T18, T23 + impressão T09 | FRONTEND | ✅ feito |
| 5 | Painel T03, T16 mínima, exportações, avisos do sino | TÉCNICO + FRONTEND | ✅ feito |
| 6 | Roteiro de implantação + backup fora do servidor | BANCO E TESTES | ✅ feito (R034 aberto: quem executa cada passo) |
| 7 | Corrigir achados da carga vistos nas telas (R036) | TÉCNICO | ✅ feito (falta o FRONTEND esconder "Estornar") |
| 8 | Revisão da prévia da carga com o Fabiano (R032, bloco 1) | Eduardo + FUNCIONAL | ✅ feito (spec v3.3 §10.7) |
| 9 | Spec atualizada com as decisões de 04/11 + R037 + R024 (perda até 6 %) | FUNCIONAL | ✅ feito (v3.3) |
| 9b | **Correção da auditoria de 06/11** (RETO do RJ em Itu em sub-lotes + marcado RETO, leitor Ø/RED/ROUND, bug da solicitação parcial; T15 mínima e consulta de RETO por origem na F1; telas; testes) | TÉCNICO + FUNCIONAL, depois FRONTEND + BANCO E TESTES | ⏳ em andamento |
| 10 | **Recarga da T25 (R038) + perda de corte 6 % no código** | TÉCNICO | ⏳ **caminho crítico** |
| 10b | Fabiano/FUNCIONAL conferem a lista do kardex e a prévia da recarga | Eduardo + FUNCIONAL | depois do 10 |
| 11 | Ponta a ponta de novo (5 caminhos) sobre a recarga | BANCO E TESTES | depois do 10 |
| 12 | Aceite com Fabiano, Matheus, Marcelo e Renato | Eduardo + BANCO E TESTES | depois do 11 e dos usuários criados |
| 13 | Go/no-go → implantação pelo roteiro | Eduardo + COORDENAÇÃO | depois do 12 |

## 2. Escopo da F1 (validado 2026-11-04)

Entra: T03–T14, T15 mínima e aba RETO por origem (v3.4, 06/11), T16 mínima, T17, T18, T23, T25, impressão da Fila RJ, exportações Excel, perfis, sync. Fica para F1.1: PDFs de romaneio/ficha, T15 completa, T16 completa, T19, T26, exportação Renato com marca, T22 equivalência. Paralelo com as planilhas depois da implantação: **planilha só conferência**, sistema é a fonte da verdade.

## 3. Riscos acompanhados

| # | Risco | Mitigação |
|---|---|---|
| K2 | RETO e RJ em Itu legados entram sem origem → rastreio por bitola só para material novo | Inventário físico + "Atribuir origem"; **dono ainda não definido** |
| K3 | Divergência sistema × Mega ("Fazer no Mega" esquecido) | T16 mínima ✅; sync 6h/13h |
| K5 | Digitação dupla no paralelo | Planilha só conferência ✅ |
| K6 | Segredos no repo | Backup externo ✅; hook bloqueia `git add -A` e leitura de segredos |
| K7 | Perda de corte | ✅ decidido: até 6 % do material usado |
| K8 | Custo/lentidão dos chats (FRONTEND) | Regras de leitura enxuta no README; PEDIDOS arquivado |

## 4. Go/no-go

1. Carga conferida pelo Fabiano (Estoque Mega = saldo Mega ± 5 kg; RJ = ESTOQUE 2026).
2. Os 5 caminhos ponta a ponta OK sobre a carga final.
3. Concorrência OK no PostgreSQL ✅.
4. Backup + restauração, com cópia externa ✅.
5. Os 4 usuários fizeram o aceite.
6. Estorno/ajuste (T18) funcionando ✅ (falta R036 item 2: o que pode ser estornado).

1, 2 ou 6 falhando → não implanta.

## 5. Pendências do Eduardo

1. R032 bloco 1 com o Fabiano (+ OPs/lotes do aceite).
2. ~~Perda de corte~~ (6 %, feito).
3. Criar os 4 usuários reais.
4. Avisar o Fabiano do IPI do NCM 82089000.
5. Dono do inventário de RETO / RJ em Itu.

## 6. Rodadas

- **R5 (06/11, auditoria):** spec v3.4 commitada (`4b383d6`); pedidos R040 (TÉCNICO), R041 (FRONTEND), R042 (BANCO E TESTES). TÉCNICO corrigindo carga/bug (em andamento). Depende do Eduardo: P19–P25 e perguntas ao Fabiano (`../carga/texto_fabiano_auditoria_2026-11-06.md`).

- **R1 (03/11):** T25, T11–T13, Parte B. Voltou toda feita.
- **R2 (04/11):** painel, T16 mínima, exportações, avisos, T04–T06/T17/T18/T23, impressão T09, roteiro de implantação, backup externo. Voltou feita, **exceto FUNCIONAL** (spec ainda na v3.1, ESTADO_FUNCIONAL sem atualização).
- **R3 (04/11):** R036 corrigido, spec v3.3, BLOCO 1 respondido pelo Fabiano, perda de corte = 6 %. Faltou o FRONTEND (T05 estornável).
- **R4a:** TÉCNICO recarga R038 + PERDA_CORTE_MAX_PCT; FRONTEND T05 estornável + T13 perda em %. **R4b** (depois da recarga): FUNCIONAL confere kardex/prévia; BANCO E TESTES ponta a ponta.

- **Migração para o Claude Code (2026-11-05):** rascunho em `projeto-controle_mp\migracao_claude_code\` (CLAUDE.md raiz/backend/frontend, 4 subagentes, /rodada, /estado, hook, settings, .mcp.json, script `aplicar_migracao.ps1`, `LEIA-ME_MIGRACAO.md`). Aplicada (commit 75c085e).
- **Handoff dos 4 chats feito (2026-11-05):** instruções permanentes de cada frente incorporadas no rascunho (CLAUDE.md raiz/backend/frontend, agentes funcional/tecnico/banco-testes, hook bloqueia também leitura de ../segredos/). Repo limpo (só frontend/tsconfig.tsbuildinfo, que vai para o .gitignore). Migração aplicada. Falta: remover as seções 'Instruções permanentes' dos ESTADO_* (duplicam os CLAUDE.md).
