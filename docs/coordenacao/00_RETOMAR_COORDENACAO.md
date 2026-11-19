# Retomar a COORDENAÇÃO (troca de conta do Claude, 2026-11-18)

Escrito pela COORDENAÇÃO em 2026-11-18, antes de o Eduardo trocar o Claude Desktop (Bedrock) por uma conta Anthropic. As conversas antigas não aparecem na conta nova; **tudo o que importa está neste repositório e nas pastas ao lado** (lista no §6). Dados reais não entram aqui: OPs, contêineres e números reais estão nos arquivos de `../carga/`.

## 1. Como começar na conta nova

1. Abrir no Claude Code a pasta `C:\Users\eduardo.macedo\Documents\projeto-controle_mp\estoqueack` (a mesma de antes). O `CLAUDE.md`, os subagentes (`.claude/agents/`), os comandos `/rodada` e `/estado` e o hook vêm do repositório.
2. Conferir se a memória do Claude veio junto: deve existir `C:\Users\eduardo.macedo\.claude\projects\C--Users-eduardo-macedo-Documents-projeto-controle-mp-estoqueack\memory\MEMORY.md`. Se não existir, copiar o conteúdo de `..\historico_claude\memoria_claude\` para essa pasta.
3. Primeira mensagem sugerida: **"Leia docs/coordenacao/00_RETOMAR_COORDENACAO.md e rode /estado."**
4. Conferir o GitHub: `gh auth status` (conta `ejmacedo`, com escrita no `acokorte-ti/estoqueack`). O Git deste repositório usa o login do `gh` (`credential.https://github.com.helper = !gh auth git-credential`, só neste repo).
5. A conversa antiga inteira (com os relatórios dos subagentes) está em `..\historico_claude\sessao_coordenacao_ate_2026-11-18.zip`, só para consulta.

## 2. Onde estamos (2026-11-18)

