# Frontend (React + TypeScript + Vite)

Regras do frontend. Valem junto com o `CLAUDE.md` da raiz.

## O que manda

- **Campos, botões e regras vêm da especificação** (`docs/03_especificacao_funcional.md`, seção da tela). Faltou algo → pedido ao `funcional`, não inventar regra.
- **Formato da API vem do contrato** (`docs/api/02_contrato_fase1.md`, seção da tela). Não ler código do backend para descobrir formato; se o contrato estiver errado ou faltando, pedido ao `tecnico`.
- Guia de UX: `docs/ux/01_guia_ux.md`. Tema: `docs/ux/02_tema_visual.md` e tokens em `src/styles/tema.css` (toda tela usa os tokens).

## Padrões de tela

- **Um** botão `.primario` (vermelho #BE0A0F) por tela, com nome do que faz; `.secundario` contorno grafite; `.perigo` contorno vermelho para desfazer. Altura mínima 48 px (56 px no rodapé do celular).
- Resultado mostrado **antes** de gravar: chamar `/validar`, mostrar as ocorrências no `PainelValidacao` (estou ciente + justificativa ≥ 10 caracteres, sufixo `#n` como veio). 409 na gravação reabre o painel; 400 vira mensagem.
- Bloqueio de validação é caixa clara com ✕, nunca botão vermelho. Campos [MEGA]/[LOTE]/[CALC]/[SISTEMA] só como texto; [SUGERIDO] preenchido e marcado.
- Tablet/celular primeiro em T09, T10, T12, T13, T20: tabelas viram cartões abaixo de 900 px; rodapé de ação fixo.
- **Campo novo da API sempre opcional no tipo TS, com reserva para a regra antiga** (ex.: `m.estornavel ?? regraAntiga`). Assim o frontend pode publicar antes do backend sem quebrar.
- Texto de tela na linguagem do chão de fábrica (`docs/ux/01_guia_ux.md`); números no formato brasileiro.
- Menu pela matriz perfil × tela (`src/api/acesso.ts`, especificação §4.1). Operação RJ vê só RJ no Rio.

## Validar sem gastar à toa

- Sempre: `npx tsc -b` e `npm run build` (o aviso "allow-scripts ignored" no build é inofensivo).
- Navegador (MCP chrome-devtools): **no máximo uma conferência por tela, no final**, preferindo `evaluate_script` (contar elementos, ler a API com `fetch(..., {credentials: "include"})`) e, se precisar ver a tela, `take_snapshot`. Nada de screenshot a cada passo, nem trace de performance ou heap snapshot. Evitar `box-shadow` com `100vmax` em tela emulada (travou o Chrome).
- Homologação tem dados reais da carga: testar lendo. **Nunca criar dado de teste no banco sem pedir.** Para testar gravação, sobrescrever `window.fetch` (via `evaluate_script`) com respostas do contrato e navegar pelo menu (SPA), sem recarregar a página. Se gravar algo, dizer no `PEDIDOS.md` (R033) o que foi gravado (some na próxima recarga).
- Senha do admin muda às vezes: se o login falhar, **não insistir** (bloqueia em 5 tentativas); pedir a nova ao Eduardo.

## Rodar e publicar

- `npm ci` na máquina do Eduardo: antes, `unset npm_config_allow_scripts` (Git Bash) ou `Remove-Item Env:npm_config_allow_scripts` (PowerShell), depois `npm ci --ignore-scripts`.
- Dev contra a homologação (o DNS interno não resolve o domínio): `API_ALVO=https://204.216.137.171 API_HOST=estoque.acokorte.com.br npx vite`.
- **Publicar = push na `main`** (só arquivos de `frontend/`, um por um). O deploy automático sobe em alguns minutos depois do CI verde. Conferir comparando o `assets/index-*.js` de `curl --resolve estoque.acokorte.com.br:443:204.216.137.171 https://estoque.acokorte.com.br/` com o do `dist/index.html`.
- Caminho manual, só se o deploy automático estiver parado: `ssh system-lab 'bash -s' < scripts/deploy_web.sh` (recria só o container `web`). API, banco e nginx do host são do `tecnico`.
