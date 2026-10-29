#!/usr/bin/env bash
# Deploy automático "por puxada" (pull) do EstoqueACK no system-lab.
# O servidor verifica a branch main no GitHub e só publica commits com o CI 100 % verde.
# Nada entra no servidor por SSH. Agendado no cron do usuário ubuntu a cada 5 minutos:
#   */5 * * * * $HOME/apps/estoqueack/deploy/auto/auto_deploy.sh >> $HOME/.local/state/estoqueack-deploy.log 2>&1
#
# Regras:
#  - backend/ ou backend do compose mudou  → backup do banco + rebuild do container api (migrações rodam na subida)
#  - frontend/, Dockerfile.web, nginx do container → rebuild só do container web
#  - deploy/nginx-host/ mudou → NÃO aplica (precisa sudo); só registra "aplicar manualmente"
#  - falhou o teste depois de subir → volta o código para o commit anterior e reconstrói
# Migrações de banco devem ser compatíveis com a versão anterior do código (regra do projeto).
set -uo pipefail
REPO=acokorte-ti/estoqueack
DIR=$HOME/apps/estoqueack
ESTADO=$HOME/.local/state
CONF=$HOME/.config/estoqueack/deploy.env           # opcional: GITHUB_TOKEN_LEITURA=... (se o repo virar privado)
mkdir -p "$ESTADO"
exec 9>"$ESTADO/estoqueack-deploy.lock"; flock -n 9 || exit 0
[ -f "$CONF" ] && source "$CONF"
log() { echo "$(date -Is) $*"; }
cd "$DIR" || exit 1

git fetch -q origin main || { log "ERRO git fetch"; exit 1; }
ATUAL=$(git rev-parse HEAD); NOVO=$(git rev-parse origin/main)
[ "$ATUAL" = "$NOVO" ] && exit 0
[ "$(cat "$ESTADO/estoqueack-deploy.recusado" 2>/dev/null)" = "$NOVO" ] && exit 0

# --- CI do commit novo precisa estar concluído e verde ---
AUTH=(); [ -n "${GITHUB_TOKEN_LEITURA:-}" ] && AUTH=(-H "Authorization: Bearer $GITHUB_TOKEN_LEITURA")
CI=$(curl -fsS "${AUTH[@]}" -H "Accept: application/vnd.github+json" \
     "https://api.github.com/repos/$REPO/commits/$NOVO/check-runs?per_page=50" | python3 -c '
import json, sys
runs = json.load(sys.stdin).get("check_runs", [])
if not runs: print("PENDENTE"); sys.exit()
if any(r["status"] != "completed" for r in runs): print("PENDENTE"); sys.exit()
print("VERDE" if all(r["conclusion"] in ("success", "skipped") for r in runs) else "VERMELHO")') || CI=ERRO
case "$CI" in
  PENDENTE) exit 0 ;;
  VERDE) ;;
  *) log "commit ${NOVO:0:7} NÃO publicado: CI=$CI"; echo "$NOVO" > "$ESTADO/estoqueack-deploy.recusado"; exit 0 ;;
esac

MUDOU=$(git diff --name-only "$ATUAL" "$NOVO")
SERV=()
grep -qE '^(backend/|\.env\.example$)' <<<"$MUDOU" && SERV+=(api)
grep -qE '^(frontend/|deploy/Dockerfile\.web$|deploy/nginx-(container|seguranca)\.conf$)' <<<"$MUDOU" && SERV+=(web)
grep -qE '^docker-compose\.yml$' <<<"$MUDOU" && SERV=(api web db)
grep -qE '^deploy/nginx-host/' <<<"$MUDOU" && log "AVISO ${NOVO:0:7}: deploy/nginx-host mudou — aplicar manualmente com sudo (ver deploy/README-system-lab.md)"

log "publicando ${ATUAL:0:7} → ${NOVO:0:7} ($(git log -1 --format=%s "$NOVO" | cut -c1-80)); serviços: ${SERV[*]:-nenhum}"
if [[ " ${SERV[*]} " == *" api "* ]]; then
  deploy/backup/backup.sh || { log "ERRO no backup pré-deploy — publicação cancelada"; exit 1; }
fi
git merge -q --ff-only "$NOVO" || { log "ERRO: árvore local divergente, nada publicado"; exit 1; }
[ ${#SERV[@]} -eq 0 ] && { log "ok (sem serviço para reconstruir)"; exit 0; }

testar() {
  for _ in $(seq 1 30); do
    if curl -fsS -o /dev/null http://127.0.0.1:8090/ && curl -fsS http://127.0.0.1:8090/api/saude | grep -q '"ok"'; then return 0; fi
    sleep 4
  done
  return 1
}

if docker compose up -d --build "${SERV[@]}" >"$ESTADO/estoqueack-deploy-build.log" 2>&1 && testar; then
  log "OK ${NOVO:0:7} no ar"
  echo "$NOVO" > "$ESTADO/estoqueack-deploy.ultimo_ok"
else
  log "FALHOU ${NOVO:0:7} — voltando para ${ATUAL:0:7} (ver estoqueack-deploy-build.log)"
  echo "$NOVO" > "$ESTADO/estoqueack-deploy.recusado"
  git reset -q --hard "$ATUAL"
  docker compose up -d --build "${SERV[@]}" >>"$ESTADO/estoqueack-deploy-build.log" 2>&1 && testar \
    && log "rollback OK: ${ATUAL:0:7} no ar" || log "ERRO GRAVE: rollback não respondeu — intervenção manual"
fi
