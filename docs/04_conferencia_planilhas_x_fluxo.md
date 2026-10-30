# Conferência: planilhas atuais × fluxo do sistema

Versão 1, 2026-10-30, feita pelo chat FUNCIONAL.

**Objetivo:** ler as 4 planilhas linha a linha, entender como a AçoKorte trabalha hoje e ver onde a especificação funcional (`03_especificacao_funcional.md`) acerta, erra ou deixa algo de fora.

**Como foi feito:** as planilhas foram lidas com script, incluindo fórmulas, comentários de célula e comentários encadeados. Depois, as OPs foram cruzadas entre elas:

- **Corte RJ:** 804 linhas, de março/2025 a outubro/2026.
- **ESTOQUE 2026:** 482 consumos com OP no comentário.
- **SA:** 8.276 linhas de 2016 a 2026, sendo 1.775 na aba "2025".
- **Estoque Geral:** 591 itens.

**Legenda do status de cada achado:**

- ✅ **Bate:** a especificação já trata do ponto.
- ⚠️ **Ajustado:** a especificação foi corrigida nesta versão.
- ❓ **Pergunta:** depende de confirmação (P13 em diante, no §12 da especificação).

---

## 1. Resumo: como o processo funciona hoje, segundo os dados

**Fluxo real do material RJ cortado no RJ:**

```
Itu: solicita corte (Controle de Corte)
RJ: corta e informa peças + PESO2 (peso real)
Itu: cadastra o SA no Mega com o PESO2       ← ANTES do envio (mediana: 1 dia antes da liberação)
RJ: emite a NF de transferência do SA (coluna "NF FIOCERTO/MEDIO VALE" da planilha de SA)
RJ: libera o COP (DATA DE LIBERAÇÃO = data de envio) e abate o ESTOQUE 2026 com o PESO2, na data da liberação
Itu: marca "RECEBIDO ACK?"
```

**Peça inteira:** a ordem é a mesma. O SA é cadastrado **antes** do envio, com o **peso previsto** (bitola + sobremetal). A NF que acompanha a barra transfere só esse peso. O ESTOQUE 2026 abate a **barra inteira** do RJ no Rio, e a diferença vira **RJ em Itu**: material fiscal do RJ que já está fisicamente em Itu.

**Corte em Itu de material RJ em Itu:**

- **Volume:** são **45 % dos SAs desde maio/2025** (649 de 1.438). Esse caminho não passa pelo Controle de Corte.
- **Como funciona hoje:** Itu corta a sobra que já está em Itu, cadastra o SA e o RJ emite uma **NF de transferência só fiscal**, sem o material viajar. Há 151 NFs que só têm SAs desse tipo.

**Conclusão:** o SA e a NF de transferência são o **documento fiscal da transferência RJ → Itu**. Eles acontecem **antes do envio físico** (corte no RJ e peça inteira) ou **no consumo em Itu** (RJ em Itu). A especificação v1 colocava o SA **depois** do recebimento em Itu, e isso foi corrigido.

---

## 2. Achados, um a um

### 2.1 O SA é feito antes do envio, não depois do recebimento ⚠️ ❓P13

| Evidência | Número |
|---|---|
| SA cadastrado entre a solicitação e a liberação | 425 de 638 |
| SA no dia da liberação ou depois | 148 de 638 (a maioria no mesmo dia) |
| Peça inteira com SA antes ou no dia da liberação | 78 de 79 |
| Mediana entre o SA e a liberação | 1 dia antes |
| SAs de outubro/2026 sem NF preenchida | 0 |

**O que muda na especificação:**

- **Fila de SA (T14):** passa a receber o item assim que o corte é registrado no RJ (T10), ou assim que a solicitação de peça inteira é enviada.
- **COP (T11):** só pode ser fechado quando todos os itens têm SA informado. Se faltar algum, o COP mostra o aviso "SA pendente".
- **NF de transferência:** é digitada por item ou grupo no COP, ou no SA no caso do RJ em Itu, e não uma vez por COP.

**Ainda precisa de confirmação (P13):** o SA é feito em Itu pelo Fabiano, e o RJ (Fio Certo / Médio Vale) só emite a NF depois que recebe o código?

### 2.2 NF × COP: na maioria é uma NF por COP, mas nem sempre ⚠️ (responde a P02)

