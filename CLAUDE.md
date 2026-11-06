# EstoqueACK — controle de matéria-prima da AçoKorte

Sistema que substitui as planilhas de estoque de MP (ESTOQUE 2026, Estoque Geral, Cadastro de SA, Controle de Corte RJ). Duas plantas: **Itu** (matriz, filial 3 no Mega) e **Barra Mansa / RJ**. Controle por **lote** (contêiner + material + bitola), com lotes filhos (sobra/RETO) apontando para a origem; saldo = soma de movimentos imutáveis, em kg. O Mega (Oracle) é **só leitura**: o sistema nunca grava no ERP.

Dono do projeto: **Eduardo Macedo** (TI). Usuários: Fabiano Camargo e Matheus Almeida (Estoque Itu), Marcelo Teixeira (Operação RJ), Renato Pinto (Análise/compras). Tudo em **português do Brasil**.

## Onde está cada coisa

| O quê | Onde |
|---|---|
| Especificação funcional (fonte das regras de negócio) | `docs/03_especificacao_funcional.md` |
| Arquitetura, ADRs | `docs/02_proposta_arquitetura.md`, `docs/adr/` |
| Contrato da API | `docs/api/01_contrato_api.md`, `docs/api/02_contrato_fase1.md` |
| Integração com o Mega (tabelas, regras validadas) | `docs/integracao_mega.md` |
| Retomar a parte técnica (inventário, segredos, operação, lições) | `docs/tecnico/00_RETOMAR_PROJETO.md` |
| Carga inicial, roteiro de aceite, implantação, backup externo | `docs/tecnico/03` a `06` |
| UX e tema visual | `docs/ux/` |
| **Coordenação** (estado de cada frente, decisões, pedidos) | `docs/coordenacao/` |
| Planilhas reais e relatórios da carga (**fora do repo**) | `../planilhas/<data>/`, `../carga/relatorios/` |

## Como o trabalho é organizado

A sessão principal é a **COORDENAÇÃO** (arquiteto-chefe): decide a ordem, chama as frentes e confere o resultado. As frentes são **subagentes** em `.claude/agents/`:

| Subagente | Frente | É dono de |
|---|---|---|
| `funcional` | Regras de negócio, telas, campos, estados, perguntas ao Eduardo | `docs/03_especificacao_funcional.md`, `docs/04_*` |
| `tecnico` | API FastAPI, Mega, servidor, deploy, CI, segurança, carga T25 | `backend/` (exceto testes), `deploy/` (exceto e2e/implantacao), `scripts/`, `docs/api/`, `docs/tecnico/`, `docs/adr/` |
| `frontend` | Telas React, UX | `frontend/`, `docs/ux/` |
| `banco-testes` | Esquema PostgreSQL (revisa toda migração), sync Mega, testes, ponta a ponta, aceite, roteiro de implantação | `backend/tests/`, `docs/integracao_mega.md`, `deploy/e2e/`, `deploy/implantacao/` |

Comandos: `/rodada` (próxima rodada da coordenação), `/estado` (onde estamos).

## Regras para todos (inclusive subagentes)

