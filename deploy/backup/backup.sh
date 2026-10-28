#!/usr/bin/env bash
# Backup diário do PostgreSQL (dump compactado + criptografado).
# Agendar no cron da VM:  15 2 * * *  /opt/estoqueack/deploy/backup/backup.sh >> /var/log/estoqueack-backup.log 2>&1
# Requisitos: arquivo .env na raiz do projeto; BACKUP_GPG_SENHA definido em /etc/estoqueack-backup.env
#             (opcional) OCI CLI configurado para envio ao Object Storage (bucket BACKUP_BUCKET).
set -euo pipefail
cd "$(dirname "$0")/../.."
source .env
[ -f /etc/estoqueack-backup.env ] && source /etc/estoqueack-backup.env

DESTINO=${BACKUP_DIR:-/var/backups/estoqueack}
RETENCAO_DIAS=${BACKUP_RETENCAO_DIAS:-30}
mkdir -p "$DESTINO"
ARQ="$DESTINO/estoqueack_$(date +%Y%m%d_%H%M%S).sql.gz.gpg"

docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=plain --no-owner \
  | gzip -9 \
  | gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase "${BACKUP_GPG_SENHA:?defina BACKUP_GPG_SENHA}" -o "$ARQ"

echo "$(date -Is) backup gerado: $ARQ ($(du -h "$ARQ" | cut -f1))"

if [ -n "${BACKUP_BUCKET:-}" ] && command -v oci >/dev/null; then
  oci os object put --bucket-name "$BACKUP_BUCKET" --file "$ARQ" --name "$(basename "$ARQ")" --force
  echo "$(date -Is) enviado ao Object Storage: $BACKUP_BUCKET"
fi

find "$DESTINO" -name 'estoqueack_*.sql.gz.gpg' -mtime +"$RETENCAO_DIAS" -delete
