#!/usr/bin/env bash
# Agendador do EstoqueACK (sincronização com o Mega 06:00/13:00 e verificação de SA a cada 30 min).
# Roda a cada 5 min pelo cron do usuário ubuntu no system-lab; quem decide se é hora é o próprio app
# (app/jobs/agendador.py, parâmetros SYNC_MEGA_HORARIOS e VERIFICACAO_SA_MIN da T23).
#   */5 * * * * $HOME/apps/estoqueack/deploy/cron/estoqueack-agendador.sh >> $HOME/.local/state/estoqueack-agendador.log 2>&1
set -u
cd "$HOME/apps/estoqueack" || exit 1
# durante um deploy o container pode estar sendo recriado: tenta na próxima rodada
docker compose ps --status running --services 2>/dev/null | grep -qx api || exit 0
saida=$(timeout 600 docker compose exec -T api python -m app.jobs.agendador 2>&1)
rc=$?
[ "$saida" = "{}" ] && exit 0      # nada vencido: não polui o log
echo "$(date -Iseconds) rc=$rc $saida"
