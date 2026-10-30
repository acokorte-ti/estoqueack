# Como retomar o projeto: parte técnica

Este é o documento de passagem do chat TÉCNICO. Se a conversa se perder, comece por aqui. Última atualização: 2026-10-30.

## 1. Ordem de leitura

1. `Documents\projeto-controle_mp\coordenacao\`: README (regras entre os 3 chats), `ESTADO_TECNICO.md`, `PEDIDOS.md` e `DECISOES.md`.
2. Este arquivo.
3. `docs/02_proposta_arquitetura.md` (arquitetura e decisões de negócio) e `docs/03_especificacao_funcional.md` (telas e fluxos, dono: FUNCIONAL).
4. `docs/integracao_mega.md` (o banco do ERP), `docs/api/01_contrato_api.md` (a API) e `deploy/README-system-lab.md` (o servidor).

## 2. Onde está cada coisa

| O quê | Onde | Versionado? |
|---|---|---|
| Código, documentação, scripts | GitHub `acokorte-ti/estoqueack` (branch `main`) e cópia local em `Documents\projeto-controle_mp\estoqueack` | ✅ Git |
| Coordenação entre os chats | `Documents\projeto-controle_mp\coordenacao\` | ❌ **só no PC do Eduardo**. Fazer backup da pasta `Documents\projeto-controle_mp` |
| Planilhas originais | `Documents\projeto-controle_mp\*.xlsx` | ❌ de propósito (dados da empresa). Só no PC |
| Relatórios do mapeamento do Mega | `estoqueack\relatorio_mega_*.md` (local) | ❌ ignorados pelo Git. O resumo está em `docs/integracao_mega.md` |
| Sistema em homologação | servidor **system-lab**, pasta `~/apps/estoqueack` | o código vem do Git; a configuração **não** (ver §3) |
| Banco do EstoqueACK | PostgreSQL 16 no container `estoqueack-db-1`, volume `/var/lib/docker/volumes/estoqueack_pgdata/_data` | backup diário (§5) |
| Banco do Mega | Oracle 19c, DB System OCI `10.0.0.235`, PDB `dbmegaxt_pdb1`, esquema `ACOKORTE` | não é nosso, só lemos |

## 3. O que existe só no servidor (não está no Git)

Inventário de **onde** fica cada segredo e configuração. **Nenhuma senha está escrita aqui.**

| Item | Caminho no system-lab | Observação |
|---|---|---|
| Configuração do sistema (senha do PostgreSQL, chave da aplicação, credenciais do Mega) | `~/apps/estoqueack/.env` (600) | gerado no próprio servidor em 2026-10-29 |
| Senha inicial do admin `eduardo.macedo` | `~/.estoqueack_admin_inicial` (600) | **apagar depois do 1º acesso** |
| Senha GPG do backup | `~/.config/estoqueack/backup.env` (600) | **guardar no cofre de senhas.** Sem ela, nenhum backup abre |
| Credenciais do Mega (cópia) | `~/estoqueack-mapeamento/.mega_ro` (600) | usado pelos scripts de mapeamento |
| Backups | `/var/backups/estoqueack/` (700) | diários por 30 dias, mais `mensal/` por 12 meses |
| Deploy automático | `~/.local/bin/estoqueack-auto-deploy.sh` | se reinstala a partir de `deploy/auto/auto_deploy.sh` |
| Agendamentos (`crontab -l` do usuário `ubuntu`) | backup às 02h15, teste de restauração aos domingos 03h30, deploy a cada 5 min | |
| Logs | `~/.local/state/estoqueack-backup.log`, `~/.local/state/estoqueack-deploy.log` | |
| Site no nginx do servidor | `/etc/nginx/sites-available/estoqueack` (link em `sites-enabled`) | cópia de `deploy/nginx-host/estoque.acokorte.com.br.conf` |
| Lista de IPs do EstoqueACK | `/etc/nginx/snippets/ips-estoqueack.conf` | inclui `ips-empresa.conf` (comum aos outros sistemas) |
| Certificado HTTPS | `/etc/letsencrypt/live/estoque.acokorte.com.br/` | renovação automática (timer do certbot) |

No **PC do Eduardo**, dentro de `estoqueack\` e ignorados pelo Git:

- `.github_token`: token de push.
- `.mega_ro`: credenciais do Mega.
- `pass_bkp\`: anotação local da senha do backup (ver §8).

## 4. Acesso

| Destino | Como |
|---|---|
| system-lab | `ssh system-lab` (alias no `~/.ssh/config` do Eduardo: `ubuntu@204.216.137.171`). Ubuntu 22.04 ARM64, 4 vCPU, 15 GB, Docker, nginx 1.18 |
| Site | https://estoque.acokorte.com.br, só dos IPs liberados: Itu Agil 45.6.164.74, Itu Vivo 201.91.252.202 e Barra Mansa 200.165.15.190 |
| Mega (Oracle) | a partir do system-lab ou de dentro do container `api`. **Exige criptografia nativa (NNE)**, então precisa do Instant Client 19 (modo thick). Usuário `estoqueack_ro`, só leitura |
| GitHub | repositório `acokorte-ti/estoqueack` (**público**: avaliar se torna privado) |

## 5. Operação do dia a dia (no system-lab, em `~/apps/estoqueack`)

```bash
docker compose ps                                     # situação dos containers
docker compose logs --tail 100 api                    # logs da API
tail -20 ~/.local/state/estoqueack-deploy.log         # últimos deploys
tail -20 ~/.local/state/estoqueack-backup.log         # últimos backups
deploy/backup/backup.sh                               # backup manual
deploy/backup/testar_restauracao.sh                   # testa o último backup (sem tocar no banco em uso)
deploy/backup/restaurar.sh <arquivo>                  # RESTAURA de verdade (substitui o banco; pede confirmação)
curl -s http://127.0.0.1:8090/api/saude               # saúde da API
```

**Publicar uma versão nova:** basta fazer `push` na `main`. O CI roda (segredos, backend, frontend e build ARM64, em cerca de 3 min). Se ficar verde, o servidor publica sozinho em até 5 min, com backup prévio e rollback automático se o teste falhar. Para publicar só o frontend na mão: `ssh system-lab 'bash -s' < scripts/deploy_web.sh`.

**Mudanças em `deploy/nginx-host/`** não são automáticas. Copie o arquivo para `/etc/nginx/...` e rode `sudo nginx -t && sudo systemctl reload nginx`, nunca com pipe no meio.

## 6. Lições aprendidas (não repetir)

| Problema | O que fazer |
|---|---|
| O **Snort do pfSense** bloqueia o IP com várias conexões SSH seguidas | Usar UMA sessão SSH persistente (`ssh -tt` + interação) ou um script por conexão. Não repetir comando que deu timeout: parar e investigar |
| O PC do Eduardo, pela **VPN site-to-site**, não completa a sessão Oracle (cai em 60 s) | Acessar o Oracle a partir do system-lab |
| O Mega exige **NNE**: o modo thin falha (DPY-3001) e o Instant Client 23 falha (ORA-28547) | Instant Client **19.27**, modo thick |
| **nginx 1.18** não aceita `http2 on;` | Usar `listen 443 ssl http2;` |
| `add_header` dentro de uma `location` **anula** os do nível acima | Cabeçalhos de segurança em `deploy/nginx-seguranca.conf`, incluídos em cada location |
| O `.env` tem espaços (formato do Docker) e quebra o `source` do bash | Os scripts leem só as variáveis necessárias (`ler_env`) |
| Cache negativo de DNS (TTL de 1 h): nome novo dá NXDOMAIN por até 1 hora | Esperar, ou limpar o cache do DNS interno (192.168.1.246, pfSense). Certbot: testar com `--dry-run` antes |
| O **sandbox do Claude sai com o IP do Eduardo** (201.91.252.202) | Para testar "de fora", usar o system-lab pelo IP público, que não está liberado |
| `MVT_ST_NUMDOC` no Mega também guarda número de NF | Filtrar `TPM_IN_CODIGO = 13` para baixas de OP |
| O Git no Windows não grava o "+x" dos scripts | `git update-index --chmod=+x <arquivo>` |
| O Desktop Commander bloqueia comandos com certas palavras (sudo etc.) e o PowerShell quebra aspas no ssh | Usar `cmd.exe` e mandar scripts por arquivo/stdin |
| **`git add -A` publicou uma senha** (§8) | Fazer commit só de arquivos explícitos e conferir `git status` antes. O CI tem gitleaks |

## 7. Pendências técnicas (ver também `ESTADO_TECNICO.md`)

1. **Segurança:** pedir ao suporte do GitHub a remoção do cache dos commits antigos (§8). Rotacionar a senha GPG do backup (adiado pelo Eduardo). Avaliar tornar o repositório privado e trocar o `.github_token` por um com permissão mínima.
2. **Backup fora do servidor:** destino a definir com o Eduardo.
3. **Mega:** mapear o cliente da OP, os códigos de situação da OP e a carga de saldo do SA. Depois, trocar o `SELECT ANY TABLE` do `estoqueack_ro` por GRANTs por tabela.
4. **Fase 1** (depois da aprovação da especificação funcional): migração 0002 com solicitação, liberação, COP e recebimento; endpoints de T07 a T12; leitor das planilhas (T25).
5. **Monitoramento:** alerta de site fora do ar, de falha de backup e de falha de deploy.

## 8. Registro de incidentes

**2026-10-29, senha do backup publicada no GitHub.** O commit `ea2b71b (antigo 3422e54)` (13h04), feito pelo chat TÉCNICO com `git add -A`, incluiu `pass_bkp/pass.txt`, uma anotação local do Eduardo com a senha GPG dos backups, num repositório **público**.

- **Impacto:** a senha só abre os arquivos de backup, que ficam apenas no system-lab (pasta 700), sem cópia externa. Nenhum backup vazou, mas a senha deve ser considerada comprometida.
- **Contenção, feita em 2026-10-29 às 14h:** arquivo removido do repositório (`d7393ab (antigo f88e9d1)`); `.gitignore` bloqueando `pass_bkp/`, `*senha*.txt` e `*pass*.txt`; job **gitleaks** no CI com regra própria (`.gitleaks.toml`), testada e capaz de detectar esse arquivo.
- **2026-10-30, histórico limpo (aprovado pelo Eduardo):** `git filter-repo --invert-paths --path pass_bkp/` numa cópia em /tmp. Antes do envio, foi conferido que (1) a árvore final é idêntica, (2) nenhum commit contém a senha (busca pelo valor) e (3) o gitleaks no histórico não acha nada. O envio foi feito com `--force-with-lease`. Os 13 commits a partir do antigo `3422e54` ganharam códigos novos (as referências na coordenação foram atualizadas como "novo (antigo xxx)"). A pasta local foi realinhada com `reset --mixed`, sem tocar em arquivos, e o clone do system-lab com `reset --hard` (árvore idêntica, sem rebuild). Os objetos antigos foram removidos (`reflog expire` + `gc --prune=now`) nos dois lugares.
- **Ainda acessível:** o GitHub mantém os commits órfãos em cache. O link direto do commit antigo responde 200 até o **suporte do GitHub** limpar (ação do Eduardo, dono da conta: https://support.github.com → "Remove cached views of sensitive data", informando o repositório e os commits `3422e54` e `f88e9d1`).
- **Decisão do Eduardo (2026-10-30):** por enquanto, **não** rotacionar a senha do backup e manter o repositório público. A rotação é a correção definitiva e continua recomendada.
