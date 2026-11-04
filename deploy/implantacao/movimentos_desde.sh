#!/usr/bin/env bash
# ROLLBACK (voltar às planilhas): lista tudo o que foi lançado NO SISTEMA desde a liberação, para o Fabiano e o
# Marcelo repassarem às planilhas. Só leitura. Gera CSV (separador ;, decimal com vírgula) em ~/estoqueack-carga/rollback/.
# Uso: deploy/implantacao/movimentos_desde.sh "2026-11-13 08:00"
set -euo pipefail
cd "$(dirname "$0")/../.."
DESDE=${1:?informe a data/hora da liberação, ex. "2026-11-13 08:00"}
[[ "$DESDE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}$ ]] || { echo "formato: AAAA-MM-DD HH:MM"; exit 2; }
PSQL=${PSQL_CMD:-docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -q -f -'}
DIR=${ROLLBACK_DIR:-$HOME/estoqueack-carga/rollback}; mkdir -p "$DIR"; chmod 700 "$DIR"
ARQ="$DIR/lancado_no_sistema_desde_$(date +%Y%m%d_%H%M).csv"
eval "$PSQL" > "$ARQ" <<SQL
COPY (
  SELECT to_char(m.criado_em AT TIME ZONE 'America/Sao_Paulo', 'DD/MM/YYYY HH24:MI') AS quando,
         u.login AS quem, m.tipo, l.codigo AS lote, c.codigo AS conteiner, i.descricao AS material,
         CASE WHEN l.planta_fiscal = 'RJ' AND l.local_fisico = 'RJ' THEN 'RJ no Rio'
              WHEN l.planta_fiscal = 'RJ' THEN 'RJ em Itu' ELSE 'Estoque Mega' END AS estoque,
         i.codigo_mega, replace(m.kg::text, '.', ',') AS kg, m.pecas, m.op, m.cop_numero, m.sa_codigo,
         m.documento, m.justificativa
    FROM movimento m
    JOIN lote l ON l.id = m.lote_id
    JOIN item_mp i ON i.id = l.item_mp_id
    LEFT JOIN conteiner c ON c.id = l.conteiner_id
    LEFT JOIN usuario u ON u.id = m.usuario_id
   WHERE m.criado_em >= (TIMESTAMP '$DESDE') AT TIME ZONE 'America/Sao_Paulo'
   ORDER BY m.criado_em
) TO STDOUT WITH (FORMAT csv, HEADER, DELIMITER ';');
SQL
chmod 600 "$ARQ"
echo "$(($(wc -l < "$ARQ") - 1)) movimento(s) lançados desde $DESDE → $ARQ"
