# Estado — FRONTEND / UX

Atualizado: 2026-11-19 (layout A "Bancada" aplicado em todas as telas)

## 2026-11-19 Layout A "Bancada" (Eduardo escolheu entre 3 protótipos)

- **Tema** (`styles/tema.css`, `app.css`, `docs/ux/02_tema_visual.md`): IBM Plex Sans/Mono (`@fontsource`, saíram Raleway/Open Sans); bancada clara; botões com borda (`.link` virou botão pequeno com contorno; novos `.fantasma`, `.pequeno`, `.falta`, `.valor`); `.etiqueta` = pílula com ícone por máscara CSS; `.chips[role=group]` = controle segmentado; `details.avancado` com contorno e seta; 44 px no computador, 48 px em toque; tabelas com cabeçalho cinza e números em mono.
- **Casca** (`components/Layout.tsx`, `Icone.tsx`): menu claro pelo caminho do material (spec v3.17 §4) com ícones e contadores (`api/pendencias.ts`: a leitura de `/painel/pendencias` é compartilhada pelo Painel e pelo menu, renovada a cada 2 min e ao trocar de tela se tiver mais de 1 min; limpa ao sair); "Esconder menu" no rodapé deixa a coluna de ícones; trilha "grupo › item" acima do título; "Pedir corte" no topo; avatar com iniciais.
- **Painel** "Para fazer agora": lista de tarefas por grupo (ícone, itens com link, quantidade, botão com verbo; ALERTA primeiro) + "Saldo por estoque" com barrinhas. **Cadastro de SA:** grupo por COP com pílula (bloqueada/pronta) e barras "SA confirmado x de y" / "R$/kg x de y"; "Falta" tracejado ou valor com lápis na coluna R$/kg; "Informar código" na coluna do SA; "Dados do SA" abre descrição/NCM/ICMS/IPI/pedido; ações em lote numa barra que aparece ao marcar; cartões no celular.
- **Testado:** `tsc` + `build`; navegador interno com API falsa (dados fictícios do contrato, sem login real nem gravação): 1440 px (Painel, SA, menu escondido, barra em lote, Estoque, COPs, sem rolagem lateral) e 375 px (gaveta, SA em cartões, Painel sem estouro). Não testado com dados reais nem pelos usuários.

## 2026-11-17 Balanceamento, ordem da Fila RJ, botões no topo

- **T07 passo 2/3 balanceamento de peças** (DECISOES 2026-11-17): ao marcar/desmarcar lotes, do menor disponível para o maior os menores recebem disponível ÷ previsto por peça (para baixo, mínimo 1 = lote inteiro) e o maior o restante (OP 50 → 1 + 49); campo "Peças deste lote" no quadro do grupo; editar ajusta o de maior disponível ainda não editado (ou o maior dos outros); "Total: X de Y peças" (vermelho acima, amarelo abaixo). Vale para o consumo misto. Saiu o rateio por kg ao passar para o passo 3 (dava 1 + 50). `PECAS_ACIMA_OP` vem da API.
- **T09** ordem padrão "há mais tempo esperando" (`enviada_em`, que a API já devolve; reserva `data`), seletor Ordem (espera / prazo), "há N dias" no cartão; a impressão segue a ordem e diz qual é.
- **Botões no topo:** T07 repete os botões de cada passo logo abaixo dos passos (mesmos estados); no passo 3 de lote em Itu o `LancamentoCorteItu` repete Voltar/Conferir/Confirmar no topo do corte (`botoesNoTopo`). T11 já tinha os botões no cabeçalho; não há outra tela em passos.
- **Testado:** `tsc` + `build`; sem navegador (o Eduardo testa à mão).

## 2026-11-17 Pedidos 2, 3 e 4 do teste manual (commit `2aad997`)