**Correção da v1 deste documento (2026-10-30):** a primeira contagem ligou o SA ao COP só pela OP. Quando a mesma OP tinha outro SA em outra data (SA complementar de peça inteira consumida depois em Itu, ou entrega anterior), ele era contado no mesmo COP, e isso inflou o número de COPs com várias NFs. A recontagem liga cada SA ao envio da mesma OP **pela data**: o SA tem que estar entre 20 dias antes e 3 dias depois da liberação. A coluna COP só existe no Controle de Corte a partir de **jan/2026** (COP 550), então a análise cobre jan a out/2026.

| Evidência (recontagem) | Número |
|---|---|
| COPs com **uma única NF** | **27 de 38 (71 %)**; na série de NF ≥ 1000, 19 de 25 (76 %) |
| COPs com mais de uma NF | 11 de 38 (ex.: COP 552 com as NFs 641, 642 e 643; COP 578 com 3114 e 3119) |
| NFs que atendem dois COPs seguidos | 3 de 49 (3114: COPs 577 e 578; 3135: 582 e 583; 3160: 588 e 589) |
| Últimos 8 COPs (593 a 600, set–out/2026) | 7 com uma NF |
| NFs só de SAs sem corte RJ (corte em Itu, transferência só fiscal) | 151 (2025–2026) |
| Séries de NF | < 1000 até o início de 2026 e ≥ 1000 depois. A hipótese é que sejam emitentes diferentes (Médio Vale × Fio Certo), mas falta confirmar |

**Achado extra:** algumas OPs de peça inteira têm um **segundo SA** semanas depois do envio, com outra NF (ex.: OP 99125: 195 kg em 22/07 e 117 kg em 14/09; OP 99834: 112 kg e 113 kg; OP 96897: 214 kg e 22 kg). Isso é consumo complementar da barra em Itu (Caminho B2) para a mesma OP.

**O que muda na especificação:**

- **No COP:** a NF é digitada **uma vez no COP** e vale para todos os itens. É o caso comum.
- **Exceção:** o Marcelo pode informar uma NF diferente para alguns itens, ou usar a mesma NF em dois COPs.
- **Onde a NF fica gravada:** em cada linha de SA, como na planilha.

A P02 está respondida.

### 2.3 Peso previsto: sobremetal em todas as dimensões, não só no comprimento ⚠️

A coluna PESO do Controle de Corte, nas 94 linhas com número (peça inteira), foi recalculada:

- **Contra a medida acabada:** PESO fica entre 1,05 e 1,7 vezes o peso da peça acabada (mediana 1,25).
- **Contra a espessura da bitola × largura e comprimento acabados:** ainda fica acima. Ou seja, o previsto inclui **espessura da bitola + sobremetal na largura + sobremetal no comprimento**.
- **Exemplo, OP 91050:** peça 23×65×165,2, 80 peças, bitola H13 28×610. A peça acabada pesa 155 kg, a espessura da bitola × acabado dá 189 kg e o previsto informado é **236 kg**, perto de 28 × 70 × 190 mm.

**Sobremetal no comprimento:** o padrão é **5 mm**. Ele aparece em 280 de 394 instruções de corte ("N PEÇAS COM xxxMM"), e o valor seguinte mais comum, 4 ou 6 mm, aparece em 22 cada. A diferença entre a largura da barra e a largura acabada fica entre 2 e 7 mm nas barras chatas.

**O que muda na especificação (T07):** o "peso previsto" deixa de ser "seção da bitola × comprimento". Ele passa a ser calculado pelas **dimensões brutas de corte**:

| Dimensão | Valor |
|---|---|
| Espessura (ou Ø) | Sempre a da bitola |
| Largura | A da bitola, quando a peça usa a largura inteira (barra chata). Quando a peça sai de uma chapa larga (ex.: 610), é a largura acabada + sobremetal de largura |
| Comprimento | Acabado + sobremetal de comprimento (padrão 5 mm) |

O sistema preenche as três e o usuário pode alterar cada uma. Assim continua valendo a regra do Matheus: bitola escolhida + sobremetal preenchido.

### 2.4 Peça inteira é uma barra específica, escolhida pelo comprimento ⚠️ ❓P14

**Evidências:**

