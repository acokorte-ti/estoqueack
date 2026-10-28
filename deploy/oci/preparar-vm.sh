#!/usr/bin/env bash
# Prepara uma VM Ubuntu 22.04/24.04 (OCI Ampere A1, ARM64) para o EstoqueACK.
# Executar UMA vez, como usuário com sudo:  bash deploy/oci/preparar-vm.sh
set -euo pipefail

echo ">> Atualizando sistema e habilitando atualizações de segurança automáticas"
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl gnupg unattended-upgrades fail2ban ufw git
sudo dpkg-reconfigure -f noninteractive unattended-upgrades

echo ">> Instalando Docker Engine + Compose plugin"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo ">> Firewall do SO (a OCI também tem Security List — libere 22, 80, 443 lá)"
# Imagens Ubuntu da OCI vêm com regras iptables próprias; ufw cuida do básico.
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

echo ">> SSH: somente chave, sem senha e sem root"
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh || sudo systemctl restart sshd

echo ">> Pronto. Saia e entre de novo na sessão SSH para o grupo docker valer."
echo "   Depois: git clone https://github.com/acokorte-ti/estoqueack && cd estoqueack"
echo "           cp .env.example .env && nano .env && docker compose up -d --build"
