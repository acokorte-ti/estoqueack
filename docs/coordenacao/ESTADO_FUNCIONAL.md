# Estado — FUNCIONAL

Atualizado: 2026-11-06 (correção da auditoria, especificação v3.4)

## No ar

- **Especificação v3.4** (`estoqueack/docs/03_especificacao_funcional.md`; a cópia da raiz deixou de ser atualizada).
  - **T15 mínima na F1** (Caminho C passo 1): "Criar lote" ou "Não é entrada"; a T16 mínima mostra a diferença explicada. Resumo F1 x F1.1 no §4.2.
  - **Aba "RETO por origem" na T04** (F1): Liga → bitola → contêiner, "sem origem" separado, totais, Excel. T19 completo continua F1.1.
  - **§10.8:** a carga quebra o RETO do RJ em Itu por bitola de origem, marca tudo como RETO e lê Ø/RED/ROUND como redondo.
  - **§9.1:** 4 regras que só estavam no código, marcadas "a confirmar". **T25 é linha de comando.** P10 detalhado (Painel, T05, T14).
  - **Perguntas P19 a P25** para o Eduardo (todas com proposta padrão).
- **Pedidos:** R040 (TÉCNICO), R041 (FRONTEND), R042 (BANCO E TESTES), todos ABERTO.
- **Texto para o Fabiano:** `carga/texto_fabiano_auditoria_2026-11-06.md` (fora do repo): D2 Ø90 ↔ 95199, 7 pares do B04, D2 36X510 no DC53 RETO, bitola das 6 parcelas do 1.2767.
- **Antes (v3.3):** §10.7 com as respostas do BLOCO 1, R024 fechado (perda de corte até 6 %), RESERVADO CPR fora da carga.

## Próximo

- Ler as respostas do Fabiano (texto acima) e do Eduardo (P19 a P25); atualizar §10.8 e pedir a nova carga ao TÉCNICO.
- Conferir os textos da T15 e da aba "RETO por origem" quando o FRONTEND entregar.
- Depois da implantação: lista do BLOCO 2 (OPs mal digitadas, SEM OP, cortes sem peso, solicitações sem lote), contêiner digitado errado no Controle de Corte, comentário com várias OPs, corte dividido entre contêineres, "PESO INICIAL" (achados B05 a B08 da auditoria, ainda sem texto na spec).

## Aguardando

- **Eduardo:** P19 a P25; repassar o texto ao Fabiano; avisar o Fabiano sobre o IPI do NCM 82089000.
- **TÉCNICO / FRONTEND / BANCO E TESTES:** R040, R041, R042.

## Instruções permanentes desta frente

1. **A especificação oficial é `estoqueack/docs/03_especificacao_funcional.md`** (sem cópia na raiz). Ao editar, subir a versão no cabeçalho (v3.4 → v3.5…), explicando em uma frase o que mudou.
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
    - Próximo número de pedido: o maior R0xx em `PEDIDOS.md` + 1 (em 06/11 o último era R042).
