"""Hook PreToolUse (Bash) do EstoqueACK.

Bloqueia, antes de executar:
  1. git add -A / --all / . / -u e git commit -a (incidente de 2026-10-29: senha publicada no GitHub);
  2. git push --force na main;
  3. comandos que mostrariam segredos na conversa (.mega_ro, pass_bkp/, .github_token, .env).
     Exceção: usar .github_token dentro de `git -c http.extraHeader=...` (o valor não aparece).
     Arquivos de ../segredos/ podem ser copiados (scp), mas não abertos.

Recebe no stdin o JSON do Claude Code ({"tool_input": {"command": "..."}}).
Saída 2 + mensagem no stderr = bloqueia e explica ao Claude. Saída 0 = deixa passar.
"""

import json
import re
import sys


def motivo_bloqueio(cmd: str) -> str | None:
    # Analisa cada parte de comandos compostos (&&, ||, ;, |, quebra de linha).
    partes = re.split(r"&&|\|\||;|\||\n", cmd)
    for parte in partes:
        p = parte.strip()
        if re.search(r"\bgit\b", p):
            if re.search(r"\badd\b(\s+\S+)*?\s+(-A|--all|-u|--update|\.)(\s|$)", p):
                return (
                    "Bloqueado: no estoqueack não se usa 'git add -A/--all/-u/.'. "
                    "Adicione arquivo por arquivo e confira 'git status --short --untracked-files=all'."
                )
            if re.search(r"\bcommit\b.*\s-[a-zA-Z]*a", p) or re.search(r"\bcommit\b.*\s--all\b", p):
                return "Bloqueado: 'git commit -a' não é permitido. Adicione os arquivos explicitamente antes do commit."
            if re.search(r"\bpush\b.*(\s-f\b|\s--force\b|\s--force-with-lease\b)", p):
                return "Bloqueado: push forçado. Se for realmente necessário, peça ao Eduardo."

    # Segredos: qualquer leitura/impressão de arquivos sensíveis.
    if re.search(r"\.mega_ro|pass_bkp", cmd):
        return "Bloqueado: .mega_ro e pass_bkp/ têm credenciais e não podem ser lidos pela conversa."
    if ".github_token" in cmd and "http.extraHeader" not in cmd:
        return "Bloqueado: .github_token só pode ser usado dentro de 'git -c http.extraHeader=...', nunca impresso."
    leitores = r"\b(cat|type|more|less|head|tail|bat|Get-Content|gc|base64|xxd|od|strings)\b"
    if re.search(leitores + r"[^\n]*(^|[\s/\\'\"])\.env(\s|$|['\"])", cmd):
        return "Bloqueado: não imprimir .env (tem segredos). Para conferir uma variável, mostre só se ela existe (ex.: grep -c '^NOME=' .env)."
    if re.search(leitores + r"[^\n]*segredos[/\\]", cmd):
        return "Bloqueado: arquivos de ../segredos/ não podem ser abertos na conversa. Copie para o servidor com scp sem ler o conteúdo."
    return None


def main() -> int:
    try:
        dados = json.load(sys.stdin)
    except Exception:
        return 0  # entrada inesperada: não travar o trabalho
    cmd = (dados.get("tool_input") or {}).get("command") or ""
    motivo = motivo_bloqueio(cmd)
    if motivo:
        print(motivo, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
