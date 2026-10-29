# Implantação no system-lab (homologação)

O servidor é Ubuntu 22.04 ARM64 (OCI), IP 204.216.137.171 / 172.16.0.249. O nginx do host atende os domínios com Let's Encrypt e encaminha cada um para uma porta local. O EstoqueACK usa a porta **127.0.0.1:8090**.

## 1. Aplicação (usuário `ubuntu`, sem sudo)

```bash
git clone https://github.com/acokorte-ti/estoqueack ~/apps/estoqueack
cd ~/apps/estoqueack
cp .env.example .env    # ajuste senhas e chaves (ou use o gerador abaixo)
docker compose up -d --build
curl -s http://127.0.0.1:8090/api/saude   # {"status":"ok"}
```

Gerador de segredos:

```bash
python3 -c "import secrets;print(secrets.token_urlsafe(48))"
```

## 2. DNS

Crie um registro **A** de `estoque.acokorte.com.br` apontando para **204.216.137.171**.

## 3. nginx e certificado (como root, uma vez)

```bash
# O site padrão da porta 80 (http-porta80) já atende /.well-known/acme-challenge em /var/www/certbot
sudo certbot certonly --webroot -w /var/www/certbot -d estoque.acokorte.com.br --non-interactive --agree-tos
sudo cp ~/apps/estoqueack/deploy/nginx-host/estoque.acokorte.com.br.conf /etc/nginx/sites-available/estoqueack
sudo ln -s /etc/nginx/sites-available/estoqueack /etc/nginx/sites-enabled/estoqueack
sudo nginx -t && sudo systemctl reload nginx   # nunca recarregar se o teste falhar
```

A renovação do certificado é automática, pelo timer do certbot que os outros sites já usam.

## 4. Atualizações: deploy automático

O cron do usuário `ubuntu` roda `~/.local/bin/estoqueack-auto-deploy.sh` (cópia de `deploy/auto/auto_deploy.sh`, que se reinstala a cada publicação) a cada 5 minutos. Ele verifica a branch `main` e **só publica commits com o CI todo verde**:

- Mudanças no backend: faz backup e reconstrói o container `api`.
- Mudanças no frontend: reconstrói só o container `web`.
- Se o teste depois da publicação falhar, volta sozinho para a versão anterior.
- Mudanças em `deploy/nginx-host/` **não** são aplicadas automaticamente, porque precisam de sudo.

O log fica em `~/.local/state/estoqueack-deploy.log`.

Optou-se por esse modelo "de puxada" em vez de um *runner* do GitHub no servidor porque o repositório é público, e o GitHub desaconselha runners próprios em repositórios públicos.

Quando for preciso publicar só o frontend na mão: `ssh system-lab 'bash -s' < scripts/deploy_web.sh`.