- **Fase:** teste manual do Eduardo na homologação, com ajustes pedidos por ele entrando quase todo dia. Depois: aceite com os usuários → go/no-go → implantação.
- **Homologação no ar** (https://estoque.acokorte.com.br), código até o layout A de 2026-11-19, spec **v3.17**, migração mais recente **0011** (próxima: 0012). Visual: layout A "Bancada" (`docs/ux/02_tema_visual.md`).
- **Carga:** recarga do zero em 2026-11-17 com as planilhas de `../planilhas/2026-11-17/` e `../carga/correcoes_carga.json`. Conferida duas vezes (TÉCNICO e BANCO E TESTES, leitor independente): Estoque Mega = saldo do Mega (0 código com diferença > 5 kg); RJ no Rio = ESTOQUE 2026; RJ em Itu e RETO batem; 0 lote do RJ com código do Mega; saldo = soma dos movimentos em 100 % dos lotes.
- **Ponta a ponta:** 5 de 5 caminhos OK em 2026-11-17 (cópia do banco, Mega real).
- **Modo de teste ligado na homologação** (`MODO_TESTE=true`): botão "Confirmar SA (teste)" na T14 e faixa "Ambiente de teste". **Desligar na implantação** (`docs/tecnico/06_implantacao.md` §2.3).
- **Perfis:** o Eduardo pediu para não se preocupar com perfis durante os testes; ajustar depois.

### Go/no-go

| Nº | Critério | Situação |
|---|---|---|
| 1 | Carga conferida | ✅ números; paridade conferida pelo Fabiano (dúvidas menores no arquivo de pendências) |
| 2 | 5 caminhos ponta a ponta | ✅ 2026-11-17 (repetir depois das mudanças de tela, antes do aceite) |
| 3 | Concorrência no PostgreSQL | ✅ |
| 4 | Backup + restauração com cópia externa | ⏳ local ✅; **cópia externa: falta o Eduardo criar bucket + 2 PARs na OCI** (`docs/tecnico/05_backup_externo.md` §2) |
| 5 | Aceite dos usuários | ⏳ falta criar os usuários reais (e a Amanda, para o SA) e fazer o aceite |
| 6 | Estorno/ajuste | ✅ |

## 3. O que entrou desde a auditoria de 06/11 (resumo)

Detalhes em `DECISOES.md` (mais recente em cima) e na spec.

- Auditoria corrigida: RETO do RJ em Itu em sub-lotes por origem, leitor de redondo (Ø/RED), solicitação parcial travada, T15 mínima, aba RETO por origem.
- **Paridade RJ × Itu por liga + bitola exatas** (sem código do Mega no material do RJ); MOD é liga distinta; 1.2344 = H13 e 1.2379 = D2; comprimento e múltiplo diferenciam; 3 exceções de "paridade manual".
- 8 % de tolerância para material do RJ, 5 % para o resto; consumo misto RJ + Itu; peça inteira do RJ com **pendência de peso real** (bloqueia o "Enviar ao RJ" depois de 7 dias); SA **não** é corrigido no Mega; quem cadastra o SA é a **Amanda** (o Fabiano pede).
- **Regra do RETO** pela espessura × largura da sobra (E ≤ 50 e L < 200, ou E > 50 e L < 250), com "Conferi a regra".
- Menu renomeado por função; "Pedir corte de material" é a **única porta de entrada** (lote de Itu continua na mesma tela para o lançamento do corte).
- **Revisão de código de 18/11 (sem regra nova):** lote travado **antes** da validação em todas as gravações que mexem em saldo ou reserva (`movimentos.travar_lotes`: pedir corte, rascunho, trocar lote, corte RJ, corte em Itu, reserva, ajuste de inventário); disponível nunca negativo; erro do Mega na estrutura da OP vai para o log; painel sem N+1; índice `paridade_item_id` (0011); frontend sem corrida de resposta em Estoque/RETO por origem, corte em Itu relê a URL, erros de carregamento mostrados, janelas da T14 no componente `Janela`, formatação central (`reais`, `rsKg`, `pct`). Teste novo de concorrência do ajuste em `tests/test_postgres.py`. Senha: não pode conter o login (Eduardo, 2026-11-18).
- **Ajustes do teste de 18/11 (spec v3.16):** Cadastro de SA agrupado e filtrado por COP; R$/kg do precificador obrigatório; NF do COP (e do B2) só depois do SA confirmado e do R$/kg (`PRECIFICADOR_PENDENTE`); precificador visível no COP; telas na largura toda; botão "Esconder menu". Detalhes da P44 com proposta padrão (pendências item 17).
- Ajustes do teste de 17/11: filtro de liga por "contém"; instrução de processo com várias opções; justificativa sem mínimo (não vazia); Fila RJ com pesquisa, cartões que expandem e ordem por tempo de espera; só Fio Certo como emitente; lote **estritamente maior** que a peça; vários lotes na mesma OP com **balanceamento de peças** e **lote menor consumido por inteiro**; impressão do RJ limpa com peso estimado; SA no recebimento; botões Voltar/Avançar no topo.

## 4. O que está pela metade / próximos passos (nesta ordem)

1. **Anexos e entrada por NF enriquecida** (spec v3.15 pronta; **não programado**): pedidos **R074** (TÉCNICO), **R075** (FRONTEND), **R076** (BANCO E TESTES: revisar migração, e os anexos entram no backup). NF/packing list/precificador escaneados (PDF/JPG/PNG, XLSX no precificador, até 10 MB), R$/kg por item, campos novos da NF, tudo visível no detalhe do lote. Seguir as propostas do arquivo de pendências itens 7–8 até o Eduardo responder.
2. **Fechamento mensal do material do RJ para a Inês**: modelo na spec (T19 item 10, "[proposta, a validar com a Inês]"), item 9 do arquivo de pendências. **Só programar depois que a Inês validar.**
3. **Melhoria do deploy** (pergunta aberta ao Eduardo): quando a ponta da `main` estiver com CI rodando, publicar o último commit já verde (`deploy/auto/auto_deploy.sh`). Hoje, commits seguidos atrasam a publicação até a sequência parar.
4. **Arquivo único de pendências dos usuários**: `../carga/PENDENCIAS_USUARIOS_2026-11-18.txt` (17 itens, cada um com proposta padrão; o sistema já funciona com as propostas). Quando as respostas chegarem: registrar em `DECISOES.md`, mandar FUNCIONAL atualizar a spec e TÉCNICO/FRONTEND ajustarem; se mudar a carga, recarregar.
5. **Pedidos menores abertos:** R066 (BANCO E TESTES revisar a 0010), R068 (FUNCIONAL registrar leituras do TÉCNICO), R069 (pontos menores da 0009: fuso do dia da pendência, ciclo na paridade, prazo no rollback), R071/R073 (formato da API para o FRONTEND; provavelmente já atendidos, conferir e fechar).
6. **Limpeza do `PEDIDOS.md`:** vários pedidos antigos estão "ABERTO" mas já foram atendidos (R023, R025, R033, R039, R046, R047, R049, R050, R051, R052, R053, R054). Fechar com uma linha cada e mover para `PEDIDOS_ARQUIVO.md`.
7. **Repetir o ponta a ponta** (`deploy/e2e/rodar_e2e.sh`, BANCO E TESTES) depois dos ajustes de tela/regra de 17/11, e uma **recarga final** com as planilhas mais novas antes do aceite.
8. **Com o Eduardo:** backup externo na OCI; criar os usuários reais (Fabiano, Matheus, Marcelo, Renato, Amanda; a Inês quando for usar o fechamento); aceite; go/no-go.
9. **Depois da implantação (F1.1):** PDFs de romaneio/ficha, relatórios completos (T19), T16 completa, T22, T26 (material a chegar), achados B05–B08 já tratados na carga ficam só como conferência.

## 5. Como a COORDENAÇÃO trabalha (combinado com o Eduardo)

- **Perguntas aos usuários (Eduardo, Fabiano, Matheus, Marcelo, Inês): sempre num arquivo único** `../carga/PENDENCIAS_USUARIOS_<data>.txt`, numerado, cada item com evidência, proposta padrão e "Resposta: ____"; texto simples; a versão anterior vai para `../carga/perguntas_antigas/`. Subagentes devolvem as perguntas no retorno e a coordenação consolida. O Fabiano se irrita com pergunta repetida: tom curto, sem repetir o que ele já respondeu.
- **Enquanto não há resposta, seguir a proposta padrão** e deixar fácil de mudar (parâmetro ou arquivo de correções). O Eduardo pediu: "o que tiver de pendência pode fazer sem depender de mim, desde que não quebre nada".
- **Commits da coordenação só com pathspec:** `git commit -m "..." -- docs/coordenacao/DECISOES.md`. O índice do Git é compartilhado com os subagentes; em 17/11 um commit da coordenação levou código do TÉCNICO junto por engano.
- **Pronto = evidência:** commit na `main`, CI verde (`gh run list`), deploy conferido pelo site (`curl --resolve ... /api/saude` e o bundle `index-*.js`), números reais quando for carga.
- **Deploy:** cron no system-lab a cada 5 min, só CI 100 % verde, backup antes, rollback se falhar. Commits em sequência atrasam a publicação (ver §4 item 3).
- **Conferência de tela pelos subagentes:** pelo Chrome do DevTools, com a sessão que o Eduardo loga; deixar aberta só a aba do EstoqueACK (em 12/11 um script rodou por engano em outra aba). Nunca pedir a senha na conversa.
- **SSH:** uma conexão por tarefa, com script (Snort bloqueia várias). Se recusar, parar e avisar.
- **Recarga** apaga os dados de teste (pedidos, cortes, COPs); usuários, ligas e parâmetros ficam. Avisar o Eduardo antes.
- O Eduardo usa o modo "ignorar permissões" no app; o `.claude/settings.json` local tem mudanças dele que **não** são commitadas.

## 6. Onde está cada coisa fora do repositório

| O quê | Onde (`C:\Users\eduardo.macedo\Documents\projeto-controle_mp\`) |
|---|---|
| Pendências dos usuários (arquivo único atual) | `carga\PENDENCIAS_USUARIOS_2026-11-18.txt` |
| Roteiro do teste manual e OPs sugeridas | `carga\ROTEIRO_TESTE_MANUAL_2026-11-17.md`, `carga\ops_teste_manual_2026-11-17.txt` |
| Correções da carga (respostas do Fabiano aplicadas) | `carga\correcoes_carga.json` (vai junto em toda recarga) |
| Relatórios da carga, paridade e leitura | `carga\relatorios\` (paridade conferida: `paridade_rj_itu_previa_20261112_0904_RESPONDIDO.xlsx`; carga atual: `carga_resultado_20261117_1322.xlsx`) |
| Respostas dos usuários recebidas | `carga\respostas.docx`, `carga\observacoes_fluxo_2026-11-17.docx`, `carga\perguntas_antigas\` |
| Planilhas mais novas | `planilhas\2026-11-17\` |
| Auditoria de 06/11 | `auditoria\` |
| Conversa antiga e memória do Claude | `historico_claude\` |
| Segredos (nunca ler/abrir) | `segredos\`, `.mega_ro`, `.github_token`, `pass_bkp\`, `.env` |
