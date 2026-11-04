#!/usr/bin/env bash
# Ponta a ponta dos 5 caminhos (Parte C2) numa CÓPIA do banco da homologação (estoqueack_e2e), com o Mega real.
# Não toca no banco em uso. Uso no system-lab:  deploy/e2e/rodar_e2e.sh [OP_A OP_B OP_B2 OP_C]
# Relatório: ~/.local/state/estoqueack-e2e-AAAAMMDD-HHMM.json ; a cópia é apagada no fim (use MANTER=1 para manter).
set -euo pipefail
cd "$HOME/apps/estoqueack"
REL="$HOME/.local/state/estoqueack-e2e-$(date +%Y%m%d-%H%M).json"
echo "1/3 copiando o banco da homologação para estoqueack_e2e..."
docker compose exec -T db sh -c 'dropdb --if-exists -U "$POSTGRES_USER" estoqueack_e2e && createdb -U "$POSTGRES_USER" estoqueack_e2e && pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | psql -q -U "$POSTGRES_USER" estoqueack_e2e >/dev/null'
echo "2/3 rodando os 5 caminhos..."
set +e
docker compose exec -T api sh -c 'DATABASE_URL="${DATABASE_URL%/*}/estoqueack_e2e" python -m app.jobs.e2e_caminhos "$@"' _ "$@" > "$REL"
rc=$?
set -e
if [ "${MANTER:-0}" != "1" ]; then
  echo "3/3 apagando a cópia..."
  docker compose exec -T db sh -c 'dropdb --if-exists -U "$POSTGRES_USER" estoqueack_e2e'
fi
python3 - "$REL" <<'EOF'
import json, sys
r = json.load(open(sys.argv[1]))
print("OPs:", r.get("dados", {}).get("ops"), "lotes:", r.get("dados", {}).get("lotes"))
for k, v in r["caminhos"].items():
    print(f"  {k:3s} {'OK ' if v.get('ok') else 'FALHOU'} {v.get('erro', '')} {v.get('situacao_final', '')}")
print("  conferência:", r["conferencia"])
print("  SA com confirmação simulada:", r["sa_confirmacao_simulada"])
print("RESULTADO:", "OK" if r["ok"] else "FALHOU")
EOF
echo "relatório completo: $REL"
exit $rc
