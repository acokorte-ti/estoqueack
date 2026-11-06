# Backend (FastAPI + SQLAlchemy + PostgreSQL 16)

Regras do backend. Valem junto com o `CLAUDE.md` da raiz.

## Padrões obrigatórios

- **Ação que grava:** `POST …/validar` (prévia, não grava, devolve `ocorrencias` + frase do resultado) e `POST …` com `confirmacoes` `{código: justificativa}`. Pendência não confirmada → **409** com o mesmo corpo da prévia; ação impossível no estado → **400**. Códigos repetidos levam sufixo `#n`. Contrato em `docs/api/02_contrato_fase1.md`: **escrever o contrato antes do código** quando a API for nova e avisar o FRONTEND por pedido.
- **Saldo:** todo código que mexe em saldo pega o lote com `movimentos.lote_ou_404(db, id, travar=True)` (`SELECT … FOR UPDATE` + `populate_existing`) e lança **só** por `movimentos.lancar`. Saldo nunca negativo. Única exceção: a carga T25, que roda sozinha logo após o TRUNCATE e só insere movimentos. Já houve bug real de perda de atualização em cortes simultâneos (corrigido em `7790bfd`).
- **Movimento e auditoria são imutáveis** (trigger no PostgreSQL): só `INSERT`. Correção = estorno ou ajuste (T18). Movimento da carga (`da_carga`) não é estornável.
- **Situação da solicitação é derivada** dos fatos (`fluxo.recalcular_solicitacao`), não gravada à mão.
- **Mensagens em formato BR:** `mensagem`/`frase` com `kg_br`/`pct_br` (`app/domain/formato.py`): "90,0 kg", "8,1 %". Números no JSON sem formatação.
- **Mega só leitura**, pelo gateway (`app/integrations`). Situação da OP: EN/CA bloqueiam (`OP_ENCERRADA`); FP/LB/PL/SI só avisam (`OP_NAO_ABERTA`). Mega fora do ar → 503 com `pode_digitar`.
- **Parâmetros de regra** (tolerâncias, horários, perda de corte `PERDA_CORTE_MAX_PCT` = 6 %) ficam na T23, nunca fixos no código.

## Migrações (Alembic)

- Existem `0001` a `0006`. A próxima é `0007`, com `down_revision` = a última. Conferir `backend/alembic/versions/` antes de criar.
- **Nunca editar migração já aplicada** na homologação. O `banco-testes` revisa toda migração nova (índices, trigger, compatibilidade com a carga).

## Testes

- `pytest` roda em SQLite e, no CI, também em PostgreSQL (`TEST_DATABASE_URL=postgresql+psycopg://…`; o banco indicado é **apagado**). Lint: `ruff`.
- Na máquina do Eduardo não há PostgreSQL nem Docker: rodar SQLite local (`py -3.12 -m venv .venv`, `pip install -r requirements-dev.txt`) e deixar o PostgreSQL para o CI. Python alvo do container é 3.12; manter `timezone.utc` (regra UP017 ignorada).
- Teste não pode depender da hora do dia (o R029 deixou o CI vermelho por isso).

## Carga inicial (T25)

- `backend/app/carga/`, roda no container: `python -m app.carga --pasta … --saida … [--importar --limpar]`. Re-executável: limpa dados operacionais (TRUNCATE) e recarrega; usuários, auditoria, ligas, parâmetros e cache do Mega ficam. Em produção exige `--confirmo-producao`.
- Planilhas no servidor em `~/estoqueack-carga/` (700/600); no PC em `../planilhas/<data>/`. Relatórios em `../carga/relatorios/`. **Antes de cada recarga:** avisar no `PEDIDOS.md` (R033), porque ela apaga o que foi criado em testes, e rodar o backup (`deploy/backup/backup.sh`).
- Passo a passo (numa conexão SSH): `scp` das planilhas para `~/estoqueack-carga/` → `docker cp` para `/tmp/carga` no container `api` → prévia → `--importar --limpar` → conferência (a)–(d) → relatório de volta por `docker cp` + `scp` para `../carga/relatorios/`. Mostrar os números da conferência na resposta.
- Se a estrutura de uma planilha mudar (aba/cabeçalho), a carga **para** (código 2); não adaptar em silêncio.
- Regras de interpretação: especificação §10.7.

## Servidor

- Ao terminar algo de infra/operação, atualizar `docs/tecnico/00_RETOMAR_PROJETO.md` (seção correspondente).
- Ajustes no system-lab (`.env`, restart, verificação) a frente técnica faz sozinha, numa única conexão SSH. Antes de mexer no `.env`: `cp -p .env .env.bak.<AAAAMMDD>`; depois, conferir `/api/saude`.
- E-mail pelo Microsoft Graph (`docs/tecnico/02_email_graph.md`); segredo vence 2028-10-29.
- Backup diário criptografado + cópia externa no OCI Object Storage (`docs/tecnico/05_backup_externo.md`).