- **Instruções que já citam a barra:** muitas apontam a barra exata, como "TRAZER 01 PEÇA H13 45X610**X3905**" (OP 91958).
- **PESO2 igual ao packing list:** o PESO2 dessas linhas é **exatamente** o peso daquela barra no packing list (aba HISTORICO: "H13 45 X 610 X 3905 → 859 kg"). Ou seja, a barra **não é pesada**, e o peso vem do packing list.
- **Registro barra a barra:** a aba HISTORICO registra muitas entradas **uma barra por linha**, com comprimento e peso. Exemplos: CH31K, CH35SH e as linhas Ø de CH37SH e CH38SH.
- **Contagem de peças e pedaços:** a coluna "QUANTIDADE CHAPA/BARRA" da ESTOQUE 2026 tem comentários como "6 PEÇAS / 1 PEDAÇO", "15 - 1762 KG / 13 - 1522 KG…" e uma lista de comprimentos de cada barra.
- **Ajuste no ESTOQUE 2026:** em 24 peças inteiras, ele abate o peso **da barra** (ex.: OP 99490: 1.401 kg), enquanto o PESO2 do Controle de Corte ficou com o previsto (349 kg). Por isso o PESO2 da planilha não é confiável para peça inteira.

**O que muda na especificação:**

- **Peças dentro do lote:** o lote passa a ter **peças** (barra ou chapa inteira, ou pedaço), com comprimento e peso. A carga sai do packing list (HISTORICO).
- **T07, modo peça inteira:** o usuário escolhe **a barra**. O peso da barra é [SUGERIDO] pelo packing list.
- **T10:** o Marcelo confirma ou corrige o peso da barra.

Isso altera a proposta da P11 (antes era "peças só como informação"). Ver a P14.

### 2.5 O RJ troca ou divide o lote no corte ⚠️

| Evidência | Número |
|---|---|
| Consumos da ESTOQUE 2026 abatidos de um **contêiner diferente** do solicitado | 67 de 475 (14 %) |
| Comentários de troca de contêiner no Controle de Corte | "CH34SH", "OU CH21K", "50x460 (CH29K)" |
| Corte dividido entre dois lotes | M795: "CH40SH - 16 PEÇAS 630,5KG / CH11EA - 4 PEÇAS 156,5KG"; M787: "14X123 CH02CR - 13 PEÇAS 198KG / 14X130 CH39SH - 29 PEÇAS 452KG"; P354: duas bitolas de DC53C |
| SAs com mais de uma linha para a mesma OP (bitolas e contêineres diferentes) | Comuns. Ex.: OP 99884, com 4 linhas |

**O que muda na especificação (T10):** botão **"Usar outro lote / dividir"**. O Marcelo informa, para cada lote usado, as peças e o peso. O sistema valida saldo e bitola, pede justificativa, notifica o Fabiano e gera uma linha de SA por lote, como já é hoje.

### 2.6 Corte em Itu de material RJ em Itu é um caminho próprio e grande ⚠️

- **Volume:** são 649 SAs desde maio/2025 sem linha no Controle de Corte. Origens: CH31K, CH30K, CH29K e outros. Pesos pequenos, de 7 a 300 kg.
- **NF própria:** são NFs de transferência **só fiscal**, emitidas em lote (ex.: 2025-05-08, NFs 556, 557 e 558 com dezenas de SAs).
- **Origem:** o Estoque Geral guarda a origem das sobras **em comentário**. Exemplo (H276, D2 RETO): "381kg de sobra (MEDIDA ORIGINAL IMP-D2 25X610MM)", "450kg de sobra (… 30,5x610MM)".

**O que muda na especificação:** novo **Caminho B2**: corte em Itu de lote RJ em Itu → SA (com a origem do lote) → NF de transferência fiscal informada no SA → baixa no Mega. A T13 passa a gerar a linha de SA para lotes de planta fiscal RJ.

### 2.7 Data do abatimento e peso abatido do estoque RJ ✅

| Evidência | Número |
|---|---|
| Consumos da ESTOQUE 2026 com o peso igual ao PESO2 (peso real do corte) | 327 de 407 cortes |
| Consumos com a data do comentário igual à DATA DE LIBERAÇÃO | 279 de 380 |
| OPs **digitadas erradas** nos comentários (ex.: "989123", "10008") | 9 |
| Consumos marcados "SEM OP" | 3 (ex.: 1.460 kg de H13 75×610 / CH33K) |

A especificação já baixa o lote com o peso real no registro do corte, e a OP vem da solicitação, sem redigitação. ✅

**Para conferir:** o significado do "SEM OP" (P15).

### 2.8 Código de SA por peça acabada ✅ (confirma a regra do Matheus)

