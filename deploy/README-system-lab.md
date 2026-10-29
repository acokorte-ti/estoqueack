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

## 4. Atualizar a versão

```bash
cd ~/apps/estoqueack && git pull && docker compose up -d --build
```

Isso fica temporário até o runner do GitHub Actions automatizar o deploy.