- **No ar:** (2) T09 "Imprimir lista de corte": no papel só a tabela; `@page` margem 0 só enquanto a T09 está aberta (o navegador não põe cabeçalho/rodapé), respiro pelo padding lateral e pelas linhas de cabeça/pé da tabela repetidas em cada página; título de uma linha (data/hora, itens, kg estimados, pesquisa aplicada), `table-layout: fixed` na largura toda, linha não quebra entre páginas, fonte 10,5 pt; imprime o que está na tela (pesquisa aplicada, spec T09). (3) **Peso estimado** (previsto com sobremetal; na parcial, proporcional às peças que faltam) por item e total na impressão, no cartão fechado ("≈ X kg"), no aberto e ao lado da pesquisa. (4) T12: **SA** (código + situação) em cada item do COP; a API já devolvia `itens[].sa`, sem pedido ao TÉCNICO.
- **Testado:** `tsc` + `build`; API real lida (21 na fila, COP 605 com SA 69038 confirmado).

## 2026-11-17 "Pedir corte" como porta única (Eduardo)

- **No ar:** T07 com lote de Itu (Estoque Mega ou RJ em Itu) continua no passo 3 com o lançamento do corte na mesma tela (componente `LancamentoCorteItu`, o mesmo da T13: consumo, sobra, regra do RETO + "Conferi a regra", perda, "Fazer no Mega"); consumo misto: depois de enviar a parte do RJ, a parte de Itu é lançada na mesma tela. "Registrar corte em Itu" saiu do menu; `/corte-itu` continua pelos atalhos (Painel/peso real, recebimento, "Usar em corte em Itu" no detalhe do lote RJ em Itu). Nenhuma mudança de API.

## 2026-11-17 Ajustes do teste manual (Eduardo)

- **No ar:** (1) filtro de liga vai para a API, que filtra por "contém" (RETO por origem separa ligas só por vírgula: "A8 MOD" é uma liga); (2) T07 "Instrução de processo" com várias opções marcadas + texto livre, gravados juntos com "; " (Fila RJ e lista impressa já mostram); (3) `JUSTIFICATIVA_MIN` = 1, sem "faltam N caracteres" (painel e janelas de justificativa; cancelar solicitação segue com 3); (4) T09 pesquisa (OP, cliente, liga, bitola, contêiner, lote) e cartões compactos que abrem ao clicar (link do sino já abre); impressão igual; (5) NF de transferência (COP e T14) com emitente fixo "Fio Certo"; histórico mostra o que veio.
- **Testado:** `tsc` + `build`; sem navegador (o Eduardo testa à mão).

## 2026-11-17 R070 "Confirmar SA (teste)"

- **No ar:** T14 com "Confirmar SA (teste)" (secundário, etiqueta "só homologação") em cada linha não confirmada, só com `modo_teste` true e perfil ADMIN; linha sem código abre janela pedindo o código; resposta atualiza a linha e mostra "confirmado em teste" (`confirmacao_teste`). Faixa discreta "Ambiente de teste" no topo do conteúdo. `modo_teste` lido da sessão (`/auth/eu`/login, no nível da sessão ou do usuário) ou, se ausente, de `/api/saude`; ausente/false = nada aparece.
- **Testado:** `tsc` + `build`; sem navegador (o Eduardo testa à mão).

## 2026-11-17 R064 (commit 260ec5c, bundle `index-r69rhZ8w.js` no site)

- **No ar:** **T13** sobra fora da bitola: "Não, mudou de medida" → placa pede E × L (mm), redondo pergunta "vai para RETO?" (+ Ø se lote novo); depois de "Conferir corte" o quadro mostra a regra e o resultado da API ("Espessura 30 mm (até 50) e largura 180 mm (menor que 200): vai para RETO.") e "Confirmar" só libera com "Conferi a regra do RETO"; fora da regra mostra o lote novo com a medida nova e, no Estoque Mega, "sem transferência; o kg continua no código X"; gravado mostra `lote_sobra`. **T23** unidade mm nos 3 `RETO_*`. **T14** cabeçalho "Fabiano confere e pede; Amanda cadastra no Mega e informa o código", dica por situação (Preparado = "aguardando cadastro do SA (Amanda)"), "SA novo – Amanda cadastra no Mega", "Informar código do SA" também para Análise (P36).
- **Conferido sem gravar (validar real, OP 100957):** L-000770 Estoque Mega 30×180 RETO / 40×200 lote novo / 60×240 RETO; L-000579 RJ em Itu 60×250 lote novo / 40×180 RETO; L-000695 redondo Ø127 → lote novo Ø100; caixa obrigatória nos 6. T23 com os 3 em mm. T14: fila em aberto vazia, linhas vistas com `fetch` simulado. Console sem erro.
- **Próximo:** aguardar a coordenação (perfis da Amanda quando o usuário existir).

