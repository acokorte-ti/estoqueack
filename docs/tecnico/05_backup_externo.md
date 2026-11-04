# Cópia do backup fora do servidor (OCI Object Storage)

Escrito em 2026-11-04 pelo chat BANCO E TESTES (go/no-go nº 4 da COORDENAÇÃO). Hoje o backup diário fica só no próprio system-lab (`/var/backups/estoqueack`): se o servidor ou o disco se perderem, o backup vai junto.

## 1. Como fica

```
02h15  backup.sh  → /var/backups/estoqueack/estoqueack_AAAAMMDD_HHMMSS.sql.gz.gpg   (como hoje)
                  → copia_externa.sh → bucket "estoqueack-backup"  diario/<arquivo>  (+ mensal/ no dia 1º)
dom 03h30  testar_restauracao.sh           (teste com o backup local, como hoje)
dom 04h00  testar_restauracao_externa.sh   (baixa o mais recente DO BUCKET, confere o sha256 e restaura num
                                            PostgreSQL temporário; não toca no banco em uso)
```

| Decisão | Por quê |
|---|---|
| **OCI Object Storage**, mesma região do servidor (`sa-vinhedo-1`), bucket **privado** | O servidor já está na OCI; 2 MB/dia cabem com folga no gratuito (20 GB) |
| **Sem credencial da OCI no servidor.** Envio por **PAR (pre-authenticated request) de bucket só de escrita** | Quem invadir o servidor não consegue ler, listar nem apagar o que está no bucket |
| **Regra de retenção de 35 dias** no bucket | Nem a escrita consegue apagar ou sobrescrever um backup antes de 35 dias (proteção contra ransomware) |
| **Ciclo de vida:** `diario/` apagado com 40 dias; `mensal/` com 400 dias | Mesmo esquema do backup local (30 dias + mensal por 12 meses), com folga para a retenção |
| PAR **só de leitura (com listagem)** para o teste de restauração | O teste semanal prova que a cópia externa abre. Os arquivos estão criptografados (GPG/AES256) |
| A senha GPG continua **fora** do bucket | Sem ela nenhum backup abre. **Ela precisa estar no cofre de senhas do Eduardo** (pendência antiga) |

## 2. O que o Eduardo faz no console da OCI (≈ 15 min)

Console: https://cloud.oracle.com → região **Brazil Southeast (Vinhedo)** (`sa-vinhedo-1`), no **mesmo compartimento do system-lab**.

1. **Criar o bucket**
   - Menu ☰ → **Storage → Object Storage & Archive Storage → Buckets → Create Bucket**.
   - Nome: `estoqueack-backup`. Default Storage Tier: **Standard**. Encryption: **Encrypt using Oracle managed keys**.
   - **Não** marcar "Enable Object Versioning" (a regra de retenção não funciona com versionamento).
   - Criar. Confirmar que **Visibility = Private**.
2. **Permitir o ciclo de vida** (uma vez por compartimento)
   - Menu ☰ → **Identity & Security → Policies** → (compartimento do system-lab) → **Create Policy**.
   - Nome: `objectstorage-ciclo-de-vida`. Modo manual, uma linha:
     ```
     Allow service objectstorage-sa-vinhedo-1 to manage object-family in compartment <NOME_DO_COMPARTIMENTO>
     ```
     (trocar `<NOME_DO_COMPARTIMENTO>` pelo nome que aparece na lista; se o system-lab estiver na raiz, usar `in tenancy`).
3. **Regras de ciclo de vida** (no bucket → **Lifecycle Policy Rules → Create Rule**), duas regras:
   - Nome `apagar-diario`: Target **Objects**, Lifecycle Action **Delete**, **40 dias**, Object Name Filters → Include prefix `diario/`.
   - Nome `apagar-mensal`: Action **Delete**, **400 dias**, prefixo `mensal/`.
4. **Regra de retenção** (no bucket → **Retention Rules → Create Rule**)
   - Nome `trava-35-dias`, Time-Bound, **35 dias**. **Não** marcar "Enable Retention Rule Lock" agora (depois de 14 dias travada ela não pode mais ser removida; travar só depois do 1º teste OK, ver §4).
5. **PAR de escrita** (no bucket → **Pre-Authenticated Requests → Create Pre-Authenticated Request**)
   - Name: `system-lab-escrita`. Target: **Bucket**. Access Type: **Permit object writes**. **Não** marcar listagem.
   - Expiration: **13/11/2027**.
   - Ao criar, a OCI mostra a **URL uma única vez**: copiar.
6. **PAR de leitura** (mesmo lugar)
   - Name: `system-lab-teste-restauracao`. Target: **Bucket**. Access Type: **Permit object reads**. Marcar **Enable Object Listing**.
   - Expiration: **13/11/2027**. Copiar a URL.
7. **Entregar as duas URLs sem passar pelo chat** (elas valem como senha):
   - Criar o arquivo `Documents\projeto-controle_mp\segredos\par_backup.txt` (**fora** da pasta `estoqueack\`, que é repositório público) com duas linhas:
     ```
     BACKUP_PAR_ESCRITA=<URL do passo 5>
     BACKUP_PAR_LEITURA=<URL do passo 6>
     ```
   - Avisar o chat BANCO E TESTES. Eu copio o arquivo para o servidor (uma conexão), apago a cópia temporária e faço o §3.
8. **Lembrete no calendário**: renovar os dois PARs antes de **13/11/2027**.

## 3. O que o BANCO E TESTES faz no servidor depois

1. Acrescentar ao `~/.config/estoqueack/backup.env` (600) as duas linhas do `par_backup.txt` e
   `BACKUP_COPIA_EXTERNA=$HOME/apps/estoqueack/deploy/backup/copia_externa.sh`.
2. Rodar `deploy/backup/backup.sh` à mão e conferir no console que `diario/<arquivo>` apareceu no bucket.
3. Rodar `deploy/backup/testar_restauracao_externa.sh` → tem que terminar com `RESTAURACAO_OK`.
4. Provar que a escrita **não** apaga: `curl -X DELETE <PAR de escrita>/diario/<arquivo>` tem que ser recusado.
5. Acrescentar ao crontab: `0 4 * * 0 $HOME/apps/estoqueack/deploy/backup/testar_restauracao_externa.sh >> $HOME/.local/state/estoqueack-backup.log 2>&1`.
6. Registrar em `coordenacao/ESTADO_BANCO.md` e marcar o go/no-go nº 4.

## 4. Depois do 1º teste OK

- O Eduardo pode **travar** a regra de retenção (Retention Rules → Edit → Enable Retention Rule Lock). A partir daí ninguém, nem o administrador da conta, apaga um backup antes de 35 dias.
- Se o servidor for perdido: num servidor novo, baixar o backup pelo PAR de leitura (ou pelo console), e restaurar com `deploy/backup/restaurar.sh <arquivo>` usando a senha GPG do cofre.

## 5. Falhas

- Falha no envio: o `backup.sh` grava `ERRO: cópia externa FALHOU …` em `~/.local/state/estoqueack-backup.log` e termina com código 3 (o backup local fica OK). Causa comum: PAR vencido ou revogado.
- Falha no teste externo: `ERRO: …` no mesmo log.
- (Monitoramento por e-mail dessas falhas é pendência do TÉCNICO, item "Monitoramento".)
