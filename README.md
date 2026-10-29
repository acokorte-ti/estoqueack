# EstoqueACK

Sistema de controle de matéria-prima da **AçoKorte**, para as plantas de Itu (Matriz) e Barra Mansa (RJ).
Endereço de produção: `https://estoque.acokorte.com.br`.

O sistema substitui as planilhas ESTOQUE 2026, Materia Prima Geral, Controle de Corte RJ e Cadastro de SA por um controle **por lote** (contêiner + bitola). Os saldos são calculados a partir dos movimentos, e o RETO fica sempre ligado à bitola e ao contêiner de origem.

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/01_analise_processo_atual.md](docs/01_analise_processo_atual.md) | Levantamento do processo e das planilhas |
| [docs/02_proposta_arquitetura.md](docs/02_proposta_arquitetura.md) | Arquitetura, fluxos, validações, telas e banco |
| [docs/03_especificacao_funcional.md](docs/03_especificacao_funcional.md) | Especificação funcional: fluxo completo, telas, botões, origem de cada dado, carga inicial |
| [docs/integracao_mega.md](docs/integracao_mega.md) | Acesso de leitura ao Oracle 19c do Mega |
| [docs/adr/](docs/adr/) | Decisões técnicas registradas |

## Estrutura

```
backend/    API FastAPI (Python 3.12), regras de negócio, migrações Alembic, testes
  app/domain/         regras puras: peso, tolerância de 5 %, medidas, árvore de lotes
  app/api/routes/     endpoints REST (/api/...)
  app/integrations/   conector Mega (somente leitura)
frontend/   React + TypeScript (Vite)
deploy/     Caddy (HTTPS), preparação da VM na OCI, backup e restauração
scripts/    migração das planilhas (Fase 1)
```

## Rodar localmente (desenvolvimento)

Pré-requisitos: Docker, Python 3.12 e Node 22.

```bash
# 1. Banco
docker compose -f docker-compose.dev.yml up -d

# 2. API
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://estoqueack:dev@localhost:5432/estoqueack
export ADMIN_LOGIN=eduardo.macedo ADMIN_SENHA_INICIAL=TrocarNoPrimeiroAcesso1
alembic upgrade head
uvicorn app.main:app --reload            # documentação da API: http://localhost:8000/api/docs

# 3. Web (em outro terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Testes:

```bash
cd backend
pytest                                                   # tudo (precisa de requirements-dev)
python -m unittest discover -s tests -p "test_dominio*"  # só regras de negócio, sem dependências
```

## Implantação na OCI (Always Free, Ampere A1)

1. Crie a VM com Ubuntu 22.04 ou 24.04 (ARM). Na Security List, libere as portas 22, 80 e 443.
2. No DNS, crie um registro `A` de `estoque.acokorte.com.br` apontando para o IP público da VM.
3. Na VM:
   ```bash
   git clone https://github.com/acokorte-ti/estoqueack /opt/estoqueack && cd /opt/estoqueack
   bash deploy/oci/preparar-vm.sh          # depois, saia e entre de novo no SSH
   cp .env.example .env && nano .env       # defina senhas, chave secreta e APP_ENV=prod
   docker compose up -d --build
   ```
4. Agende o backup diário (veja o cabeçalho de `deploy/backup/backup.sh`) e faça um teste de restauração.

Recomendação: mude a conta OCI para **Pay As You Go**. Os recursos Always Free continuam gratuitos, e a Oracle deixa de recuperar instâncias ociosas.

## Segurança

- Login local com hash Argon2id, sessão em cookie HttpOnly e proteção CSRF. A conta é bloqueada após 5 tentativas erradas, e a troca de senha é obrigatória no primeiro acesso.
- Perfis: **Administrador**, **Estoque Itu** (Fabiano, Matheus), **Operação RJ** (Marcelo) e **Análise** (Renato).
- Os movimentos e a auditoria são imutáveis no banco. Correção é sempre por estorno.
- **Nunca faça commit de `.env`, planilhas ou backups.** O `.gitignore` já bloqueia esses arquivos.

## Roadmap

| Fase | Entrega | Situação |
|---|---|---|
| 0 | Fundação: infraestrutura, login, usuários, ligas e densidades, calculadora, regra de tolerância de 5 %, CI | **em andamento** |
| 1 | Estoque RJ: lotes, consulta, corte, fila RJ, COP, recebimento, SA e migração do histórico | próxima |
| 2 | Itu: consumo, sobra, RETO rastreado, destinações e restrições | |
| 3 | Mega: leitura de saldos, OPs e SAs, e conciliação | |
| 4 | Relatórios e painéis | |
| Futuro | Controle por peça com etiqueta e QR Code, e escrita no Mega pelo mecanismo oficial | |
