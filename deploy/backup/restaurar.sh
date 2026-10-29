#!/usr/bin/env bash
# Restaura um backup gerado por backup.sh.  ATENÇÃO: substitui o banco atual.
# Uso: deploy/backup/restaurar.sh /var/backups/estoqueack/estoqueack_YYYYMMDD_HHMMSS.sql.gz.gpg
set -euo pipefail
cd "$(dirname "$0")/../.."
# Lê só as variáveis necessárias do .env (o arquivo segue o formato do Docker, não é script bash)
ler_env() { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
POSTGRES_USER=$(ler_env POSTGRES_USER); POSTGRES_DB=$(ler_env POSTGRES_DB)
source "${ESTOQUEACK_BACKUP_CONF:-$HOME/.config/estoqueack/backup.env}"
ARQ=${1:?informe o arquivo de backup}
read -r -p "Isto vai SUBSTITUIR o banco '$POSTGRES_DB'. Digite RESTAURAR para continuar: " ok
[ "$ok" = "RESTAURAR" ] || { echo "Cancelado."; exit 1; }
docker compose stop api
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE);"
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE \"$POSTGRES_DB\";"
gpg --batch --quiet --decrypt --passphrase-fd 3 "$ARQ" 3<<<"${BACKUP_GPG_SENHA:?}" | gunzip | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
docker compose start api
echo "Restauração concluída."
