#!/bin/bash
# Acesso ao EstoqueACK por CERTIFICADO DE CLIENTE, além dos IPs da empresa (2026-11-23).
#
# Por quê: o IP de Barra Mansa é dinâmico; quando muda, o RJ recebe 403. Com isto o site abre se o IP for da
# empresa (ips-estoqueack.conf, como antes) OU se o computador tiver um certificado emitido por esta AC.
#
# Uso, no system-lab, numa sessão interativa (pede a senha do sudo e a senha do .p12, que não aparecem na tela):
#   sudo bash ~/acesso_certificado.sh <nome>      ex.: sudo bash ~/acesso_certificado.sh rj-barra-mansa
# Na 1ª vez cria a AC e liga a regra no nginx; nas próximas só emite mais um certificado (outro PC/celular).
# Sai em ~<usuário>/<nome>.p12 (copiar para ../segredos/ e apagar do servidor). Validade: 3 anos.
# Revogar tudo (PC perdido): apagar /etc/nginx/estoqueack-ca/ca.* e emitir de novo os certificados que ficam.
set -euo pipefail

NOME="${1:?informe o nome do certificado, ex.: rj-barra-mansa}"
[[ "$NOME" =~ ^[a-z0-9-]+$ ]] || { echo "Nome só com letras minúsculas, números e hífen."; exit 2; }
[ "$(id -u)" = 0 ] || { echo "Rode com sudo."; exit 2; }
AC=/etc/nginx/estoqueack-ca
SITE=/etc/nginx/sites-available/estoqueack
DONO="${SUDO_USER:-ubuntu}"
SAIDA="/home/$DONO/$NOME.p12"
IP_PUBLICO=204.216.137.171
URL=https://estoque.acokorte.com.br/entrar

umask 077
mkdir -p "$AC"

# 1) Autoridade certificadora própria (só na 1ª vez; a chave nunca sai do servidor)
if [ ! -f "$AC/ca.key" ]; then
  openssl genrsa -out "$AC/ca.key" 4096 2>/dev/null
  openssl req -x509 -new -key "$AC/ca.key" -sha256 -days 3650 \
    -subj "/O=AcoKorte/CN=EstoqueACK acesso externo" -out "$AC/ca.crt"
  echo "AC criada em $AC"
fi
chmod 644 "$AC/ca.crt"

# 2) Certificado do cliente (uso: autenticação de cliente)
openssl genrsa -out "$AC/$NOME.key" 2048 2>/dev/null
openssl req -new -key "$AC/$NOME.key" -subj "/O=AcoKorte/CN=$NOME" -out "$AC/$NOME.csr"
EXT=$(mktemp)
printf 'basicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=clientAuth\n' > "$EXT"
openssl x509 -req -in "$AC/$NOME.csr" -CA "$AC/ca.crt" -CAkey "$AC/ca.key" -CAcreateserial -days 1095 -sha256 \
  -extfile "$EXT" -out "$AC/$NOME.crt" 2>/dev/null
rm -f "$EXT" "$AC/$NOME.csr"

# 3) Arquivo .p12 para instalar no Windows (3DES/SHA1: abre em qualquer Windows 10/11 e no Android)
while true; do
  read -rsp "Senha para o arquivo $NOME.p12 (o colaborador digita ao instalar): " S1; echo
  read -rsp "Repita a senha: " S2; echo
  [ -n "$S1" ] && [ "$S1" = "$S2" ] && break
  echo "As senhas não conferem (ou ficaram vazias). De novo."
done
printf '%s' "$S1" | openssl pkcs12 -export -inkey "$AC/$NOME.key" -in "$AC/$NOME.crt" -certfile "$AC/ca.crt" \
  -name "EstoqueACK $NOME" -keypbe PBE-SHA1-3DES -certpbe PBE-SHA1-3DES -macalg sha1 -passout stdin -out "$SAIDA"
unset S1 S2
chown "$DONO:$DONO" "$SAIDA"
chmod 600 "$SAIDA"

# 4) Regra no nginx (só na 1ª vez): satisfy any = IP da empresa OU certificado válido desta AC
if ! grep -q "_acesso_certificado" "$SITE"; then
  cp -p "$SITE" "$SITE.bak.$(date +%Y%m%d)"
  BLOCO=$(mktemp)
  cat > "$BLOCO" <<'FIM'
    # Acesso (2026-11-23): IP da empresa (ips-estoqueack.conf) OU certificado de cliente da AçoKorte, para quem
    # acessa de fora ou de IP que muda (RJ). Ver deploy/nginx-host/acesso_certificado.sh
    ssl_client_certificate /etc/nginx/estoqueack-ca/ca.crt;
    ssl_verify_client optional;
    ssl_verify_depth 1;
    satisfy any;
    include /etc/nginx/snippets/ips-estoqueack.conf;
    auth_request /_acesso_certificado;
    location = /_acesso_certificado {
        internal;
        if ($ssl_client_verify = SUCCESS) { return 204; }
        return 403;
    }
FIM
  awk -v bloco="$BLOCO" '/^[[:space:]]*include \/etc\/nginx\/snippets\/ips-estoqueack\.conf;/ {
      while ((getline l < bloco) > 0) print l; close(bloco); next } { print }' "$SITE" > "$SITE.novo"
  rm -f "$BLOCO"
  if [ "$(grep -c '_acesso_certificado' "$SITE.novo")" != 2 ]; then
    rm -f "$SITE.novo"
    echo "ERRO: não achei a linha do ips-estoqueack.conf no $SITE. Nada foi mudado no nginx."; exit 1
  fi
  cat "$SITE.novo" > "$SITE"
  rm -f "$SITE.novo"
  if nginx -t 2>/dev/null; then
    systemctl reload nginx
    echo "nginx: regra do certificado ligada."
  else
    cp -p "$SITE.bak.$(date +%Y%m%d)" "$SITE"
    nginx -t
    echo "ERRO: o nginx recusou a configuração nova; voltei a anterior. Nada mudou no site."; exit 1
  fi
  sleep 2
fi

# 5) Conferência pelo IP público do servidor (que não está na lista): sem certificado 403, com certificado 200
SEM=$(curl -s -o /dev/null -w '%{http_code}' --resolve "estoque.acokorte.com.br:443:$IP_PUBLICO" "$URL" || true)
COM=$(curl -s -o /dev/null -w '%{http_code}' --resolve "estoque.acokorte.com.br:443:$IP_PUBLICO" \
      --cert "$AC/$NOME.crt" --key "$AC/$NOME.key" "$URL" || true)
echo "Conferência de fora da lista de IPs: sem certificado = $SEM (esperado 403); com certificado = $COM (esperado 200)"

# a chave do cliente só fica dentro do .p12
shred -u "$AC/$NOME.key" 2>/dev/null || rm -f "$AC/$NOME.key"
echo "Pronto: $SAIDA (válido por 3 anos)."
