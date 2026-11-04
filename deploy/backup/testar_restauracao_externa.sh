#!/usr/bin/env bash
# Teste de restauração A PARTIR DA CÓPIA EXTERNA (OCI Object Storage): baixa o backup mais recente do bucket,
# confere o sha256 gravado no envio e restaura num PostgreSQL temporário (testar_restauracao.sh), sem tocar no
# banco em uso. Usa um PAR de bucket SÓ DE LEITURA com listagem (BACKUP_PAR_LEITURA no backup.env).
# Agendado aos domingos, depois do teste local:
#   0 4 * * 0  $HOME/apps/estoqueack/deploy/backup/testar_restauracao_externa.sh >> $HOME/.local/state/estoqueack-backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/../.."
CONF=${ESTOQUEACK_BACKUP_CONF:-$HOME/.config/estoqueack/backup.env}
# shellcheck disable=SC1090
source "$CONF"
URL=${BACKUP_PAR_LEITURA:?defina BACKUP_PAR_LEITURA em $CONF}
URL=${URL%/}
PREFIXO=${1:-diario/}
ULTIMO=$(curl -fsS --max-time 60 "$URL/?prefix=$PREFIXO&limit=1000" | python3 -c '
import json, sys
objs = [o["name"] for o in json.load(sys.stdin).get("objects", []) if o["name"].endswith(".sql.gz.gpg")]
print(sorted(objs)[-1] if objs else "")')
[ -n "$ULTIMO" ] || { echo "$(date -Is) ERRO: nenhum backup em $PREFIXO no bucket"; exit 1; }
TMPD=$(mktemp -d); trap 'rm -rf "$TMPD"' EXIT
ARQ="$TMPD/$(basename "$ULTIMO")"
curl -fsS --max-time 600 -D "$TMPD/cab" "$URL/$ULTIMO" -o "$ARQ"
ESPERADO=$(grep -i '^opc-meta-sha256:' "$TMPD/cab" | tr -d '\r' | awk '{print $2}')
REAL=$(sha256sum "$ARQ" | cut -d' ' -f1)
[ -z "$ESPERADO" ] || [ "$ESPERADO" = "$REAL" ] || { echo "$(date -Is) ERRO: sha256 diferente em $ULTIMO"; exit 1; }
echo "$(date -Is) cópia externa baixada: $ULTIMO ($(du -h "$ARQ" | cut -f1)), sha256 conferido"
deploy/backup/testar_restauracao.sh "$ARQ" | sed 's/^/  /'
