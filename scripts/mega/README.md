# Ferramentas de mapeamento do Mega

1. `01_criar_usuario_leitura.sql`: o DBA cria o usuário `estoqueack_ro`, somente leitura, com um perfil de limites (sessões, CPU e tempo ocioso).
2. `descobrir_mega.py`: procura no dicionário do Oracle as tabelas reais de produto, saldo, OP, SA e movimentos, a partir de valores conhecidos das planilhas. Gera `relatorio_mega_*.md`.

As credenciais ficam num arquivo local `.mega_ro` com 3 linhas (`dsn`, `usuário`, `senha`), na raiz de `estoqueack`. Esse arquivo é **ignorado pelo Git**.

O relatório gerado também não deve ir para o repositório. Os nomes de tabela encontrados vão para `docs/integracao_mega.md`.
