#!/usr/bin/env bash
# Inspeção SOMENTE LEITURA de um servidor candidato a rodar o EstoqueACK. Não altera nada.
echo "== Sistema";   . /etc/os-release; echo "$PRETTY_NAME | $(uname -m) | kernel $(uname -r)"; uptime -p
echo "== Usuário";   echo "$(whoami) | grupos: $(id -nG)"
echo "== CPU/RAM";   echo "$(nproc) vCPU"; free -h | sed -n '1,2p'
echo "== Disco";     df -h / /var 2>/dev/null | sort -u
echo "== Rede";      ip -4 -o addr show | awk '{print $2, $4}'
echo "== Mega (10.0.0.235:1521)"
if timeout 5 bash -c 'cat < /dev/null > /dev/tcp/10.0.0.235/1521' 2>/dev/null; then echo "porta ABERTA"; else echo "porta FECHADA/sem rota"; fi
echo "== Docker";    docker --version 2>&1; docker compose version 2>&1 | head -1
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}' 2>&1 | head -30
echo "== Portas em escuta"; ss -ltnH 2>/dev/null | awk '{print $4}' | sort -u
echo "== Proxy/web";  for s in nginx caddy apache2 traefik postgresql; do systemctl is-active --quiet $s 2>/dev/null && echo "$s: ativo"; done
echo "== Python";    python3 --version 2>&1
echo "== Firewall";  (command -v ufw >/dev/null && echo "ufw instalado") ; ls /etc/iptables 2>/dev/null
