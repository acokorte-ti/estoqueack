# ADR 0002: Autenticação local (sem Microsoft 365)

Status: aceito em 28/10/2026, por decisão do Eduardo.

## Decisão

Os usuários e as senhas ficam no banco do sistema.

- As senhas são guardadas com hash **Argon2id**.
- A sessão fica no servidor. O navegador recebe só um token aleatório num cookie `HttpOnly; Secure; SameSite=Strict`, e o banco guarda apenas o hash SHA-256 desse token.
- A proteção CSRF usa double-submit: um cookie `ack_csrf` e o header `X-CSRF-Token`.
- Depois de 5 falhas seguidas, a conta é bloqueada por 15 minutos.
- A mensagem de erro é a mesma para "usuário não existe" e "senha errada".
- A senha é temporária no primeiro acesso, e a troca é obrigatória.
- Ao trocar ou redefinir a senha, todas as outras sessões são revogadas.
- Todo login, falha e logout é registrado na auditoria.

## Futuro

Um segundo fator (TOTP) pode ser adicionado sem mudar o modelo.
