# Coordenação do EstoqueACK

Desde a migração para o Claude Code, as frentes são **subagentes** (`.claude/agents/`) chamados pela sessão principal (COORDENAÇÃO, comando `/rodada`). Esta pasta continua sendo a **memória compartilhada**: cada subagente começa do zero e retoma pelo seu `ESTADO_*`.

| Arquivo | Para quê | Quem escreve |
|---|---|---|
| `ESTADO_COORDENACAO.md` | Ordem das etapas, escopo, riscos, go/no-go, pendências do Eduardo, rodadas | COORDENAÇÃO |
| `ESTADO_FUNCIONAL.md`, `ESTADO_TECNICO.md`, `ESTADO_FRONTEND.md`, `ESTADO_BANCO.md` | No ar / próximo / aguardando de cada frente (curto) | a própria frente |
| `DECISOES.md` | Decisões, mais recente em cima | quem registrou a decisão |
| `PEDIDOS.md` | Pedidos abertos entre frentes (`R0xx`) | quem pede abre; quem recebe responde |
| `PEDIDOS_ARQUIVO.md` | Pedidos fechados (só consulta) | COORDENAÇÃO arquiva |

As regras de trabalho (leitura enxuta, respostas curtas, sem prazo, git, segredos) estão no `CLAUDE.md` da raiz do repositório.

Histórico: até 2026-11-05 o projeto foi tocado em 5 conversas separadas no Claude Cowork (FUNCIONAL, BACKEND 2, FRONTEND, BANCO E TESTES e COORDENAÇÃO), com esta pasta fora do repositório (`projeto-controle_mp\coordenacao\`).
