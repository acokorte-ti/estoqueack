#!/usr/bin/env bash
# Backup diário do PostgreSQL do EstoqueACK: dump → gzip → GPG (AES256).
# Agendado no cron do usuário ubuntu (system-lab):
#   15 2 * * *  $HOME/apps/estoqueack/deploy/backup/backup.sh >> $HOME/.local/state/estoqueack-backup.log 2>&1
# Configuração (fora do repositório, permissão 600): ~/.config/estoqueack/backup.env
#   BACKUP_GPG_SENHA=...        (OBRIGATÓRIA; guarde uma cópia no cofre de senhas — sem ela o backup não abre)
#   BACKUP_DIR=/var/backups/estoqueack
#   BACKUP_RETENCAO_DIAS=30
#   BACKUP_COPIA_EXTERNA=...    (opcional: comando que recebe o arquivo como $1, ex. envio ao Object Storage)
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a; source .env; set +a
CONF=${ESTOQUEACK_BACKUP_CONF:-$HOME/.config/estoqueack/backup.env}
[ -f "$CONF" ] && source "$CONF"

DESTINO=${BACKUP_DIR:-/var/backups/estoqueack}
RETENCAO_DIAS=${BACKUP_RETENCAO_DIAS:-30}
mkdir -p "$DESTINO"
ARQ="$DESTINO/estoqueack_$(date +%Y%m%d_%H%M%S).sql.gz.gpg"
TMP="$ARQ.parcial"
trap 'rm -f "$TMP"' EXIT

docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=plain --no-owner --no-privileges \
  | gzip -9 \
  | gpg --batch --yes --quiet --symmetric --cipher-algo AES256 \
        --passphrase-fd 3 -o "$TMP" 3<<<"${BACKUP_GPG_SENHA:?defina BACKUP_GPG_SENHA em $CONF}"
mv "$TMP" "$ARQ"
chmod 600 "$ARQ"
echo "$(date -Is) backup gerado: $ARQ ($(du -h "$ARQ" | cut -f1))"

if [ -n "${BACKUP_COPIA_EXTERNA:-}" ]; then
  $BACKUP_COPIA_EXTERNA "$ARQ" && echo "$(date -Is) cópia externa enviada"
fi

# Retenção: diários por $RETENCAO_DIAS dias; no dia 1º, uma cópia vai para mensal/ (guardada 12 meses)
if [ "$(date +%d)" = "01" ]; then
  mkdir -p "$DESTINO/mensal" && cp -p "$ARQ" "$DESTINO/mensal/"
fi
find "$DESTINO" -maxdepth 1 -name 'estoqueack_*.sql.gz.gpg' -mtime +"$RETENCAO_DIAS" -delete
find "$DESTINO/mensal" -name 'estoqueack_*.sql.gz.gpg' -mtime +366 -delete 2>/dev/null || true