## 2026-11-17 Conferência na homologação (recarga de 17/11, API do R058 no ar)

- **Conferido sem gravar** (leitura real; peso real pendente simulado com `window.fetch`, pois a homologação tem 0 peças aguardando): Painel (card, vermelho, "Encerrar pendência" com justificativa, links da T13), T04 (agrupado nos 4 estoques, "mesma linha por exceção" em 3 linhas, RETO por origem com RJ em Itu), T07 com OP real (8 grupos, validar real; faixa vermelha + ERRO `PESO_REAL_PENDENTE` + "Enviar ao RJ" desabilitado; aviso cinza antes do prazo), T09 (21), T11 (47 COPs), T12 (vazia), T13 (peças pendentes, prévia real Estoque Mega/RJ em Itu, tolerância 5 %/8 % simulada), T14 (8.361 no histórico, sem "Corrigir no Mega"), T15, T16, T23 (`PENDENCIA_PESO_REAL_DIAS` = 7). Console sem erro.
- **Corrigido:** T16 mostrava 0 códigos/0 kg (API soma `totais` só das divergentes) → lê tudo e filtra na tela; T07 mandava espessura/largura junto com o diâmetro ao trocar para redondo.
- **Aguardando TÉCNICO (R065):** prazo com ano errado em 2 solicitações da carga; totais da T16 na API.
- **Próximo:** R064 (spec v3.13: T13 E × L da sobra e regra do RETO, T23 3 parâmetros, T14 texto/perfil Análise) quando o contrato do R063 sair.

## 2026-11-17 R059 (commit 505ba19)

- **No ar:** Painel com o card "Peças inteiras do RJ aguardando peso real" (dias desde o recebimento, vermelho acima de `limite_dias`, "Informar peso real", "Encerrar pendência" com justificativa); **T07** faixa vermelha `PESO_REAL_PENDENTE` / aviso cinza antes do prazo, "Enviar ao RJ" desabilitado; **T13** lista as peças pendentes e abre com a sugerida (`?op&lote_id`), sem correção de SA; **T04** etiqueta "mesma linha por exceção" (`paridade_manual`); T14 tolerante a situação desconhecida. Módulo comum `src/api/pesoReal.ts`.
- **Textos:** botões e mensagens com os nomes do menu ("Pedir corte de material", "Cortes a fazer no RJ", "Conferir estoque com o Mega", "Entradas do Mega sem lote"). T17/T18 seguem pelo T05; T24 sem tela (anotado em `docs/ux/01_guia_ux.md` §4).
- **Aguardando TÉCNICO (R060):** formato da API do R058(2). Sem os campos novos, as telas ficam como antes (a pendência antiga sem `recebido_em` não conta para o bloqueio). T23 mostra `PENDENCIA_PESO_REAL_DIAS` sozinha quando a API criar.

## 2026-11-17 Menu por etapa (só texto)

- Menu agrupado (Estoque, Pedidos de corte, Rio de Janeiro, Itu, Ferramentas, Administração; grupo vazio some) e itens/títulos `<h1>` com nomes novos ("Consultar estoque", "Cortes a fazer no RJ", "Receber material do RJ"...). Rotas e ACESSO iguais.

## Rodada 2026-11-12 (commit 2f7bb9e)

