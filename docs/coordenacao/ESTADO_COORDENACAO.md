# Estado — COORDENAÇÃO (arquiteto-chefe)

Chat COORDENAÇÃO (Claude Code). Atualizado 2026-11-18. **Para retomar (troca de conta do Claude): ler `00_RETOMAR_COORDENACAO.md`.**

> **Sem prazo fixo (decisão do Eduardo, 2026-11-04).** Não existe data alvo nem marcos com data. O que vale é a **ordem** abaixo; a implantação acontece quando os critérios de go/no-go (§4) estiverem atendidos e o Eduardo liberar. Documentos que citam 13/11 (ex.: roteiro de implantação) leem "dia da implantação".

## 1. Ordem até a implantação

| # | Etapa | Dono | Situação |
|---|---|---|---|
| 1 | Carga T25 na homologação, re-executável, com conferência | TÉCNICO | ✅ feito |
| 2 | Telas do fluxo (T07–T14) | FRONTEND | ✅ feito |
| 3 | Parte B (PostgreSQL, concorrência, trigger) | BANCO E TESTES | ✅ feito |
| 4 | Telas de apoio T04, T05, T06, T17, T18, T23 + impressão T09 | FRONTEND | ✅ feito |
| 5 | Painel T03, T16 mínima, exportações, avisos do sino | TÉCNICO + FRONTEND | ✅ feito |
| 6 | Roteiro de implantação + backup fora do servidor | BANCO E TESTES | roteiro ✅; **backup externo: scripts prontos, falta o Eduardo criar bucket + 2 PARs na OCI** (`docs/tecnico/05_backup_externo.md` §2) |
| 7 | Corrigir achados da carga vistos nas telas (R036) | TÉCNICO | ✅ feito (falta o FRONTEND esconder "Estornar") |
| 8 | Revisão da prévia da carga com o Fabiano (R032, bloco 1) | Eduardo + FUNCIONAL | ✅ feito (spec v3.3 §10.7) |
| 9 | Spec atualizada com as decisões de 04/11 + R037 + R024 (perda até 6 %) | FUNCIONAL | ✅ feito (v3.3) |
| 9b | Correção da auditoria de 06/11 (RETO do RJ em Itu em sub-lotes + RETO, leitor Ø/RED/ROUND, solicitação parcial; T15 mínima, RETO por origem; telas; testes) | todas | ✅ feito (até `d339372`) |
| 10 | Regras novas (spec v3.5–v3.13): paridade liga × bitola, 8 % RJ, consumo misto, peso real com bloqueio, regra do RETO, menu renomeado | TÉCNICO + FRONTEND | ✅ no ar (até `b0cf389`) |
| 10b | Paridade conferida pelo Fabiano (3 exceções) e respostas de 17/11 aplicadas | Eduardo + Fabiano | ✅ (restam dúvidas menores em `../carga/PENDENCIAS_USUARIOS_2026-11-18.txt`) |
| 11 | Recarga do zero (planilhas 2026-11-17) + conferência + ponta a ponta 5 caminhos | TÉCNICO + BANCO E TESTES | ✅ 2026-11-17: Estoque Mega = Mega; RJ no Rio = ESTOQUE 2026; 5 caminhos OK |
| 12 | Teste manual do Eduardo (roteiro `../carga/ROTEIRO_TESTE_MANUAL_2026-11-17.md`) com ajustes pedidos por ele (17/11: filtro "contém", Fila RJ, vários lotes na OP, lote estritamente maior, menu, impressão) → aceite com os usuários | Eduardo + todas | ⏳ em andamento; falta programar anexos/NF enriquecida (R074–R076) e o fechamento mensal (espera a Inês) |
| 13 | Go/no-go → implantação pelo roteiro | Eduardo + COORDENAÇÃO | depois do 12 |

## 2. Escopo da F1 (validado 2026-11-04)

Entra: T03–T14, T15 mínima e aba RETO por origem (v3.4, 06/11), T16 mínima, T17, T18, T23, T25, impressão da Fila RJ, exportações Excel, perfis, sync. Fica para F1.1: PDFs de romaneio/ficha, T15 completa, T16 completa, T19, T26, exportação Renato com marca, T22 equivalência. Paralelo com as planilhas depois da implantação: **planilha só conferência**, sistema é a fonte da verdade.

## 3. Riscos acompanhados

| # | Risco | Mitigação |
|---|---|---|
| K2 | RETO e RJ em Itu legados entram sem origem → rastreio por bitola só para material novo | Inventário físico + "Atribuir origem"; **dono ainda não definido** |
| K3 | Divergência sistema × Mega ("Fazer no Mega" esquecido) | T16 mínima ✅; sync 6h/13h |
| K5 | Digitação dupla no paralelo | Planilha só conferência ✅ |
| K6 | Segredos no repo | Hook bloqueia `git add -A` e leitura de segredos ✅ |
| K7 | Perda de corte | ✅ decidido: até 6 % do material usado |
| K8 | Custo/lentidão dos chats (FRONTEND) | Regras de leitura enxuta no README; PEDIDOS arquivado |

## 4. Go/no-go