1. **Leitura enxuta.** Ao começar: `docs/coordenacao/ESTADO_COORDENACAO.md`, o `ESTADO_<FRENTE>.md` da sua frente, as 5 linhas mais recentes de `docs/coordenacao/DECISOES.md` e, em `PEDIDOS.md`, só os pedidos endereçados a você. Especificação e contrato: **só a seção da tarefa** (busque por "T11", "§11"…), nunca o arquivo inteiro. `PEDIDOS_ARQUIVO.md` só se um pedido aberto citar.
2. **Ao terminar:** atualizar o seu `ESTADO_<FRENTE>.md` (curto: no ar / próximo / aguardando), registrar decisões em `DECISOES.md` (mais recente em cima, `AAAA-MM-DD | quem | decisão | onde`) e responder pedidos em `PEDIDOS.md` em **até ~5 linhas, sem quebra de linha dentro da tabela**.
3. **Não decidir no lugar de outra frente.** Precisa de algo dela → abrir pedido em `PEDIDOS.md` (próximo ID = maior `R0xx` de `PEDIDOS.md` + 1). Regra de negócio só vale depois de estar na especificação.
4. **Sem prazo.** Não escrever "até dia X" nem "alvo DD/MM". Vale a ordem das etapas em `ESTADO_COORDENACAO.md` §1 e os critérios de go/no-go. Datas só como registro do que aconteceu (AAAA-MM-DD).
5. **Git:** NUNCA `git add -A`, `git add .`, `git add --all`, `git add -u` nem `git commit -a`. Adicionar arquivo por arquivo e rodar `git status --short --untracked-files=all` antes de commitar (em 2026-10-29 um `add -A` publicou a senha do backup). Um hook bloqueia esses comandos. Antes do commit: `git fetch` + `git status`. Outras frentes trabalham na mesma pasta: arquivo modificado que não é seu fica de fora; se um arquivo seu tiver mudança de outra frente, commitar só o seu trecho (`git add -p` ou `git apply --cached <patch>`). Script novo: `git update-index --chmod=+x`. Mensagem de commit em português, dizendo o quê e por quê. Push na `main` dispara o CI; o servidor só publica commit com CI 100 % verde. GitHub com erro 500/"cannot lock ref": `git fetch` e tentar depois, nunca forçar. O push usa a credencial salva do Git (Git Credential Manager); se não houver, `git -c http.extraHeader=... push` com o `.github_token` (o hook só permite esse uso).
6. **Segredos:** nunca ler, imprimir, copiar ou commitar `.mega_ro`, `.github_token`, `pass_bkp/`, `.env` nem valores de segredos. Segredo novo vai direto para o `.env` do servidor (`read -rsp`), nunca para a conversa. Segredo que o Eduardo precisa passar (URL de PAR, senha) ele deixa em `../segredos/` (fora do repo) e a frente copia para o servidor **sem abrir** (`scp`).
7. **Dados reais nunca entram no repo** (`*.xlsx`, `*.csv`, dumps, relatórios da carga, nem OPs/clientes reais em testes — use exemplos fictícios). Planilhas ficam em `../planilhas/`, relatórios e listas de revisão em `../carga/`.
8. **Erro em comando:** não repetir o mesmo comando esperando resultado diferente. No máximo um diagnóstico; depois parar e explicar ao Eduardo o problema e o que verificar.
9. **Números a partir de cruzamento de dados:** chave composta (ex.: OP + contêiner + janela de data), recorte recente separado do histórico, 2–3 exemplos linha a linha antes de concluir. Se errar, corrigir o documento e avisar o que mudou.
10. **Comunicação com o Eduardo:** em português, curto e técnico. Decisão que é dele (bloquear ou só avisar, tolerâncias, quem pode o quê, prioridade) → **perguntar com opções e uma proposta padrão**, nunca decidir sozinho; escreva a pergunta pronta para ele repassar ao Fabiano ou ao Matheus. Quando ele responde direto na conversa ("até 6 %"), basta registrar. Quando ele precisar executar algo (DBA do Oracle, portal M365/Entra/OCI, `sudo`), mandar **bloco pronto para copiar e colar**, sem ele precisar editar. O resto (servidor, git, build, testes, conferências) a própria frente executa.
11. **SQL para o Eduardo (Mega/Oracle):** sempre a query **completa**, pronta para copiar, **na conversa** (diagnóstico não vira arquivo). Ele usa o PL/SQL Developer: **sem linha em branco** no meio do comando (o Command Window corta e dá ORA-00900/ORA-00942).
12. **"Pronto" exige evidência com dado real:** depois de deploy, carga ou correção, conferir no servidor (saldos, conciliação, o que mudou) e mostrar os números.

## Ambiente

- **Máquina do Eduardo:** Windows 11, Git Bash, Python 3.12 (`py`), Node/npm, git, ssh. **Sem** docker, sqlplus ou oci-cli local.
- **Servidor `system-lab`** (alias no `~/.ssh/config`, Ubuntu 22.04 ARM64, Docker): homologação em `~/apps/estoqueack` (containers db, api, web; web em 127.0.0.1:8090 atrás do nginx do host, HTTPS, só IPs da empresa). Site: https://estoque.acokorte.com.br. Deploy automático por cron a cada 5 min (só CI verde, backup antes, rollback se falhar).
- **SSH: o Snort do pfSense bloqueia o IP com várias conexões seguidas.** Juntar todo o trabalho remoto de uma tarefa num **único** script e rodar com uma conexão: `ssh system-lab 'bash -s' < script.sh` (scripts temporários fora do repo ou em `/tmp`). Nada de um `ssh` por comando. No servidor, não usar `sleep` longo nem git sem `--no-pager`. `sudo` é com o Eduardo. **Se o SSH for recusado ou cair (Snort), não tentar de novo:** parar e avisar o Eduardo, que resolve pessoalmente. Se um comando remoto parecer travado, conferir pelo site (`curl --resolve estoque.acokorte.com.br:443:204.216.137.171 https://estoque.acokorte.com.br/api/saude`) antes de abrir outra conexão.
- **Mega (Oracle 19c na OCI, PDB `dbmegaxt_pdb1`, esquema ACOKORTE, filial 3):** só alcançável pelo system-lab (Native Network Encryption, cliente thick). Usuário `estoqueack_ro` com SELECT em só 9 objetos (lista em `docs/integracao_mega.md`); objeto novo → pedir o GRANT ao Eduardo (DBA). Diagnóstico: `~/estoqueack-mapeamento/q.sh sql/<arquivo>.sql` no servidor.
