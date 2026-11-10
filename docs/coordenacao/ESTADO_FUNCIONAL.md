# Estado — FUNCIONAL

Atualizado: 2026-11-10 (respostas da auditoria, especificação v3.5)

## No ar

- **Especificação v3.5** (`estoqueack/docs/03_especificacao_funcional.md`).
  - **P19 a P25 fechadas** (§12); §9.1 sem "a confirmar" (CR8MOD é liga distinta).
  - **P22(a) reescrita** (§2.2, T13, §9, T23): material inteiro do RJ com previsto pela peça acabada e oscilação de **8 %**; 5 % segue no corte RJ e no Estoque Mega. P22(b): vale o SA mais recente.
  - **T07 passo 2:** sugestão por liga × bitola exata, Itu e RJ lado a lado; "Consumo nos dois estoques" (opção A proposta).
  - **Carga (§10.7 item 6, §10.8):** redondo exige RED/Ø; D6 chapas; planilha "Materia Prima Geral 05nov"; RETO do RJ em Itu sem lote-pai por candidato único; 1.2767 RETO sem origem.
- **Pedidos:** R045 (TÉCNICO) e R046 (FRONTEND) abertos. R040, R041, R042 já respondidos.
- **Arquivos fora do repo:** `carga/perguntas_fabiano_2026-11-10.txt` (7 pares do B04), `carga/perguntas_eduardo_2026-11-10.txt` (P26).

## Próximo

- Aplicar as respostas do Fabiano (7 pares) em §10.7 e avisar o TÉCNICO.
- Aplicar a resposta do Eduardo à P26 (consumo misto A ou B, avisos da peça inteira) e liberar o R045 item 5.
- Depois da implantação: lista do BLOCO 2 (OPs mal digitadas, SEM OP, cortes sem peso, solicitações sem lote), contêiner digitado errado, comentário com várias OPs, corte dividido entre contêineres, "PESO INICIAL" (B05 a B08).

## Aguardando

- **Eduardo:** P26. Avisar o Fabiano sobre o IPI do NCM 82089000 (se ainda não foi).
- **Fabiano:** 7 pares do B04.
- **TÉCNICO / FRONTEND:** R045, R046.

## Instruções permanentes desta frente

1. **A especificação oficial é `estoqueack/docs/03_especificacao_funcional.md`** (sem cópia na raiz). Ao editar, subir a versão no cabeçalho (v3.5 → v3.6…), explicando em uma frase o que mudou.
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
    - Próximo número de pedido: o maior R0xx em `PEDIDOS.md` + 1 (em 10/11 o último era R046).
