# Roteiro de implantação (sem data: vale a ordem das etapas e o go/no-go)

Escrito em 2026-11-04 pelo chat BANCO E TESTES (rodada 2 da COORDENAÇÃO). **Divisão de tarefas proposta, a confirmar pelo TÉCNICO no R034.** A produção é o mesmo servidor e o mesmo endereço da homologação (system-lab, https://estoque.acokorte.com.br); o que muda é que, a partir da liberação, **o sistema é a fonte da verdade** e as planilhas viram só conferência até o fim do paralelo (duas semanas).

Siglas: **ED** = Eduardo · **TEC** = chat TÉCNICO (BACKEND 2) · **BT** = chat BANCO E TESTES · **FAB** = Fabiano.

## 0. Pré-requisitos (antes da implantação — go/no-go)

| # | Item | Quem | Ok |
|---|---|---|---|
| 0.1 | Go/no-go da COORDENAÇÃO dado (ESTADO_COORDENACAO §5: carga conferida, 5 caminhos, concorrência, backup externo, aceite, estorno/ajuste) | ED + COORDENAÇÃO | ☐ |
| 0.2 | Correções do R032 aplicadas nas planilhas e **última recarga na homologação conferida pelo Fabiano** | TEC + FAB | ☐ |
| 0.3 | Ponta a ponta na cópia do banco OK (`deploy/e2e/rodar_e2e.sh`, antes do aceite) | BT | ☐ |
| 0.4 | Backup externo funcionando e testado (`docs/tecnico/05_backup_externo.md`) | ED (console) + BT | ☐ |
| 0.5 | Os 4 usuários reais criados e testados no aceite | ED | ☐ |
| 0.6 | **Commit que vai para produção** escolhido (o último com CI verde depois do aceite) e anotado aqui: `________` | TEC | ☐ |
| 0.7 | Senha GPG do backup no cofre de senhas do Eduardo (sem ela, nenhum backup abre) | ED | ☐ |

## 1. Linha do tempo

### Véspera da implantação (D-1)

| Hora | Passo | Quem |
|---|---|---|
| 18:00 | **Congelamento das planilhas.** Mensagem para Fabiano, Matheus, Marcelo e Renato: "a partir de agora não lancem mais nada nas 4 planilhas (ESTOQUE 2026, Materia Prima Geral, Controle de Corte, Cadastro de SA). O que acontecer até a liberação de D, anotem em papel; lançamos no sistema depois da liberação." | ED |
| 18:30 | Copiar as 4 planilhas **congeladas** (mesmos nomes de arquivo e de abas) para `Documents\projeto-controle_mp\planilhas\AAAA-MM-DD (data de D-1)\` e guardar uma cópia zipada `planilhas_congeladas_AAAA-MM-DD.zip` (é o ponto de volta do rollback) | ED |
| 18:30 | **Congelamento de código:** nada novo entra na `main` até D 18:00, a não ser correção combinada com a COORDENAÇÃO | TEC, FRONTEND, BT |

### Dia da implantação (D)

| Hora | Passo | Quem | Comando / conferência |
|---|---|---|---|
| 06:00 | Sincronização automática do Mega (06h) | — | `tail ~/.local/state/estoqueack-agendador.log` → `{"estoque": "OK"}` |
| 06:15 | **Pausar** o deploy automático e o agendador (crontab) | BT | §2.1 |
| 06:20 | **Backup antes** (local + cópia externa), anotar o arquivo: `________` | BT | `deploy/backup/backup.sh` → "cópia externa OK" |
| 06:25 | Conferir versão e **migrações**: commit = 0.6; `alembic current` = `head` | BT | §2.2 |
| 06:30 | `APP_ENV=prod` no `.env` e recriar só a API | TEC | §2.3 |
| 06:35 | Enviar as planilhas congeladas ao servidor (uma conexão) e copiar para o container | TEC | `docs/tecnico/04_carga_inicial.md` §1, passos 1–2, pasta `AAAA-MM-DD` |
| 06:40 | **Sincronizar agora** (saldo do Mega do dia) | TEC | `POST /api/mega/sincronizar` ou `python -m app.jobs.agendador --forcar` |
| 06:45 | **Prévia** da carga (não grava). **Para se:** "estrutura mudou" (código 2) ou pendência BLOQUEIA nova em relação à última prévia aprovada | TEC | passo 4 |
| 06:55 | **Carga final:** `--importar --limpar --confirmo-producao` | TEC | passo 5 |
| 07:05 | **Conferência (a)–(d)** do relatório da carga (aba Conferência) | TEC | (a) Estoque Mega × saldo Mega ≤ 5 kg; (b) RJ no Rio × ESTOQUE 2026; (c) RJ em Itu × Estoque Geral; (d) solicitações/COPs/SAs × planilhas |
| 07:10 | **Conferência independente** no banco | BT | `deploy/implantacao/conferir.sh` → `CONFERENCIA_OK` |
| 07:15 | O Fabiano confere 3 lotes que conhece de cabeça e a Fila RJ (T09) | FAB | mesmos saldos da planilha congelada |
| 07:20 | **Smoke test** | BT | §3 |
| 07:35 | Religar o **agendador** (o deploy automático continua pausado até 18:00) | BT | §2.1 |
| 07:40 | Apagar `~/.estoqueack_admin_inicial`; conferir que nenhum usuário de teste está ativo | BT + ED | §2.4 |
| 07:45 | **Decisão de liberação** (tudo acima ok) | ED | — |
| 08:00 | **Liberação.** Mensagem aos usuários: "a partir de agora o estoque de MP é no sistema; as planilhas ficam só para conferência até o fim do paralelo (duas semanas)". Lançar no sistema o que foi anotado em papel. **Anotar a hora exata:** `________` (usada no rollback) | ED | — |
| 08:00–12:00 | Plantão: logs da API, sino de falhas, dúvidas dos usuários | TEC + BT | `docker compose logs -f api` |
| 13:00 | Sincronização das 13h OK | BT | log do agendador |
| 17:00 | `conferir.sh` de novo + backup manual; registrar o dia em ESTADO_BANCO | BT | — |
| 18:00 | Religar o deploy automático; fim do congelamento de código | BT | §2.1 |

## 2. Comandos (system-lab, `~/apps/estoqueack`, uma sessão SSH)

### 2.1 Pausar e religar os agendamentos

```bash
crontab -l > ~/crontab_antes_implantacao.txt                                  # guarda como estava
crontab -l | sed -E '/estoqueack-(auto-deploy|agendador)/ s/^/#PAUSADO# /' | crontab -   # pausa os dois
crontab -l | sed -E '/estoqueack-agendador/ s/^#PAUSADO# //' | crontab -       # 07:35 religa o agendador
crontab -l | sed -E 's/^#PAUSADO# //' | crontab -                              # 18:00 religa o deploy
crontab -l                                                                     # conferir
```

### 2.2 Versão e migrações

```bash
git --no-pager log --oneline -1                    # = commit do item 0.6
docker compose exec -T api alembic current         # tem que terminar em "(head)"
docker compose exec -T api alembic heads           # uma só cabeça
```

### 2.3 Modo produção

```bash
sed -i 's/^APP_ENV=.*/APP_ENV=prod/' .env && grep '^APP_ENV' .env
docker compose up -d api && sleep 10 && curl -fsS http://127.0.0.1:8090/api/saude    # {"status":"ok"}
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8090/api/docs             # 404 (documentação fechada)
```

### 2.4 Usuários

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT login, perfil, ativo FROM usuario ORDER BY login"'
rm -f ~/.estoqueack_admin_inicial
```

Só devem estar ativos: `eduardo.macedo`, `fabiano.camargo`, `matheus.almeida`, `marcello.teixeira`, `renato.pinto` (usuários `e2e.*` só existem na cópia do banco e somem com ela).

## 3. Smoke test (BT, ≈ 15 min, sem gravar nada no banco de produção)

| # | Teste | Esperado |
|---|---|---|
| 1 | `curl https://estoque.acokorte.com.br/api/saude` de dentro da empresa | `{"status":"ok"}` |
| 2 | `deploy/e2e/rodar_e2e.sh` (roda os 5 caminhos numa **cópia** do banco recém-carregado, com o Mega real, e apaga a cópia) | `RESULTADO: OK` |
| 3 | Login de um usuário de cada perfil (Fabiano, Marcelo, Renato) | Menu do perfil; Marcelo só vê RJ no Rio |
| 4 | T04: totais por estoque | Iguais aos do `conferir.sh` |
| 5 | T07, passo 1, com uma OP aberta real | Item, cliente, pedido e estrutura vindos do Mega |
| 6 | Painel | "Mega atualizado em <data de D>, 06:4x" |

## 4. ROLLBACK — voltar às planilhas

### 4.1 Antes da liberação (até 08:00): **não liberar**

Critérios (qualquer um): a carga parou ("estrutura mudou" ou erro); conferência (a)–(d) com diferença não explicada; `conferir.sh` ≠ `CONFERENCIA_OK`; o Fabiano não reconhece os saldos; smoke test falhou.

1. ED avisa os usuários: "**continuem nas planilhas**, a implantação foi adiada". As planilhas são **descongeladas** (o que foi anotado em papel volta para elas).
2. BT religa os agendamentos (§2.1) e volta `APP_ENV=homolog` (§2.3 com `homolog`).
3. O banco fica como está, para a análise (a carga é re-executável; não precisa restaurar). Se o problema for o próprio banco, BT restaura o backup das 06:20: `deploy/backup/restaurar.sh <arquivo>`.
4. TEC + BT registram a causa em ESTADO_BANCO/ESTADO_TECNICO; COORDENAÇÃO define nova implantação.

### 4.2 Depois da liberação (durante o paralelo)

**Critérios para voltar** (decisão do Eduardo, ouvida a COORDENAÇÃO):
- saldo errado em lote que **não** se corrige com estorno/ajuste (T18);
- operação parada mais de **2 horas** sem contorno (não dá para registrar corte, COP, SA ou recebimento);
- sistema fora do ar mais de **4 horas** no expediente;
- perda de dado (algo gravado que sumiu).

Erros de texto, de tela ou de conforto **não** são motivo de rollback: viram correção.

**Passo a passo:**

1. **Decisão e aviso** (ED): "a partir de agora, voltem às planilhas; não lancem mais no sistema".
2. **Fechar a gravação** (TEC): desativar os usuários operacionais na T21 (Fabiano, Matheus, Marcelo, Renato), mantendo o Admin. Os dados ficam no banco para a análise.
3. **Backup do estado** (BT): `deploy/backup/backup.sh` (vai também para a cópia externa).
4. **O que foi lançado no sistema** (BT): `deploy/implantacao/movimentos_desde.sh "<hora da liberação>"` → CSV com data, quem, tipo, lote, contêiner, material, estoque, código Mega, kg, peças, OP, COP, SA, documento e justificativa. Também: lista de solicitações, COPs e SAs criados desde a liberação (T08/T11/T14 com filtro de data, ou consulta do BT).
5. **Atualizar as planilhas** (FAB + Marcelo): partir das **planilhas congeladas de D-1 18:00** (zip do item 18:30) e lançar o que está no CSV. Conferir os totais: RJ no Rio por contêiner e Estoque Geral.
6. **Mega**: nada a desfazer — o sistema nunca grava no Mega; as baixas e SAs feitos no Mega continuam valendo.
7. **Registro** (TEC + BT): causa, dados do período e plano de nova implantação.

## 5. Depois da implantação

- **Paralelo (duas semanas após a liberação):** planilhas só para **conferência semanal**, não para operar (decisão do Eduardo, ESTADO_COORDENACAO §6 item 2). BT roda `conferir.sh` todo fim de dia na 1ª semana.
- A partir da 1ª sexta depois da liberação: conferência semanal com o Fabiano (sistema × planilha) e com a T16 mínima (sistema × Mega).
