#!/usr/bin/env bash
# Atualiza SÓ o frontend (container web) na homologação. API e banco não reiniciam.
# Uso (1 conexão SSH): ssh system-lab 'bash -s' < scripts/deploy_web.sh
set -e
cd ~/apps/estoqueack
git pull --ff-only 2>&1 | tail -3
git log --oneline -1
docker compose up -d --build web 2>&1 | tail -6
sleep 3
docker compose ps --format 'table {{.Service}}\t{{.Status}}'
echo '--- testes'
curl -s -o /dev/null -w 'index %{http_code}\n' http://127.0.0.1:8090/
curl -s -o /dev/null -w 'logo %{http_code} %{content_type}\n' http://127.0.0.1:8090/logo-acokorte.png
curl -s http://127.0.0.1:8090/ | grep -o 'assets/index-[^"]*' || true
curl -s -o /dev/null -w 'api %{http_code}\n' http://127.0.0.1:8090/api/saude