- **Bitolas diferentes, mesmo código:** 889 itens usaram **o mesmo código de SA com bitolas diferentes**.
- **Itens com mais de um código:** 100 dos 2.787 itens (antes eram 39 de 1.684 só na aba 2025). Na maioria, o código antigo foi **inativado** ("39294 - INAT", "37475 - INATIV.").
- **Ajuste na regra:** usar o código **mais recente ativo**. Se o Mega disser que está inativo, pedir um novo.
- **Código compartilhado:** 23 códigos de SA aparecem em mais de um item. São casos raros, que entram na lista de pendências da carga.

### 2.9 SA de RETO mantém o contêiner de origem ✅

Há 25 SAs com DIMENSÃO "RETO" e ORIGEM = contêiner (ex.: OP 100126, 1.2746 RETO, CH35SH). A rastreabilidade do RETO até o contêiner já é usada na prática, e a especificação cobre isso.

### 2.10 Valor precificador (R$/kg) do SA ❓P16

- **Fórmula:** o SA usa `= (R$/kg × PESO) / QTDE`, com o R$/kg digitado dentro da fórmula.
- **Origem desconhecida:** esse R$/kg **não bate** com o "VALOR UNITÁRIO" do contêiner na ESTOQUE 2026. Ex.: CH11EA A8 21×202 tem 13,11 na ESTOQUE 2026 e 14,06 no SA.
- **Por que precisa resolver:** o campo é obrigatório no SA de hoje, então o sistema precisa saber de onde vem o número (P16).

### 2.11 Renato baixa os SAs periodicamente ⚠️

Há vários comentários "até esta linha foi baixado para computador Renato José Pinto. Qualquer alteração anterior a esta linha, favor avisar."

**O que muda na especificação (T14):** botão **"Exportar SAs novos para o Renato"**. Ele exporta só os SAs ainda não exportados e marca a data. Uma alteração depois da exportação gera um aviso ao Renato.

### 2.12 Pedidos de compra em andamento ficam em comentário ❓P17

O Estoque Geral tem cerca de 40 comentários do Renato com pedidos de importação: fornecedor, quantidade e previsão. Exemplos: "Pedido EASON 3 tons, prazo final de Nov/2026"; "Pedido Alice 0,5 ton, material de estoque, previsão embarque começo de Nov/2026"; "1574kg embarcados, previsão Santos em 30/Maio".

**O que pode mudar:** uma tela simples **"Material a chegar"** (item, fornecedor, kg, previsão, situação), mostrada na posição de estoque. Ainda falta definir se entra na v1 (P17).

### 2.13 Ligas equivalentes e nomes diferentes ⚠️ ❓P18

- **Mesma liga com nomes diferentes:** o Estoque Geral soma **1.2344 dentro de H13**. Ex.: H13 50×610 = 4.738 kg no Estoque Geral = 1.948 (H13) + 2.790 (1.2344) na ESTOQUE 2026. O mesmo acontece com 12746 / 1.2746 / DIN 1.2746 e com CR12MOV / Cr12MoV / CR12 MoV.
- **Diferenças só de nome:** das 230 combinações material + bitola entre a ESTOQUE 2026 e o Estoque Geral, 111 diferem. Quase todas são só de nome (sufixos "x2800-6000", "MULT.", "_", "()").

**O que muda na especificação:** o catálogo (T22) ganha **equivalência de liga**: 1.2344 ≈ H13, 1.2379 ≈ D2, 1.2767 ≈ 45NiCrMo16 etc.

**Ainda precisa de confirmação (P18):** a T07 deve listar lotes de liga equivalente como compatíveis?

### 2.14 Restrições, substituições e comprimentos fixos no Estoque Geral ✅ ⚠️

- **Restrições:** "não usar para guilhotinas" (11 itens), "RESERVADO CPR", "USAR SOMENTE PARA CONTRATO VOTORANTIM", "Destinação testes somente com liberação de Vendas", "MAT P/ DESFOLHADEIRAS". Elas já entram em T17 ✅.
- **Itens substituídos:** "SUBSTITUÍDO POR A8 21X203", "SUBSTITUÍDO POR CR8 PLACAS 5,8 E 4,8 (RISUN / 18 TONS)" e outros 11. ⚠️ O catálogo ganha o campo **"substituído por"**: a T07 avisa e sugere o substituto.
- **Comprimentos fixos:** "COMPR. FIXADOS" ("3110MM (MIN)", "MULT. 1820", ">= 3200") ⚠️ aparece em T07 como informação do item, ao lado do comprimento de corte.

### 2.15 Instruções de processo junto do corte ⚠️