- **T04** "Agrupado por liga × bitola" (chave, códigos de Itu, Estoque Mega / RJ em Itu / RJ no Rio, total, reservado, disponível, "só no RJ"/"só em Itu"; clicar abre os lotes da linha). Código Mega só em lote Estoque Mega.
- **T07 passo 2**: grupos de `/lotes/compativeis` com Itu e RJ lado a lado, frase necessário × disponível, kg a usar por lote e "faltam X kg". Sem `grupos`, a lista antiga.
- **Consumo misto opção A**: lotes do RJ = solicitação com `consumo_misto`; parte de Itu (um lote) abre "Registrar corte em Itu agora" com OP, lote, peças e previsto proporcional; marca na T08 (lista e detalhe).
- **T13**: tolerância usada (8 % RJ em Itu / 5 % Estoque Mega) e limite na mensagem de EXCESSO_TOLERANCIA; perda em kg e %. **T10**: aviso BARRA_MAIS_LEVE_QUE_PECA (da API, com reserva local). **T23**: unidade ao lado do valor.
- **Fora (P30/P31)**: SA complementar, "Transferir para o Estoque Mega", comprimento do HISTORICO.
- **Conferido na homologação (12/11, sem gravar; carga antiga):** T04 agrupado (RJ no Rio, RJ em Itu, abrir lotes), T07 passo 2 com OP real (8 grupos, Itu × RJ, consumo misto até a prévia), T08 marca (fetch simulado), T13 prévia 5 % (Estoque Mega) e 8 % (RJ em Itu), T10 aviso (previsto simulado), T23, T15, RETO por origem. Console sem erros. Ajuste `f2a91a9` (marca só com "Todos"; rótulo da aba RETO).
- **Aguardando TÉCNICO (R055):** 500 em `/api/lotes` e `/api/lotes/agrupado` com lote do Estoque Mega (T04 "Todos"/"Estoque Mega" quebrado).
- Próximo: R054 (spec v3.10: pendência "Informar o peso real", "Corrigir no Mega") quando a coordenação mandar.

## No ar (https://estoque.acokorte.com.br)

| Tela | Rota | Commit |
|---|---|---|
| T01, T01b, T02 Login, recuperação e troca de senha | `/entrar`, `/esqueci-senha`, `/redefinir-senha`, `/trocar-senha` | `ba62def`, `75052a6` |
| T03 Painel: **pendências por perfil** + atrasos/divergências + barra de estoque + "Mega atualizado em" | `/` | `21cdec9`, `bc3b321` |
| **T16 Conciliação mínima** (só leitura) | `/conciliacao` | `bc3b321` |
| **Exportar para Excel** em T04, T08 e T14 | — | `bc3b321` |
| **T04 Consulta de estoque** (por lote / agrupado, filtros) | `/estoque` | `026a7fd` |
| **T05 Detalhe do lote** (movimentos, árvore, notas) + **T17** reservas + **T18** ajuste/estorno + atribuir origem | `/estoque/:id` | `026a7fd` |
| **T06 Entrada por NF** | `/entradas-nf` | `026a7fd` |
| T07 Nova solicitação | `/solicitacoes/nova` | `8772e6b` |
| T08 Solicitações | `/solicitacoes`, `/solicitacoes/:id` | `21cdec9` |
| T09 Fila RJ + **Imprimir lista de corte** (A4) | `/fila-rj` | `21cdec9`, `026a7fd` |
| T10 Registrar corte | `/fila-rj/:id/corte` | `21cdec9` |
| T11 COP | `/cops`, `/cops/:id` | `2c0a116` |
| T12 Receber COP | `/recebimentos`, `/recebimentos/:id` | `2c0a116` |
| T13 Corte em Itu | `/corte-itu` | `2c0a116` |
| T14 SA (+ **R031** avisos NF/IPI, histórico da carga) | `/sa` | `8772e6b`, `026a7fd` |
| **T23 Parâmetros** (mínima) | `/admin/parametros` | `026a7fd` |
| Sino, T20 Calculadora, T21 Usuários, T22 Ligas | — | — |

Com isso, **todas as telas da F1 estão no ar**, inclusive o painel com pendências, a T16 mínima e as exportações (`bc3b321`, 04/11).

## Testes com dados reais (carga T25, R033)

