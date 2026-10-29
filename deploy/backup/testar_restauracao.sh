#!/usr/bin/env bash
# Teste de restauração SEM tocar no banco em uso: restaura o backup mais recente (ou o informado)
# num PostgreSQL temporário e compara a contagem de linhas das tabelas com o banco atual.
# Uso: deploy/backup/testar_restauracao.sh [arquivo.sql.gz.gpg]
set -euo pipefail
cd "$(dirname "$0")/../.."
# Lê só as variáveis necessárias do .env (o arquivo segue o formato do Docker, não é script bash)
ler_env() { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
POSTGRES_USER=$(ler_env POSTGRES_USER); POSTGRES_DB=$(ler_env POSTGRES_DB)
CONF=${ESTOQUEACK_BACKUP_CONF:-$HOME/.config/estoqueack/backup.env}
source "$CONF"
ARQ=${1:-$(ls -t "${BACKUP_DIR:-/var/backups/estoqueack}"/estoqueack_*.sql.gz.gpg | head -1)}
NOME=estoqueack-teste-restauracao-$$
echo "Restaurando $ARQ num container temporário ($NOME)…"
docker run -d --rm --name "$NOME" -e POSTGRES_PASSWORD=teste -e POSTGRES_DB=restaurado postgres:16-alpine >/dev/null
trap 'docker rm -f "$NOME" >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 30); do docker exec "$NOME" pg_isready -U postgres -d restaurado >/dev/null 2>&1 && break; sleep 1; done
sleep 2
gpg --batch --quiet --decrypt --passphrase-fd 3 "$ARQ" 3<<<"$BACKUP_GPG_SENHA" | gunzip \
  | docker exec -i "$NOME" psql -q -v ON_ERROR_STOP=1 -U postgres -d restaurado >/dev/null

CONTA="SELECT string_agg(t||'='||c, ' ' ORDER BY t) FROM (SELECT table_name t, (xpath('/row/c/text()', query_to_xml('select count(*) c from '||table_name, false, true, '')))[1]::text::int c FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE') x"
ATUAL=$(docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "$CONTA")
REST=$(docker exec "$NOME" psql -U postgres -d restaurado -tAc "$CONTA")
echo "Atual:      $ATUAL"
echo "Restaurado: $REST"
if [ "$ATUAL" = "$REST" ]; then echo "RESTAURACAO_OK"; else echo "DIFERENCA (normal se houve uso entre o backup e o teste)"; fi