1. Carga conferida pelo Fabiano: ✅ números (Estoque Mega = Mega ± 5 kg; RJ = ESTOQUE 2026); paridade conferida.
2. Os 5 caminhos ponta a ponta OK sobre a carga final ✅ (2026-11-17).
3. Concorrência OK no PostgreSQL ✅.
4. Backup + restauração ✅ local; **cópia externa pendente** (bucket + PARs na OCI, Eduardo).
5. Os 4 usuários fizeram o aceite.
6. Estorno/ajuste (T18) funcionando ✅.

1, 2 ou 6 falhando → não implanta.

## 5. Pendências do Eduardo

1. P32 (`../carga/perguntas_eduardo_2026-11-12c.txt`) e conferência do relatório de paridade com o Fabiano (`../carga/perguntas_fabiano_2026-11-12.txt`).
2. ~~Perda de corte~~ (6 %, feito).
3. Criar os 4 usuários reais.
4. Backup externo: bucket + 2 PARs na OCI (`docs/tecnico/05_backup_externo.md` §2, ≈ 15 min).
5. Dono do inventário de RETO / RJ em Itu.

## 6. Rodadas

- **R11 (19/11):** layout A "Bancada" escolhido pelo Eduardo entre 3 protótipos (`../layouts/`) e aplicado pela COORDENAÇÃO direto no frontend (tema, menu pelo caminho do material com contadores, Painel em lista de tarefas, Cadastro de SA com ação na coluna do dado). Spec v3.17 §4, `docs/ux/02_tema_visual.md`. Sem mudança de regra nem de API.
- **R10 (18/11):** revisão de código completa (4 revisores + análise estática, achados conferidos): travas antes de validar, disponível ≥ 0, N+1 do painel, índice 0011, frontend (corridas, erros, janelas, formatação). Detalhe em `00_RETOMAR_COORDENACAO.md` §3.
- **R9 (18/11):** ajustes do teste manual de 18/11 feitos pela COORDENAÇÃO direto (sessão sem os subagentes): spec v3.16, contrato §4/§7, backend (trava da NF por SA confirmado + R$/kg, `PRECIFICADOR_PENDENTE`, precificador no item do COP), testes (`test_v316_precificador_nf.py`), T14 por COP, T11 com precificador, largura toda e menu recolhível.
- **R8 (17–18/11):** ajustes do teste manual (DECISOES 2026-11-17), spec v3.14–v3.15, unificação de "Pedir corte", vários lotes na OP, deploy esperando sequência de commits (não estava travado). Documento de retomada `00_RETOMAR_COORDENACAO.md` e histórico exportado em `../historico_claude/`.
- **R7 (17/11):** respostas dos usuários de 17/11; spec v3.11–v3.13; menu renomeado; bloqueio do peso real; regra do RETO; recarga do zero conferida; ponta a ponta 5/5; ferramenta "Confirmar SA (teste)" (só fora de produção; desligar na implantação, `06_implantacao.md` §2.3).
- **R6 (06–12/11, auditoria + respostas):** P19–P31 respondidas e registradas em DECISOES; spec v3.5–v3.10; TÉCNICO R044–R049, R053, R055 (500 da T04); FRONTEND R041–R052 conferido na homologação; BANCO E TESTES R042, R048, e2e preparado. Git autentica pelo `gh` (credential helper local do repo).
- **R5 (06/11, auditoria):** spec v3.4 commitada (`4b383d6`); pedidos R040 (TÉCNICO), R041 (FRONTEND), R042 (BANCO E TESTES). TÉCNICO corrigindo carga/bug (em andamento). Depende do Eduardo: P19–P25 e perguntas ao Fabiano (`../carga/texto_fabiano_auditoria_2026-11-06.md`).

- **R1 (03/11):** T25, T11–T13, Parte B. Voltou toda feita.
- **R2 (04/11):** painel, T16 mínima, exportações, avisos, T04–T06/T17/T18/T23, impressão T09, roteiro de implantação, backup externo. Voltou feita, **exceto FUNCIONAL** (spec ainda na v3.1, ESTADO_FUNCIONAL sem atualização).
- **R3 (04/11):** R036 corrigido, spec v3.3, BLOCO 1 respondido pelo Fabiano, perda de corte = 6 %. Faltou o FRONTEND (T05 estornável).
- **R4a:** TÉCNICO recarga R038 + PERDA_CORTE_MAX_PCT; FRONTEND T05 estornável + T13 perda em %. **R4b** (depois da recarga): FUNCIONAL confere kardex/prévia; BANCO E TESTES ponta a ponta.

- **Migração para o Claude Code (2026-11-05):** rascunho em `projeto-controle_mp\migracao_claude_code\` (CLAUDE.md raiz/backend/frontend, 4 subagentes, /rodada, /estado, hook, settings, .mcp.json, script `aplicar_migracao.ps1`, `LEIA-ME_MIGRACAO.md`). Aplicada (commit 75c085e).
- **Handoff dos 4 chats feito (2026-11-05):** instruções permanentes de cada frente incorporadas no rascunho (CLAUDE.md raiz/backend/frontend, agentes funcional/tecnico/banco-testes, hook bloqueia também leitura de ../segredos/). Repo limpo (só frontend/tsconfig.tsbuildinfo, que vai para o .gitignore). Migração aplicada. Falta: remover as seções 'Instruções permanentes' dos ESTADO_* (duplicam os CLAUDE.md).
