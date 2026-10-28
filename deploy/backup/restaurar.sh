#!/usr/bin/env bash
# Restaura um backup gerado por backup.sh.  ATENÇÃO: substitui o banco atual.
# Uso: deploy/backup/restaurar.sh /var/backups/estoqueack/estoqueack_YYYYMMDD_HHMMSS.sql.gz.gpg
set -euo pipefail
cd "$(dirname "$0")/../.."
source .env
[ -f /etc/estoqueack-backup.env ] && source /etc/estoqueack-backup.env
ARQ=${1:?informe o arquivo de backup}
read -r -p "Isto vai SUBSTITUIR o banco '$POSTGRES_DB'. Digite RESTAURAR para continuar: " ok
[ "$ok" = "RESTAURAR" ] || { echo "Cancelado."; exit 1; }
docker compose stop api
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE);"
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE \"$POSTGRES_DB\";"
gpg --batch --decrypt --passphrase "${BACKUP_GPG_SENHA:?}" "$ARQ" | gunzip | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
docker compose start api
echo "Restauração concluída."