O Controle de Corte tem 18 notas do almoxarifado: "RETIFICAR LARGURA E ESPESSURA", "Retificar espessura deixando com 22mm", "UTILIZAR SOBRAS DE A8 CONFORME VERIFICADO" e "PEÇA BI-PARTIDA".

**O que muda na especificação:** a T07 ganha o campo **"Instrução de processo"** (texto livre e opções rápidas: Retificar espessura / largura). Ele aparece na Fila RJ e na lista de corte impressa.

### 2.16 Erros e correções que hoje ficam em comentário ✅

Exemplos encontrados:

- "FOI INFORMADO O PESO ERRADO PELO FUNCIONÁRIO ELIAS. O PESO CORRETO É 193,5KG".
- "Descontado o peso de 1199,5Kg conforme informado via e-mail por conta de erro no controle do RJ".
- "99588 deveria ter pedido material A8 comum… anexamos essas outras 20 peças na OP 99788".
- "Foi definido que cortaríamos 80 peças a mais… A op será ajustada no mega".
- "Solicitado erroneamente CR12MOV".

Tudo isso vira **estorno ou ajuste com justificativa** e **troca de OP** (§8), com auditoria. A especificação já cobre ✅. Falta só definir a tela da troca de OP (R007).

### 2.17 Prazos do corte RJ ✅

- **Prazo atual:** da solicitação à liberação, a mediana é **6 dias** e o p90 é 13 dias.
- **Faixas da planilha:** Normal ≤ 7 dias, Atenção ≤ 15 dias e Atrasado acima disso.
- **Abertos há muito tempo:** 14 itens estão abertos há 75 dias ou mais, até 462 dias. São pendências reais a limpar antes da carga.

**Na especificação:** essas faixas entram como parâmetros em T23.

### 2.18 Detalhes para a carga inicial ⚠️

| Planilha | Achado | Tratamento |
|---|---|---|
| HISTORICO | Não é só de lotes esgotados. Tem as **entradas** dos contêineres ativos (CH31K a CH40SH, CH01AT, CH04TG, CH10EA, CH11EA), com o detalhe por barra. As saídas não são mantidas desde cerca de 2019 | Usar para criar as **peças** (comprimento e peso) dos lotes ativos. O saldo vem da ESTOQUE 2026 |
| ESTOQUE 2026 | 5 contêineres sem entrada no HISTORICO (10, 103, 1K, CH03K, CH4R) | Lotes sem documento de entrada, marcados na pendência |
| ESTOQUE 2026 | 9 OPs mal digitadas e 3 "SEM OP" | Lista de pendências para o Fabiano corrigir |
| Controle de Corte | Aba "Planilha1" com OPs repetitivas da LP (Chile/Brasil) e linhas "EM PROCESSO" | Conferir se ainda estão ativas. Se estiverem, importar como solicitações abertas |
| Controle de Corte | Coluna "Peso previsto (acabado)" sempre vazia | Ignorar |
| SA | 2 séries de NF (< 1000 e ≥ 1000), provavelmente de emitentes diferentes | Guardar o emitente junto com a NF |

---

## 3. Perguntas novas (entram no §12 da especificação)

| # | Pergunta | Proposta padrão |
|---|---|---|
| P13 | A ordem é mesmo **corte RJ → SA em Itu → NF do RJ → envio do COP**? Quem emite a NF de transferência (Fio Certo, Médio Vale) precisa do código de SA antes? | Sim. O COP só fecha com SA informado em todos os itens |
| P14 | Controlar **cada barra ou chapa** do lote (comprimento e peso do packing list), pelo menos para chapas e blocos grossos? | Sim, peça por peça para chapa ≥ 25 mm e redondos acima de Ø200. Para as barras finas, só a contagem |
| P15 | O que é "SEM OP" no ESTOQUE 2026 (ex.: 1.460 kg de H13 75×610)? Transferência para estoque em Itu, venda, amostra? | Criar a solicitação **"Trazer para estoque em Itu"**, sem OP e com motivo |
| P16 | De onde vem o **R$/kg** do valor precificador do SA? | O Renato informa por contêiner + bitola (T22). Enquanto isso, fica em branco |
| P17 | Incluir **"Material a chegar"** (pedidos do Renato) na v1? | Sim, como lista simples ligada ao item |
| P18 | **1.2344 e H13** (e outras equivalências) podem ser usados um no lugar do outro na OP? | Mostrar como compatíveis com o selo "liga equivalente" e exigir "estou ciente" |
