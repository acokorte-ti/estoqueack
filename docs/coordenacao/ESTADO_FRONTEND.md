# Estado — FRONTEND / UX

Atualizado: 2026-11-04 (chat FRONTEND, rodada 2 da COORDENAÇÃO)

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
