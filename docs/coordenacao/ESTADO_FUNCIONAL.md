# Estado — FUNCIONAL

Atualizado: 2026-11-17 (T07 + T13 unificadas e ajustes do teste manual, especificação v3.14)

## No ar

- **Especificação v3.14:** as 2 decisões de 17/11 da DECISOES. (1) T07 é a única porta de entrada; com lote de Itu continua no lançamento do corte (conteúdo da T13); T13 fora do menu, só pelos atalhos do T03 (peso real) e do T05 (botão novo "Registrar corte em Itu" no lote RJ em Itu) (§2, §4, §4.1, §4.2, T07, T13, §9). (2) Filtro de liga por "contém" (T04, RETO por origem, T08, T19), instrução de processo múltipla (T07), justificativa sem mínimo, não vazia (§9, T15), T09 com pesquisa e cartões que expandem, emitente só Fio Certo (§2.1, T11, T14). Nova **P38** (detalhes que são proposta). Sem pedido novo (a COORDENAÇÃO já acionou as frentes).
- **Especificação v3.13:** observações do Eduardo de 17/11 (SA cadastrado no Mega pela **Amanda**, Fabiano só pede: §2, T14; peso real da peça inteira = consumo da OP, resto = estoque em Itu: §2.2, T13; **regra do RETO** por E × L com "Conferi a regra" e 3 parâmetros na T23: T13, T10, §9) e R062 respondido (§10.3, §10.9 A.1/A.7/B/E: 41 contêineres corrigidos dentro do aprovado, 1 com material diferente; CH35SH = H13 nas três planilhas; Planilha1 com SA). Novas **P35** (RETO), **P36** (quem informa o código do SA), **P37** (carga 17/11); P34(d) com evidência. Pedidos **R063** (TÉCNICO) e **R064** (FRONTEND).
- **Especificação v3.12:** nomes novos do menu (aprovados pelo Eduardo em 17/11) no §4, matriz §4.1, títulos T03–T16 e fluxos do §2; códigos das telas mantidos. T17, T18 e T24 ficaram fora do menu aprovado.
- **Especificação v3.11:** respostas de 17/11 (DECISOES 2026-11-17). SA da peça inteira **não é corrigido** (saem "Corrigir no Mega"/"Corrigido no Mega"); pendência do peso real com mais de 7 dias **bloqueia** "Enviar ao RJ" na T07 (`PESO_REAL_PENDENTE`, T23 `PENDENCIA_PESO_REAL_DIAS`); faixa da seção = maior valor (§1.4 item 7, R057 respondido); paridade manual (§1.4 item 8); novo §10.9 (correções antes da recarga + arquivo de correções). P32 respondida; **P33** (detalhes do bloqueio) e **P34** (escolhas da carga) abertas, devolvidas à COORDENAÇÃO para o arquivo único. Pedidos **R058** (TÉCNICO) e **R059** (FRONTEND).
- **Especificação v3.10:** P30 (pendência do Fabiano para o peso real; SA corrigido para o peso real com "Fazer no Mega" e situação "Corrigir no Mega"; previsto só na NF; sem SA complementar; sobra sem OP = nada na F1) e P31 (comprimento do HISTORICO só conta se Itu também tem comprimento). **P32** aberta (pendência não resolvida; quando o SA conta como corrigido), em `carga/perguntas_eduardo_2026-11-12c.txt`. Pedido **R054**. Exemplos com OPs e contêineres fictícios (6c7c043).
- **Especificação v3.9:** P27 (peso pesado substitui o previsto na peça inteira do RJ, também acima de 8 %; B2 gera SA normal com dados do Fabiano) e P29 (comprimento do HISTORICO vale; faixa igual = mesma linha; CH39SH = 95199). **P30** aberta (SA complementar dos kg a mais; sobra RJ em Itu sem OP), em `carga/perguntas_eduardo_2026-11-12.txt`. Pedido **R052**. OP 100092 trocada por fictícia.
- **Especificação v3.8:** P28 respondida (MOD é liga diferente; 1.2344 = H13 e 1.2379 = D2 na mesma linha; comprimento informado e múltiplo diferenciam; normalização da escrita; recarga do zero após o relatório de paridade). CH39SH ("D2 Ø90", sem comprimento na ESTOQUE 2026; HISTORICO diz Ø90×2425) não fica na linha do 95199. **P29** aberta (comprimento só no HISTORICO; faixa de comprimento). Pedido **R051**.
- **Especificação v3.7:** paridade RJ × Itu por **liga + bitola exatamente iguais** (novo §1.4); RJ sem código do Mega na carga (código só pelo SA); Itu e RJ na mesma linha na T04 ("agrupado por liga × bitola") e na T07; 7 pares do B04 = não; P19, família de liga (§10.7 item 1) e CH39SH = 95199 substituídos; T13/T14/T15/T16 dizem o que muda. **P28** aberta (ligas equivalentes, comprimento, escrita da medida, recarga do zero), spec escrita com as propostas "[proposta, P28]"; pergunta em `carga/perguntas_eduardo_2026-11-11c.txt`. Pedidos **R049** (TÉCNICO: carga + relatório de paridade antes da recarga) e **R050** (FRONTEND). Exemplo OP real do §2.2 e do doc 04 trocado por fictício.
- **Especificação v3.6:** P26 aplicada (consumo misto opção A na F1; peça inteira do RJ sem SA complementar; justificativa de sobremetal > 20 % mantida; redondo inteiro do RJ com a mesma lógica). P26(2a) = sim (aviso de barra mais leve, só aviso). **P27** aberta (a regra sem SA complementar vale para o B2?), em `carga/perguntas_eduardo_2026-11-11b.txt`. Pedido **R047** (TÉCNICO, FRONTEND).
- **Especificação v3.5** (`estoqueack/docs/03_especificacao_funcional.md`).
  - **P19 a P25 fechadas** (§12); §9.1 sem "a confirmar" (CR8MOD é liga distinta).
  - **P22(a) reescrita** (§2.2, T13, §9, T23): material inteiro do RJ com previsto pela peça acabada e oscilação de **8 %**; 5 % segue no corte RJ e no Estoque Mega. P22(b): vale o SA mais recente.
  - **T07 passo 2:** sugestão por liga × bitola exata, Itu e RJ lado a lado; "Consumo nos dois estoques" (opção A proposta).
  - **Carga (§10.7 item 6, §10.8):** redondo exige RED/Ø; D6 chapas; planilha "Materia Prima Geral 05nov"; RETO do RJ em Itu sem lote-pai por candidato único; 1.2767 RETO sem origem.
