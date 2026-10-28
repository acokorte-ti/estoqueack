# ADR 0001: Stack e hospedagem

Status: aceito em 28/10/2026.

## Decisão

- **Front-end:** React + TypeScript (Vite).
- **API:** Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic.
- **Banco:** PostgreSQL 16.
- **Proxy:** Caddy, com HTTPS automático.
- **Hospedagem:** VM OCI Always Free (Ampere A1, ARM64), com tudo em Docker Compose.

## Motivos

A tipagem de ponta a ponta reduz erros. O Pydantic dá validação forte na entrada da API. O PostgreSQL oferece integridade transacional, *CHECK constraints* e consultas recursivas, que servem para a árvore de origem dos lotes. Por fim, com Docker, migrar para uma VM paga ou um banco gerenciado não exige mudar o código.

## Riscos e mitigação

O Always Free não tem SLA, e a Oracle pode recuperar instâncias ociosas. Para mitigar: mudar a conta para *Pay As You Go* (os recursos grátis continuam), fazer backup diário criptografado no Object Storage e numa cópia fora da OCI, e testar a restauração todo mês.
