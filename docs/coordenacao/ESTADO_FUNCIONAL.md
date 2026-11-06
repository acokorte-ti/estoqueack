# Estado — FUNCIONAL

Atualizado: 2026-11-04 (respostas do Fabiano ao BLOCO 1)

## No ar

- **Especificação v3.3** (`estoqueack/docs/03_especificacao_funcional.md`, cópia na raiz).
  - **§10.7 (novo):** regras da carga que o Fabiano definiu.
    - Paridade sem múltiplo.
    - Material do RJ sem igual em Itu fica sem código Mega, e as medidas não se juntam.
    - Quando os totais divergem, vale a ESTOQUE 2026.
    - Código do Mega fora do catálogo entra se teve movimento no kardex nos últimos 2 anos.
    - 13 restrições entram com "estou ciente"; "RESERVADO CPR" (2) não entra.
    - Solicitações ativas: 4 concluídas, 8 canceladas, 6 mantidas.
  - **R024 fechado:** perda de corte normal até 6 % do material usado (T13, §9, T23).
  - **Da v3.2:** decisões de 04/11 (T16 mínima, impressão da T09, sem data, conferência semanal, §10.6), R037 e R024 itens 2–5.
- **BLOCO 1 respondido:** `carga/revisao_bloco1_fabiano_RESPONDIDO.xlsx`. R032 respondido; a recarga foi pedida ao TÉCNICO no **R038**.

## Próximo

- Conferir a lista de códigos que entraram pelo kardex, quando o TÉCNICO mandar (R038 item 2), e a prévia da recarga.
- Depois da implantação: lista do BLOCO 2 (OPs mal digitadas, SEM OP, cortes sem peso, solicitações sem lote).
- Roteiro de aceite com o BANCO E TESTES, se for pedido.

## Aguardando

- **R038 (TÉCNICO):** recarga da T25 com as respostas do BLOCO 1.
- **Eduardo:** avisar o Fabiano sobre o IPI do NCM 82089000 e confirmar a P06.

## Em andamento / não commitado (2026-11-05, migração para o Claude Code)

- **Tudo do FUNCIONAL está commitado e no `main`.** Último commit: `eb9b59b`, especificação v3.3 com o R024 fechado e o RESERVADO CPR fora da carga.
- **Fora do repositório, de propósito:**
  - pasta `coordenacao\`;
  - cópias na raiz `03_Especificacao_Funcional.md` e `04_Conferencia_Planilhas_x_Fluxo.md`, idênticas às de `estoqueack/docs/`;
  - `carga/revisao_bloco1_fabiano.xlsx` e `carga/revisao_bloco1_fabiano_RESPONDIDO.xlsx`, que têm dados da empresa e por isso não vão para o repositório público.
- **Em andamento:** nada. Aguardando o R038 (recarga com as respostas do BLOCO 1).

## Instruções permanentes desta frente

1. **A especificação oficial é `estoqueack/docs/03_especificacao_funcional.md`.** Depois de editar, copiar para a raiz (`03_Especificacao_Funcional.md`) e subir a versão no cabeçalho (v3.3 → v3.4…), explicando em uma frase o que mudou.
2. **Git:**
   - Commit e push pelo **PowerShell do Windows**, porque o git do sandbox trava em `index.lock`.
   - Usar `git add` só do arquivo da especificação. Nunca `-A`: há arquivos de outros chats sem commit na mesma pasta.
   - Push com o token de `estoqueack\.github_token`, passado via `-c http.extraHeader` e nunca gravado no `git config`.
   - Antes do commit, `git fetch` + `git status`.
3. **Regra de negócio só vale se estiver na especificação.**
   - Decisão do Eduardo, do Matheus ou do Fabiano vai sempre para a especificação **e** para `DECISOES.md`, citando quem decidiu e a data.
   - Ponto que é escolha minha fica marcado como proposta e é perguntado.
   - Bloquear ou só avisar, valores de tolerância, quem pode fazer o quê: **perguntar ao Eduardo** (AskUserQuestion com opções), nunca decidir sozinho.
4. **Antes de afirmar algo tirado das planilhas,** cruzar por chave composta (OP + contêiner + **data**), separar o período recente do histórico e mostrar 2–3 exemplos. Em 30/10, um cruzamento só por OP inflou o "NF × COP", de 11 para 23 COPs. Se errar, corrigir o documento e dizer o que mudou.
5. **Ler com atenção o que o Eduardo e o Fabiano escrevem nas planilhas de revisão.**
   - Coluna amarela em branco = concorda com a proposta.
   - "Não sei do que se trata" = **descartar**, e não virar pendência para outra pessoa. Isso já foi corrigido uma vez: o RESERVADO CPR.
   - Se uma resposta parecer copiada de outra linha, aplicar a regra geral que o Fabiano deu e avisar.
6. **Conhecimento do negócio que o Fabiano já corrigiu:**
   - Medidas parecidas (21x202, 21x203, 21x204; 22x510 × 22x610) são materiais **diferentes**: nunca sugerir juntar.
   - Código de múltiplo ("…MULT.") nunca se liga a material comum.
   - "IMP" no nome = importado.
   - A8 MOD ≠ A8 na solicitação.
7. **Sem prazo.** Não escrever "até dia X" nem "alvo DD/MM" (README, regra 7).
8. **Respostas ao Eduardo:**
   - Em português, curtas, com a decisão que ele precisa tomar escrita como pergunta pronta, que ele possa repassar ao Matheus ou ao Fabiano.
   - Ele responde direto no chat ("Até 6%"): basta registrar, sem pedir arquivo.
   - Pedidos da COORDENAÇÃO pedem resposta em até 5 linhas.
9. **Quando eu gerar uma lista para o Fabiano revisar:** Excel com aba "Leia-me", colunas amarelas só para ele preencher, sugestão minha em coluna separada e o arquivo em `carga/` (fora do repositório).
10. **Pedidos (`PEDIDOS.md`):**
    - Ao responder, mudar o status e escrever no máximo ~5 linhas, sem quebra de linha na célula. O detalhe vai na especificação ou neste ESTADO.
    - Próximo número de pedido: o maior R0xx em `PEDIDOS.md` + 1 (em 05/11 o último era R039).
