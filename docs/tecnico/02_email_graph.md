# E-mail do EstoqueACK via Microsoft Graph

Criado em 2026-10-30 pelo TÉCNICO. Uso atual: link do "Esqueci minha senha". Uso futuro: alertas (backup, site fora do ar).

## Por que Graph e não SMTP

A Microsoft está retirando o login por usuário e senha (Basic Auth) no SMTP AUTH do Exchange Online. Com o Graph:

- nenhuma senha de caixa fica no servidor; o sistema usa um **app** do Entra ID (client credentials);
- o app só consegue enviar **como `estoque@acokorte.com.br`**, por causa da restrição do Exchange (RBAC for Applications). Ele não lê e-mail e não envia como outras pessoas;
- se o segredo vazar, basta apagá-lo no portal; a caixa não é afetada.

A API usa o Graph quando as 4 variáveis `GRAPH_*` estão preenchidas. Senão, usa o SMTP (`SMTP_*`). Se nenhum dos dois estiver configurado, só registra um aviso no log. Código: `backend/app/services/email.py`.

## Passo a passo (Eduardo, admin do M365)

### 1. Criar a caixa compartilhada

Exchange admin center (https://admin.exchange.microsoft.com) → **Recipients → Mailboxes → Add a shared mailbox**:

- Display name: `EstoqueACK`
- Email: `estoque@acokorte.com.br`

A caixa compartilhada não consome licença e não tem senha. Para ver os e-mails enviados, dê a você mesmo permissão de "Read and manage" nela.

### 2. Registrar o app

Entra admin center (https://entra.microsoft.com) → **Identity → Applications → App registrations → New registration**:

- Name: `EstoqueACK - envio de e-mail`
- Supported account types: **Accounts in this organizational directory only**
- Redirect URI: deixe em branco

Depois de criar, anote o seguinte da página **Overview**:

- **Application (client) ID** → `GRAPH_CLIENT_ID`
- **Directory (tenant) ID** → `GRAPH_TENANT_ID`

**Não** adicione permissões em "API permissions". O `Mail.Send` dado ali vale para **todas** as caixas da empresa, e a restrição do passo 4 não teria efeito.

### 3. Criar o segredo

No app → **Certificates & secrets → Client secrets → New client secret**:

- Description: `system-lab`
- Expires: **24 months** (anote a data para renovar antes dela)

Copie o **Value** na hora (ele só aparece uma vez) → `GRAPH_CLIENT_SECRET`. **Não cole o segredo no chat nem em arquivo dentro da pasta do projeto.** Ele vai direto para o servidor no passo 5.

### 4. Liberar o envio só pela caixa estoque@ (Exchange Online PowerShell)

Primeiro pegue o **Object ID** do app em **Enterprise applications** (não em App registrations): Entra → Identity → Applications → **Enterprise applications** → `EstoqueACK - envio de e-mail` → Object ID.

Num PowerShell do Windows (como administrador, uma vez só):

```powershell
Install-Module ExchangeOnlineManagement -Scope CurrentUser
Connect-ExchangeOnline

$AppId    = "<Application (client) ID>"
$ObjectId = "<Object ID da Enterprise application>"

New-ServicePrincipal -AppId $AppId -ObjectId $ObjectId -DisplayName "EstoqueACK - envio de e-mail"

New-ManagementScope -Name "EstoqueACK - so caixa estoque" `
  -RecipientRestrictionFilter "PrimarySmtpAddress -eq 'estoque@acokorte.com.br'"

New-ManagementRoleAssignment -App $AppId -Role "Application Mail.Send" `
  -CustomResourceScope "EstoqueACK - so caixa estoque"

# Conferência: deve dar InScope = True para a estoque@ e False para outra caixa
Test-ServicePrincipalAuthorization -Identity $AppId -Resource estoque@acokorte.com.br
Test-ServicePrincipalAuthorization -Identity $AppId -Resource eduardo.macedo@acokorte.com.br
```

A permissão pode levar de 30 min a 2 h para valer. Até lá, o Graph responde 403 (`ErrorAccessDenied`).

### 5. Gravar no servidor (system-lab)

Depois de o código novo estar publicado (deploy automático após o push), em `ssh system-lab`. O segredo é digitado sem aparecer na tela e não fica no histórico:

```bash
cd ~/apps/estoqueack
read -rp "Tenant ID: " T; read -rp "Client ID: " C; read -rsp "Client secret: " S; echo
cp -p .env ".env.bak.$(date +%F-%H%M)"
sed -i '/^GRAPH_/d' .env
printf 'GRAPH_TENANT_ID=%s\nGRAPH_CLIENT_ID=%s\nGRAPH_CLIENT_SECRET=%s\nGRAPH_REMETENTE=estoque@acokorte.com.br\n' "$T" "$C" "$S" >> .env
unset S T C
chmod 600 .env
docker compose up -d --force-recreate api
```

### 6. Testar

```bash
cd ~/apps/estoqueack
docker compose exec api python -m app.services.email eduardo.macedo@acokorte.com.br
```

Deve mostrar `modo: graph` e `e-mail 'EstoqueACK: teste de envio' enviado`. Depois disso, teste o fluxo real pelo site ("Esqueci minha senha" com o seu login).

| Erro no log | Causa provável |
|---|---|
| `token do Entra recusado (HTTP 401, invalid_client)` | segredo errado ou expirado (passo 3) |
| `token do Entra recusado (HTTP 400, invalid_request)` / `unauthorized_client` | tenant ID ou client ID trocados |
| `Graph recusou o envio (HTTP 403, ErrorAccessDenied)` | passo 4 não feito, ainda propagando, ou `GRAPH_REMETENTE` diferente da caixa liberada |
| `Graph recusou o envio (HTTP 404, ErrorInvalidUser)` / `MailboxNotEnabledForRESTAPI` | caixa estoque@ não existe ou ainda está sendo criada |

## Manutenção

- **Renovar o segredo** antes de vencer: criar um novo no portal, repetir o passo 5 e só depois apagar o antigo.
- **Revogar em emergência:** apagar o segredo no portal (Certificates & secrets). O envio para na hora.
- Os logs da API registram só o código do erro, nunca o segredo nem o token.
