#!/usr/bin/env bash
# Envia um backup (já criptografado com GPG) ao OCI Object Storage, fora do servidor (go/no-go nº 4).
# Não há credencial da OCI no servidor: usa um PAR (pre-authenticated request) de bucket SÓ DE ESCRITA, que não
# lê, não lista e não apaga. A regra de retenção do bucket impede apagar/sobrescrever por 35 dias (proteção
# contra quem invadir o servidor). Detalhes e passo a passo do console: docs/tecnico/05_backup_externo.md
#
# Chamado pelo backup.sh (BACKUP_COPIA_EXTERNA no backup.env):
#   BACKUP_COPIA_EXTERNA=$HOME/apps/estoqueack/deploy/backup/copia_externa.sh
#   BACKUP_PAR_ESCRITA=https://objectstorage.sa-vinhedo-1.oraclecloud.com/p/<token>/n/<namespace>/b/<bucket>/o/
# Uso manual: deploy/backup/copia_externa.sh /var/backups/estoqueack/estoqueack_AAAAMMDD_HHMMSS.sql.gz.gpg
set -euo pipefail
ARQ=${1:?informe o arquivo de backup}
CONF=${ESTOQUEACK_BACKUP_CONF:-$HOME/.config/estoqueack/backup.env}
# shellcheck disable=SC1090
[ -f "$CONF" ] && source "$CONF"
URL=${BACKUP_PAR_ESCRITA:?defina BACKUP_PAR_ESCRITA em $CONF}
URL=${URL%/}
NOME=$(basename "$ARQ")
SHA=$(sha256sum "$ARQ" | cut -d' ' -f1)

enviar() {   # $1 = prefixo (diario | mensal)
  curl -fsS --retry 3 --retry-delay 10 --max-time 600 -X PUT --upload-file "$ARQ" \
       -H "Content-Type: application/octet-stream" -H "opc-meta-sha256: $SHA" \
       "$URL/$1/$NOME" -o /dev/null
}
enviar diario
# no dia 1º, uma cópia em mensal/ (o ciclo de vida do bucket guarda 13 meses)
[ "$(date +%d)" = "01" ] && enviar mensal
echo "$(date -Is) cópia externa OK: $NOME (sha256 ${SHA:0:12}…)"