- **Leituras conferidas:**
  - T04: 609 lotes; 176 no RJ no Rio; 158 itens agrupados.
  - T05: movimentos, notas e R$/kg da carga.
  - T06 e T08.
  - T09: 6 solicitações, com a versão impressa conferida.
  - T11: 45 COPs recebidos.
  - T14: 8.293 SAs no histórico.
  - T23: 17 parâmetros.
- **Gravações reais:** só no lote L-000185, uma nota e uma reserva já encerrada; somem na recarga. Prévias de ajuste e de entrada por NF foram feitas sem gravar.
- **Achados de dado → R036 (TÉCNICO):** saldo acumulado negativo nos movimentos por causa da data do `SALDO_INICIAL`; "Estornar" aparece nos consumos da carga; ordem do histórico de SA; COPs da carga sem NF.
- **Ainda não testados com dado real** (precisam de solicitação e corte novos, criados no ensaio ponta a ponta do BANCO E TESTES): T07 → T10 → T11 → T12 → T13 gravando. A lógica foi testada com respostas simuladas.

## Rodada auditoria 06/11 (commit 343c4cd)

- **T15** `/entradas-mega` (menu Itu, contador no Painel), **aba "RETO por origem"** na T04 com Excel, **R043** (Encerrar com saldo pendente em Material insuficiente com corte), **T16** com "explicada na T15", **P10** no Painel do RJ (só RJ no Rio). Menu sem "Carga inicial".
- Validado com `tsc` + `build` (o front não tem lint nem testes). Conferência na homologação: pendente do deploy.

## Próximo

1. **T16 vazia** (R036 item 5): conferir de novo quando o TÉCNICO corrigir o vínculo do código Mega.
2. Ajustes que vierem do R036 (TÉCNICO) e do R037 (FUNCIONAL, colunas da lista impressa).
3. Acompanhar o ensaio ponta a ponta de 11/11 e o aceite de 12/11, corrigindo o que os usuários apontarem.
4. F1.1: PDFs (romaneio, ficha do lote), "Exportar SAs novos para o Renato" com marca, tratamento da T16, T15, T19, T26 e coluna "A chegar" no T04.

## Como publicar

1. `git add` arquivo por arquivo só do `frontend/` (há arquivos de outros chats na pasta), depois commit e push.
2. O deploy automático publica em até ~5 min depois do CI verde.
3. Para conferir, compare o `assets/index-*.js` do site (via `curl.exe --resolve estoque.acokorte.com.br:443:204.216.137.171`) com o do `dist/index.html`.

## Rodada 4a (2026-11-04)

- **T05** (`108f7a7`): "Estornar" só quando `estornavel=true` e etiqueta "da carga" quando `da_carga=true`. Se o campo não vier, vale a regra antiga. Conferido depois da recarga: L-000185 com 9 movimentos da carga, sem "Estornar", saldo sem negativo; T16 com 403 códigos (402 OK, 1 MEGA_MAIOR). R036 fechado.
- **T13**: perda em kg e % (PERDA_CORTE_MAX_PCT, spec v3.3) **aguardando o TÉCNICO publicar**; até lá, a prévia continua com a "perda esperada (serra)".

## Aguardando

- TÉCNICO: perda em % na prévia do T13 (`/cortes-itu/validar`).
- Recarga do R038 (respostas do Fabiano): conferir de novo T04/T05/T16 por amostra quando entrar.

## Em andamento / não commitado (2026-11-05, migração para o Claude Code)

- **Nada pendente de commit no `frontend/`.** Último commit `108f7a7` já está no ar (site e `dist` com o mesmo `index-CZhmGSvX.js`).
- `frontend/tsconfig.tsbuildinfo` aparece como não rastreado: é artefato do `tsc -b`, **não commitar** (vale pôr no `.gitignore`).
- Em andamento: só a **T13 perda em kg e %**, esperando o TÉCNICO publicar o `PERDA_CORTE_MAX_PCT` no `/cortes-itu/validar`. Hoje a tela usa `perda_esperada_kg` em `pages/CorteItu.tsx` (linha ~223, "Perda esperada (serra)"); trocar pelo campo novo quando sair, mantendo o antigo como reserva até a API confirmar.
- A pasta `coordenacao/` **não é repositório git**: as mudanças nela valem só no disco (não tem commit).

