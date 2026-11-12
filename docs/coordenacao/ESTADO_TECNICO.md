# Estado — BACKEND / TÉCNICO

Atualizado: 2026-11-12 pelo TÉCNICO: R055 (500 da T04) corrigido e conferido na homologação (`d339372`); P31; R053 (1)–(5); R054(3) respondido (Mega não traz peso do SA). Recarga só com o ok do Eduardo e do Fabiano no relatório `paridade_rj_itu_previa_20261112_0904.xlsx`.

> Para retomar a parte técnica do zero: `estoqueack/docs/tecnico/00_RETOMAR_PROJETO.md` (inventário, onde fica cada segredo, operação, lições e incidentes; §7.2 e §7.3 = Fase 1).

## 1. Resumo

- **Fase 1 em desenvolvimento**, liberada pelo R022 (especificação v3). Sem data fixa (regra 7 do README): vale a ordem de `ESTADO_COORDENACAO.md` §1.
- **Na homologação** (https://estoque.acokorte.com.br, só IPs da empresa): o fluxo completo da Fase 1 está na API (T06 a T14, T17, T18, T23, notificações) e a integração com o Mega está fechada (OP, cliente, SA, estrutura, preço médio e sincronização 06h/13h).
- **CI verde de novo** (R029 resolvido pelo BANCO E TESTES no `3f2b1ca`, publicado sozinho às 15h55). Homologação no commit `3f2b1ca`, 103 testes.
- **T25 carga inicial NO AR na homologação (2026-11-03 17h33)** com as planilhas de 03/11 (`planilhas\2026-11-03\`) e o saldo do Mega das 17h02. Re-executável (rodou 2 vezes seguidas com o mesmo resultado). Conferência: (a) Estoque Mega = saldo Mega em **todos** os códigos; (b) RJ no Rio **239.066,5 kg** = ESTOQUE 2026; (c) RJ em Itu **28.441,8 kg** = Estoque Geral; (d) 790 de 810 solicitações, 741 de 795 cortes, 45 de 45 COPs, 8.293 de 8.293 SAs (o que ficou de fora está nas pendências). Relatórios em `Documents\projeto-controle_mp\carga\relatorios\` (prévia `carga_previa_20261103_2031.xlsx`, resultado `carga_resultado_20261103_2032.xlsx`). **R032 aberto para o FUNCIONAL revisar a prévia com o Fabiano.**
- **Rodada 2 (2026-11-04, commit `7b60e7f`, 121 testes):** API do **painel T03** com pendências por perfil, **T16 conciliação mínima** (só leitura), **avisos automáticos do sino** no agendador e **exportações Excel** (estoque, solicitações, SA). Contrato §11–§14 e pedido **R035** para o FRONTEND.
- **Comigo daqui para frente:** recarregar a T25 quando o Fabiano devolver as correções do R032 (avisar antes no R033); campos da impressão da Fila RJ se o FUNCIONAL pedir; na implantação, a carga final (roteiro do BANCO E TESTES, em `deploy/implantacao/`). PDFs de romaneio e ficha do lote ficaram para a F1.1.

## 2. Feito

### Paridade RJ × Itu por liga × bitola (R049, P28 do Eduardo, 2026-11-11)

- **Carga:** lote RJ (no Rio e em Itu) **sem código do Mega**, item próprio por liga real + formato + seção + comprimento + múltiplo (`medidas.chave_material`; 1.2344 = H13 e 1.2379 = D2 na mesma linha; MOD diferente). Linha do Estoque Geral sem código não vira item. Restrição das colunas RJ vai só para lote RJ do mesmo material. RETO criado de lote RJ (T13) e entrada NF (T06) usam item sem código.
- **P29 + P31 e Estoque Geral "10nov"** (2026-11-12 08h31): `carga\relatorios\paridade_rj_itu_previa_20261112_0831.xlsx` (abas "Paridade RJ x Itu", "Comprimento do HISTORICO" e "Correções aplicadas"; correções de `carga\correcoes_carga.json`). Comprimento só do HISTORICO entra na chave só quando a linha de Itu também tem comprimento (P31): das 93 linhas, 1 usada (CH39SH), 45 com Itu sem comprimento e 47 com vários comprimentos ficam só como nota do lote. RJ no Rio 183 materiais / 236.172 kg: mesma linha 62 (61 iguais + 1 liga equivalente, 62.181 kg); só no RJ 121 (27 bitola igual/liga diferente, 4 comprimento diferente, 9 liga igual/bitola diferente, 81 sem nada parecido). RJ em Itu 30 linhas / 27.743,8 kg: 18 mesma linha. CH39SH D2 Ø90 → Ø90X2425 = 95199: ESTOQUE 2026 peso inicial 2.187 e total 1.944 kg; HISTORICO 1.459 + 728 = 2.187 kg; 95199 com 0 kg Mega e 1.944 kg "RJ no Rio" na planilha. Leitor aceita "×" e faixa de comprimento.
- **2026-11-12 (`a2740a6`, `d339372`, CI verde, no ar; 178 testes + 5 skip local):** R055 corrigido (item do Mega sem bitola derrubava a chave → "<liga> SEM BITOLA"; homologação: Todos 618 lotes, Estoque Mega 412, busca=4140 18, sem erro). R053: (1)/(2) equivalência sem MOD da T22 = mesma liga (`estoque.mapa_mesma_linha`; na homologação só 1.2344/H13 e 1.2379/D2), (3) NF com comprimento em item próprio, (4) `CORRECAO_NAO_APLICADA` BLOQUEIA a gravação, (5) savepoint na pendência ENTRADA (0008 não editada). Relatório refeito com a P31 e `correcoes_carga.json` (planilhas 11/11): `paridade_rj_itu_previa_20261112_0904.xlsx`, números iguais aos do `_0831`. R054(3): Mega não traz peso do SA (PC). **Próximo:** R054 (2) depois da P32, R051/R052; recarga só com o ok.
- **Relatório de paridade** (antes da P29, só para registro): `carga\relatorios\paridade_rj_itu_previa_20261111_1609.xlsx`. RJ no Rio 183 materiais / 236.172,0 kg: mesma linha 61 (60 iguais + 1 liga equivalente, 60.237 kg); só no RJ 122 (27 bitola igual/liga diferente, 5 comprimento diferente, 9 liga igual/bitola diferente, 81 sem nada parecido). RJ em Itu 30 linhas / 27.743,8 kg: 18 mesma linha, 12 só no RJ. 62 materiais com diferença ESTOQUE 2026 × "RJ no Rio" do Geral > 5 kg. CH39SH D2 Ø90 (1.944 kg) fica sem código e em linha diferente do 95199 (D2 RED 90X2425: comprimento). **Recarga só depois do ok do Eduardo e do Fabiano.**
- **API:** T04 agrupado por `chave` com `codigos_itu`; sugestão T07 pela mesma chave (equivalente no mesmo grupo, com selo por lote); `codigo_mega` só no Estoque Mega (filtro e resposta). Pedido R050 ao FRONTEND.

### Spec v3.5/v3.6 (R045, R047) e R044, migração 0008 (2026-11-11)

- **T13 tolerância por origem (P22(a)):** lote fiscal RJ em Itu (peça inteira recebida, sobra, RETO) usa `TOLERANCIA_EXCESSO_RJ_INTEIRO_PCT` = 8 %; Estoque Mega 5 %; mensagem "Limite: 8 % para material do RJ"; `resultado.tolerancia_excesso_pct`. Redondo igual. Sem SA complementar na peça inteira (P26 2b): o código já ligava o 1º corte ao SA do COP.
- **T10 peça inteira:** `BARRA_MAIS_LEVE_QUE_PECA` (ALERTA) se a barra pesa menos que o previsto da peça (P26 2a).
- **P24:** CR8MOD é liga distinta (leitor de medidas); `SA_JANELA_ANTES_DIAS` = 7 na T23 (antes fixo).
- **T07 sugestão agrupada:** `GET /api/lotes/compativeis` ganha `grupos` (liga × bitola exatas × múltiplo; `ITU` e `RJ_NO_RIO` lado a lado; necessário × disponível) e `peso_necessario_kg`.
- **Consumo misto (P26 opção A):** `consumo_misto` na solicitação e no corte em Itu; sem `OP_DUPLICADA` entre partes marcadas; marca `consumo_misto {itu_kg, rj_kg, texto}` na T08 e no Excel.
- **Carga:** RETO do RJ em Itu sem lote-pai por candidato único (pendência `RETO_ORIGEM_SO_BITOLA`); Estoque Geral com nome variável (`Materia Prima Geral*.xlsx`, um só na pasta). Já estavam certos: D6 97X2660/101X2260 = chapa, CH39SH D2 Ø90 → 95199, 1.2767 RETO sem origem.
- **R044 (0008):** índice único parcial `uq_pend_entrada_aberta`, CHECK `ck_pend_situacao`/`ck_pend_motivo`; reabrir com outra ABERTA do código soma nela; bitola de origem normalizada na aba RETO por origem.
- Dry-run local (planilhas de 03/11, sem Mega): RETO do RJ em Itu 14 lotes, 10.836,8 kg; com pai 6 → 0, sem pai 8 → 14. CH39SH D2 Ø90 → 95199 pela paridade atual. Testes novos em `tests/test_v35_r045.py`.
- Dry-run com `planilhas/2026-11-11/` (Estoque Geral de 11/11, ainda com o nome "20out"): RETO RJ em Itu 8 lotes, 10.144,8 kg, todos sem pai. **Diferenças na planilha:** o DC53 RETO (linha 347) **ainda** tem a parcela "IMP-D2 36X510MM" (182 kg); o D2 RETO (linha 281) caiu para 948 kg mas o comentário soma 1.027 kg → entra como um lote só sem origem (pendência `RETO_PARCELAS_MAIORES_QUE_SALDO`); o 1.2767 RETO (linha 525) está com 0 e o 1.2746 RETO (linha 526) tem 1.594 kg. Solicitações 796 → 829 (31 ativas), SAs 8.336.
- **Recarga suspensa** (Eduardo, 11/11): a paridade RJ × Itu passa a ser só liga + bitola exatas, sem código Mega no material do RJ; a FUNCIONAL reespecifica. Hoje o código ainda liga material RJ a código Mega na carga (`plano._paridade`/`_item_rj`); não mexi.

### Auditoria de 06/11, parte 2 (T15 mínima, RETO por origem, P10; migração 0007)

- **T15** (`services/entradas_mega.py`, `api/routes/entradas_mega.py`): pendência por código atualizada ao fim de cada sincronização; criar-lote (prévia + gravação), "Não é entrada", reabrir (Admin). Migração **0007** (colunas em `pendencia_mega` e `item_mp.criado_pela_t15`), **para o BANCO E TESTES revisar (R042)**. Código novo só gera pendência com entrada (ED) nos últimos 120 dias no Mega (escolha minha, avisada no R040). T16 mínima mostra `explicada_na_t15`; Painel tem o contador.
- **RETO por origem**: `estoque.lote_infos` (monta `LoteInfo` do banco), `domain.lotes.origem_do_reto` (3 classes), `GET /api/lotes/reto-por-origem` e Excel de 2 abas.
- **P10**: `painel/resumo` e `painel/pendencias`, árvore do T05 e T14 (lista, detalhe, Excel) não mostram Itu ao Marcelo.
- Contrato §15, §16, §16.1. Testes novos em `tests/test_t15_reto_origem_p10.py`. Não mexi no §9.1 nem recarreguei a homologação.

### Correção da auditoria de 06/11 (commit `591d583`; NÃO publicado: push negado; CI e prévia no servidor pendentes)

- **RETO do RJ em Itu:** entra como tipo RETO e em sub-lotes pelas parcelas do comentário da célula ("381kg de sobra (MEDIDA ORIGINAL IMP-D2 25X610MM)"); o resto do saldo vira um lote "sem origem"; soma = saldo da célula. Dry-run local (planilhas de 03/11, sem Mega): 6 linhas RETO = 14 lotes, 10.836,8 kg. D2 = 6 parcelas + 73 kg sem origem; DC53 = 2 parcelas + 680 kg; A8, D6, H13 e 1.2767 = 1 lote cada (sem comentário; o 1.2767 é fórmula de 6 parcelas sem bitola).
- **Decisão de modelo (sem migração):** a medida de origem fica em `lote.origem_ref["bitola_origem"]` e na nota do lote. Havendo **um só** lote ORIGINAL com a mesma liga e bitola no cadastro, o sub-lote ganha `lote_pai_id` e `origem_identificada=true` (hoje 5 do D2 e 1 do DC53); zero ou vários candidatos, ou medida em faixa ("45x510~610"), fica sem pai. A parcela D2 36X510 dentro do DC53 RETO está registrada como veio (pendência REVISAR `RETO_ORIGEM_DE_OUTRA_LIGA`, pergunta ao Fabiano).
- **`reto_por_origem`** (domínio) agora agrupa também o RETO sem pai pela `bitola_origem`. Falta o serviço que monta `LoteInfo` do banco (R040 item 2), não feito por ordem da coordenação.
- **Leitor de medidas:** Ø/RED/ROUND + N×M = redondo de diâmetro N e comprimento M. Dry-run local: lotes esgotados do HISTORICO 493 → 346; ativos sem data de entrada 31 → 13; solicitações importadas 790 → 796 (+6). Restam 4 linhas D6 (97X2660, 101X2260…) que parecem redondos sem marcador; perguntar ao Fabiano.
- **Solicitação parcial travada:** em Material insuficiente com corte, "Encerrar com saldo pendente" passa a valer (leva a Cortada) e os cortes já feitos entram no COP. Trocar lote e Cancelar seguem bloqueados com corte. Pedido R043 ao FRONTEND.
- Testes novos (solicitação, medidas/lotes, carga); suíte local verde (SQLite), ruff limpo. Recarga na homologação não feita.

### Rodada 4a (2026-11-04)

- **R024:** `PERDA_CORTE_MAX_PCT` = 6 % do material usado (migração **0006**, que também abre a densidade da liga para 1–25 g/cm³); prévia do T13 com perda em kg e %. Aviso ao FRONTEND no R039.
- **R038, recarga 19h54** com a revisão do Fabiano (§10.7): paridade sem múltiplo e "só no RJ", kardex de 2 anos (196 códigos entraram, 114 fora), densidades revistas, CPR fora, 4 solicitações concluídas e 8 canceladas (6 na Fila RJ). Conferência (a)–(d) OK. Lista do kardex e relatórios em `carga\relatorios\`.

### Rodada 3 (2026-11-04)

- **R036 corrigido** (`075f975`, `330eaab`): saldo inicial da carga datado antes do 1º consumo; `estornavel`/`da_carga` nos movimentos e movimento da carga não estornável (corrige-se por ajuste no T18); SAs confirmados do mais novo; NF da planilha de SA no SA e no item do COP. **Recarga da homologação 04/11 08h31** (mesmas planilhas de 03/11): 0 saldos acumulados negativos, 0 movimentos da carga estornáveis, 403/448 itens de COP com NF, T16 com 403 códigos OK. R034 respondido (divisão do roteiro de implantação de acordo).

### Fase 1, API (BACKEND 2, 2026-11-03)

| Commit | O quê |
|---|---|
| `c605fde` | Migração **0003** (modelo §11 inteiro). T07 a T10: solicitação com peso previsto pela bitola + sobremetal, reserva, rascunho, cancelar, trocar lote, encerrar com saldo pendente, trocar OP, duplicar; fila RJ; corte RJ com "Usar outro lote / dividir". Lotes compatíveis com liga equivalente. Operação RJ vê só RJ no Rio. Sino de notificações |
| `98d0b93` | T11 COP (fechar gera SAs, reabrir, NF por COP ou por item, enviar); T14 SA (código sugerido, `SA_CODIGO_TROCADO`, confirmação no Mega, NF do B2); T12 recebimento (divergência, peça inteira vira lote RJ em Itu) |
| `e9fe723` | T13 corte em Itu (consumo, perda, RETO, instrução "Fazer no Mega", SA do B2, conclui peça inteira); T06 entrada por NF; T17 reservas; T18 ajuste e estorno; atribuir origem; T23 parâmetros |
| `19d3b87` | Contrato da API da Fase 1: `estoqueack/docs/api/02_contrato_fase1.md` (R025) |

Situação da solicitação é **derivada** dos fatos (`fluxo.recalcular_solicitacao`); todo movimento passa por `movimentos.lancar` (saldo nunca negativo); prévia `/validar` + gravação com `confirmacoes` (409 com a prévia; 400 = ação impossível no estado).

### Mega e sincronização (BANCO E TESTES, 2026-11-03, detalhes em `ESTADO_BANCO.md`)

- `ded65ac`, `2a5f11e`, `64039f6`: cliente e pedido da OP (79/79 batem com a planilha); situações da OP (EN/CA bloqueiam; FP/LB/PL/SI só avisam, `OP_NAO_ABERTA`, confirmado no R026); confirmação do SA pela entrada na filial 13/3 em peças; SA inativo (`SA_INATIVO_MEGA`) e inexistente (`SA_NAO_ENCONTRADO_MEGA`); NCM/IPI do Mega; estrutura da OP e sugestão de SA pela estrutura.
- `7852704`: preço médio (bate exato com o relatório C.M.D.); sincronização com migração **0004**, agendador por cron (06h/13h + verificação de SA a cada 30 min), `POST /api/mega/sincronizar` e `GET /api/mega/sincronizacoes`. 1ª carga de 107.840 movimentos; incremental em 4 s. A sincronização das 13h de 03/11 rodou sozinha.
- **GRANTs restritos aplicados pelo Eduardo (DBA) em 03/11:** o `estoqueack_ro` só tem `CREATE SESSION` e SELECT em 9 objetos. Conferido depois: tudo funciona; o resto dá ORA-00942. Para mapear algo novo no Mega é preciso liberar o objeto de novo.
- Testes: **102** automáticos (no último commit verde).

### Base (até 2026-10-30)

- **Login e usuários:** Argon2id, sessão em cookie, CSRF, bloqueio por tentativas, "Manter conectado", login `nome.sobrenome`, senha mínima de 6 caracteres e troca obrigatória com senha temporária, recuperação de senha por e-mail.
- **E-mail pelo Microsoft Graph:** remetente `estoque.smtp@acokorte.com.br`, app do Entra restrito a essa caixa (guia `docs/tecnico/02_email_graph.md`). Testado pelo site em 30/10. **O segredo vence em 2028-10-29.**
- **Infra no system-lab:**
  - **Containers:** db, api e web, atrás do nginx do host (HTTPS Let's Encrypt até 2027-01-27, renovação automática), acesso só pelos IPs da empresa (`ips-estoqueack.conf`, inclui Barra Mansa).
  - **Deploy automático:** cron a cada 5 min, só publica com CI verde, faz backup antes e rollback se o teste falhar.
  - **Backup diário criptografado:** 02h15, retenção de 30 dias + mensal, teste de restauração aos domingos.
- **CI:** gitleaks, backend (lint, migrações no PostgreSQL e pytest), frontend e build ARM64.

### T25 carga inicial (TÉCNICO, 2026-11-03)

- Código `backend/app/carga/` (commits `8f153ac`, `f63dda8`, `cbe43d5`), 3 testes com planilhas sintéticas. Como rodar e o que vira o quê: `estoqueack/docs/tecnico/04_carga_inicial.md`.
- **Estrutura das planilhas de 03/11 conferida com as de 28/10:** mesmas abas e cabeçalhos; só mais linhas (SA 2025 +22, Corte +6) e mais comentários (ESTOQUE 2026 508→528). Se mudar, a carga para (código 2) em vez de se adaptar.
- **Na homologação:** 1.137 lotes (704 RJ no Rio, sendo 494 esgotados do HISTORICO só para consulta; 30 RJ em Itu; 403 Estoque Mega), 1.181 itens, 2.144 movimentos, 790 solicitações (7 Enviadas na Fila RJ, 7 Material insuficiente, 4 Cortadas, 768 Concluídas, 4 Canceladas), 741 cortes, 45 COPs, 8.293 SAs, 30 ligas novas, 605 pendências.
- As planilhas ficam **fora do repositório**: `~/estoqueack-carga/` no servidor (700/600) e `Documents\projeto-controle_mp\planilhas\` no PC.

## 3. Falta (na ordem)

1. ~~T25 Carga inicial~~ **feita na homologação em 03/11** (ver §2). Falta: revisão da prévia pelo Fabiano (R032) e, se ele corrigir as planilhas, rodar de novo; no **dia da implantação**, a carga final com as planilhas congeladas + saldo do Mega do dia (`docs/tecnico/04_carga_inicial.md` §1).
2. ~~T03 Painel com pendências~~ **feito em 04/11** (`GET /api/painel/pendencias`, contrato §11).
3. ~~T16 Conciliação mínima~~ **feita em 04/11** (`GET /api/conciliacao`, só leitura, contrato §12; decisão do Eduardo de 04/11).
4. ~~Avisos automáticos do sino~~ **feitos em 04/11** (agendador a cada 5 min, uma vez por documento, contrato §14).
5. ~~Exportações Excel~~ **feitas em 04/11** (`/api/exportar/…`, contrato §13). "Exportar SAs novos para o Renato" com marca fica para a F1.1.
6. **Impressão da Fila RJ (T09, entra na F1):** a tela usa `GET /api/fila-rj`; acrescento campos se o FUNCIONAL pedir.
7. **Com o chat BANCO E TESTES (não é comigo):** roteiro de implantação, backup fora do servidor, testes da T16, E2E de 11/11 e aceite de 12/11.
8. **Depois da implantação (F1.1):** T15 Entradas Mega a classificar, tratamento da T16, T19 Relatórios, T26 Material a chegar, exportação para o Renato com marca, equivalência de ligas na T22, PDFs (romaneio do COP e ficha do lote).
9. **Monitoramento:** alerta por e-mail de site fora do ar, backup com falha e deploy recusado.

## 4. Depende dos outros

| De quem | O quê | Onde |
|---|---|---|
| **FUNCIONAL + Eduardo/Matheus** | Responder o R024. O FUNCIONAL já aceita 4 dos 5 pontos; **falta o Eduardo/Matheus dizer quantos kg de perda são normais num corte em Itu** (perda de corte (R008 "50 % acima da esperada" × exemplo de 5 kg no §2.2), campo "peso do material usado" no T13, instrução do Mega com a perda, códigos novos (`LIGA_DIFERENTE`, `LOTE_TROCADO` etc.) e "Encerrar com saldo pendente" como Cortada | `PEDIDOS.md` R024 |
| **FRONTEND** | Telas que faltam sobre a API pronta (R025), na ordem dele: T11 e T12 → T13 → T04, T05, T06, T17, T18, T23 → painel com pendências (espera a minha API). Já feitas: T03 (barra + sync), T07, T08, T09, T10, T14 e sino. Sem lotes na homologação, as telas foram testadas com respostas simuladas: o teste real depende da carga T25 | `ESTADO_FRONTEND.md` |
| **BANCO E TESTES** | Avisos de NF e IPI no T14 (R026) e Partes B e C (item 5 acima) | `ESTADO_BANCO.md` |
| **Eduardo** | Avisar o Fabiano do IPI do NCM 82089000 (5,2 % no Mega × 0,08 na planilha de SA) | `ESTADO_FUNCIONAL.md` |
| **Eduardo** | Criar os usuários reais (Fabiano, Matheus, Marcelo, Renato) e validar o acesso do RJ | — |
| **Eduardo** | Confirmar com o FUNCIONAL: prioridade F1 × F1.1 (o TÉCNICO seguiu a proposta), paralelo das planilhas até 27/11 e valores iniciais dos parâmetros do R008 | `ESTADO_FUNCIONAL.md` |
| **Eduardo** | Destino da cópia do backup **fora do servidor** (sugestão: Object Storage da OCI) | — |
| **Eduardo** | Guardar a senha GPG do backup no cofre e apagar `~/.estoqueack_admin_inicial` depois do 1º acesso | — |
| **Eduardo** | Pedir ao suporte do GitHub a remoção do cache dos commits antigos (incidente de 29/10); decidir se o repositório fica privado | §6 |
| **Eduardo** | Mais para frente: trocar o segredo do Graph (o valor passou pelo chat) e rotacionar a senha do backup | — |

## 5. Pedidos em aberto que envolvem o TÉCNICO

| ID | De → Para | Assunto | Situação |
|---|---|---|---|
| R029 | FRONTEND → TÉCNICO | CI do backend vermelho | FECHADO (corrigido no `3f2b1ca`) |
| R030 | BANCO E TESTES → TÉCNICO | Regras de saldo/concorrência e migração 0005 | FECHADO em 04/11 (ciente; a carga só insere movimentos) |
| R032 | TÉCNICO → FUNCIONAL | Revisar a prévia da carga com o Fabiano | ABERTO (marco 09/11) |
| R033 | TÉCNICO → FRONTEND, BANCO E TESTES | Homologação com dados reais; a carga apaga e recria | ABERTO (aviso antes de cada recarga) |
| R044, R045, R047 | BANCO E TESTES / FUNCIONAL → TÉCNICO | Revisão da 0007; spec v3.5/v3.6 | RESPONDIDOS em 11/11 (0008) |
| R048 | TÉCNICO → BANCO E TESTES | Revisar a migração 0008 | ABERTO |
| (novo) | FUNCIONAL → TÉCNICO | Paridade RJ × Itu só por liga + bitola, sem código Mega no RJ: ajustar carga e sugestão, relatório de paridade antes da recarga | AGUARDANDO a especificação |
| R035 | TÉCNICO → FRONTEND | APIs do painel, T16, exportações e avisos | ABERTO |
| R024 | TÉCNICO → FUNCIONAL | Decisões de código para confirmar na especificação | ABERTO (aguarda a perda de corte do Eduardo/Matheus) |
| R025 | TÉCNICO → FRONTEND | APIs da Fase 1 no ar; telas em andamento | ABERTO (em andamento) |
| R013 | TÉCNICO → todos | Aviso de segurança do `git add -A` | ABERTO (só aviso; pode fechar) |
| R018 | FUNCIONAL → TÉCNICO | Regras do Matheus | FECHADO (atendido no código) |

## 6. Segurança e incidentes

- **Incidente de 29/10:** a senha GPG do backup foi publicada no GitHub público por um `git add -A`. Histórico limpo em 30/10, gitleaks no CI. Falta o suporte do GitHub limpar o cache dos commits antigos. O Eduardo decidiu não rotacionar a senha por ora.
- **Regra para todos os chats:** nunca `git add -A`; commit só de arquivos explícitos. Neste ambiente, fazer commit e push **pelo Windows**, porque o git no sandbox deixa `.git\index.lock` preso.
- **Repositório:** ainda **público**. O `.github_token` tem permissão de administrador; o ideal é trocar por um só com Contents e Workflows.

## 7. Referência rápida (system-lab)

- **Pasta e containers:** `~/apps/estoqueack`, com `docker compose ps` e `docker compose logs --tail 100 api`.
- **Logs:**
  - deploy: `~/.local/state/estoqueack-deploy.log`
  - backup: `~/.local/state/estoqueack-backup.log`
  - agendador do Mega: `~/.local/state/estoqueack-agendador.log`
- **Acesso:** uma sessão SSH só, pelo Desktop Commander (o Snort do pfSense bloqueia várias conexões seguidas). Na sessão, use `git --no-pager`.
- **Mega:** só a partir do system-lab, com Instant Client 19 em modo thick, somente leitura (`estoqueack_ro`).
- **Testes "de fora":** o sandbox do Claude sai com o IP do Eduardo (201.91.252.202). Para testar como alguém de fora, use o IP público do system-lab.

## 8. Em andamento / não commitado (2026-11-05, migração para o Claude Code)

- **Nada do TÉCNICO fica sem commit:** tudo está na `main` até `41d492f` (código) e publicado na homologação. O único arquivo solto na pasta é `frontend/tsconfig.tsbuildinfo`, que é artefato de build do FRONTEND (não versionar).
- **Fora do Git, de propósito:** planilhas (`projeto-controle_mp\planilhas\<data>\` no PC; `~/estoqueack-carga/planilhas/` no system-lab, 700/600), relatórios da carga (`projeto-controle_mp\carga\relatorios\` e `~/estoqueack-carga/relatorios/`) e a pasta `coordenacao\`.
- **Homologação carregada** em 2026-11-04 19h54 com a revisão do Fabiano (R038). Próxima recarga só quando houver novas correções (avisar antes no R033) e, no dia da implantação, a carga final pelo roteiro do BANCO E TESTES.
- **Aguardando:** FUNCIONAL conferir os 59 códigos `NAO-INFORMADA` do kardex (R038); FRONTEND ajustar a T13 ao formato novo da perda (R039).

## 9. Instruções permanentes desta frente

Regras, armadilhas e preferências do Eduardo que o TÉCNICO segue e que não estão em documento do repositório:

1. **Executar no servidor eu mesmo** (system-lab). Só mandar bloco para o Eduardo colar quando depender de algo que eu não alcanço (portal M365/Entra, PowerShell do Exchange com login admin, DBA do Oracle). Antes de mexer no `.env`: `cp -p .env .env.bak.<data>`; depois, conferir `/api/saude`.
2. **Uma sessão SSH só** (`ssh -tt -o ServerAliveInterval=30 system-lab` pelo Desktop Commander, `cmd.exe`) e reaproveitar. O Snort do pfSense bloqueia conexões seguidas. Se a sessão travar, conferir pelo site (`curl --resolve estoque.acokorte.com.br:443:204.216.137.171 …`) antes de abrir outra. Usar `git --no-pager` na sessão.
3. **Erro: parar e explicar**, não repetir o mesmo comando. GitHub fora do ar (500/"cannot lock ref"): fazer `git fetch` e tentar de novo depois, sem forçar.
4. **Git:** nunca `git add -A`/`.`; só arquivos explícitos e conferir `git status --short --untracked-files=all`. Outros chats trabalham **na mesma pasta**: arquivos modificados que não são meus ficam de fora; se um arquivo meu tiver mudança de outro chat, commitar só o meu trecho (`git apply --cached <patch>`). Commit e push **pelo Windows** (PowerShell, com o `.github_token` no header), porque o git no sandbox deixa `.git\index.lock` preso. Testes, ruff e gitleaks podem rodar no sandbox (`/tmp/venv`).
5. **Respostas curtas** quando a COORDENAÇÃO pedir (até 5 linhas); **sem prazo fixo** ("dia da implantação", nunca "até DD/MM"); datas absolutas na coordenação.
6. **Planilhas e dados da empresa nunca no repositório** (é público): nem planilhas, nem relatórios da carga, nem OPs/clientes em testes além de exemplos fictícios. Segredos nunca dentro de `estoqueack\`; o valor de um segredo não vai para o chat (preferir `read -rsp` no servidor).
7. **Mudança de esquema = migração nova** (a próxima é a 0007); nunca editar migração já aplicada. Código que mexe em saldo: `lote_ou_404(travar=True)` + `movimentos.lancar`; a carga é a única exceção (roda sozinha após o TRUNCATE e só insere movimentos).
8. **Contrato antes do código** quando o FRONTEND depende (`docs/api/02_contrato_fase1.md`) e avisar no PEDIDOS se o formato de resposta mudar. Regra de negócio só depois de estar na especificação; decisão de interpretação vai para o FUNCIONAL confirmar.
9. **Conferir com dado real** antes de dizer que está pronto: depois de cada deploy/carga, rodar a verificação no servidor (saldos, conciliação, estornáveis) e mostrar números.
10. **Recarga da T25** sempre com backup antes (`deploy/backup/backup.sh`) e aviso no R033; planilhas por `scp` para `~/estoqueack-carga/`, `docker cp` para `/tmp/carga` no container, relatório de volta por `docker cp` + `scp` para `carga\relatorios\`.