- **Pedidos:** R045 (TÉCNICO) e R046 (FRONTEND) abertos. R040, R041, R042 já respondidos.
- **Arquivos fora do repo:** `carga/perguntas_fabiano_2026-11-10.txt` (7 pares do B04), `carga/perguntas_eduardo_2026-11-10.txt` (P26).

## Próximo

- Responder o R068 (leituras do TÉCNICO no R063/R065).
- Aplicar P33, P34, P35, P36, P37 e P38 quando o Eduardo (e o Fabiano, P34 a/c) responder; aplicar a resposta do 1.2767 × 1.2746 RETO (PENDENCIAS 17/11) no §10.9 D.
- Aplicar a P27 quando o Eduardo responder.
- Depois da implantação: lista do BLOCO 2 (OPs mal digitadas, SEM OP, cortes sem peso, solicitações sem lote), contêiner digitado errado, comentário com várias OPs, corte dividido entre contêineres, "PESO INICIAL" (B05 a B08).

## Aguardando

- **Eduardo:** P33, P34, P35, P36, P38. **Marcelo:** P37(a). **Fabiano:** P37(b), P34(d) (10 discordantes), aviso da paridade do contêiner H13. **Fabiano:** 1.2767 × 1.2746 RETO (`carga/PENDENCIAS_USUARIOS_2026-11-17.txt`). (55322: resolvido, A8 MOD do RJ fica separado.) Avisar o Fabiano sobre o IPI do NCM 82089000 (se ainda não foi).
- **TÉCNICO / FRONTEND:** R045, R046, R047, R049, R050, R051, R052, R054, R058, R059, R063, R064.

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
    - Próximo número de pedido: o maior R0xx em `PEDIDOS.md` + 1 (em 17/11 o último era R064).