## Instruções permanentes desta frente

**Git e publicação**
- **Nunca `git add -A` ou `git add .`**: só arquivo por arquivo do `frontend/`. A pasta tem arquivos de outros chats (backend, carga), e um `add` geral já vazou a senha do backup no repo público.
- O FRONTEND pode commitar, dar push e publicar **só o container `web`**. API, banco, nginx e infra são do TÉCNICO.
- Deploy automático: cron de 5 min, só com o CI verde (já levou até ~9 min). Para conferir, comparar o `index-*.js` do site (via `curl --resolve`) com o do `dist/index.html`.
- Deploy manual só se precisar: **uma** conexão SSH, `cmd /c "ssh system-lab bash -s < estoqueack\scripts\deploy_web.sh"`. O PowerShell quebra aspas em ssh inline, e o Snort do pfSense bloqueia muitas conexões seguidas.

**Ambiente**
- O git roda só pelo Windows, porque o mount Linux dá lock.
- Dev contra a homologação: em `frontend/`, `$env:API_ALVO="https://204.216.137.171"; $env:API_HOST="estoque.acokorte.com.br"; npx vite`. O DNS interno dá NXDOMAIN para o domínio.
- npm 11.19 da máquina: a variável `npm_config_allow_scripts` quebra o `npm ci`. Usar `Remove-Item Env:npm_config_allow_scripts; npm ci --ignore-scripts`. O aviso "allow-scripts ignored" no build é inofensivo.
- Validar sempre com `npx tsc -b` + `npm run build`.

**Navegador (chrome-devtools)**
- No máximo **1 conferência por tela, ao final**. Preferir `evaluate_script` (contar elementos, ler a API com `fetch` usando `credentials:'include'`) ou `take_snapshot`. Sem screenshot a cada passo, sem performance/heap.
- Login: se a senha falhar, **não insistir** (bloqueia em 5 tentativas): pedir a nova ao Eduardo. Senha não vai para arquivo nem para a memória.
- Evitar `box-shadow` com 100vmax em tela emulada: já travou o Chrome do DevTools.
- Para testar gravação sem dado real, sobrescrever `window.fetch` com respostas do contrato e navegar pelo menu (SPA), sem recarregar a página. **Nunca criar dado de teste no banco sem pedir.** Se gravar, avisar no R033 o que foi gravado (some na recarga).

**Leitura e economia de tokens**
- Ler só o README, o ESTADO_COORDENACAO, este ESTADO e os pedidos endereçados ao FRONTEND. Da especificação e do contrato da API, só a seção da tela (buscar "T13", "§11"), nunca o arquivo inteiro.
- Resposta no PEDIDOS.md com até 5 linhas, sem quebra de linha na célula. Resposta ao Eduardo também curta.

**Regras de conteúdo**
- Frontend não inventa regra de negócio: se faltar campo, botão ou regra, abrir pedido ao FUNCIONAL. Dado errado da API ou da carga vai para o TÉCNICO.
- Campo novo da API sempre opcional no tipo TS, com reserva para a regra antiga (`m.estornavel ?? regraAntiga`). Assim dá para publicar antes do backend sem quebrar nada.
- Sem prazo fixo nos textos ("até dia X", "alvo 13/11"); vale só a ordem das etapas do ESTADO_COORDENACAO.
- Texto de tela na linguagem do chão (ver `docs/ux/01_guia_ux.md`), números no formato brasileiro, datas absolutas nos documentos.
- PL/SQL ou diagnóstico de dado: query completa, pronta para copiar, e no chat (não em arquivo).
- O Eduardo prefere que eu execute as coisas eu mesmo (servidor, build, conferência) em vez de mandar bloco para ele colar. A exceção é M365/DBA.
- Comando que dá erro: parar, explicar e corrigir junto com ele, sem ficar tentando de novo.
