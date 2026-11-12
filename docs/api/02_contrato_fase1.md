# Contrato da API: Fase 1 (especificação v3)

Escrito em 2026-11-03 pelo chat TÉCNICO (BACKEND 2), em resposta ao R022 e para o FRONTEND montar as telas do R023. As convenções (sessão, CSRF, erros, paginação, **prévia `/validar` + gravação com `confirmacoes`**) são as do `01_contrato_api.md` §1 e continuam valendo. A referência executável é o OpenAPI em `/api/docs` (homologação).

Situação: ✅ no ar (commit `e9fe723` em diante) · 📋 contrato definido, ainda não implementado.

## 0. O que muda em relação ao contrato v1

- **Códigos com sufixo.** Quando a mesma validação aparece em mais de um lote da mesma ação, o 2º lote em diante vem com sufixo: `LOTE_TROCADO#2`, `SALDO_INSUFICIENTE#3`. Mande a confirmação com o código **exatamente como veio**.
- **Erros novos:** `400` = ação impossível no estado atual (ex.: cancelar uma solicitação já cortada), com `detail` pronto para mostrar. `409` continua sendo "validação pendente", com o corpo do `/validar`.
- **Perfis:** a API já aplica a matriz §4.1. Perfil sem permissão recebe `403`. **Operação RJ** só enxerga RJ no Rio: em `GET /api/lotes` o filtro `estoque` é forçado para `RJ_NO_RIO`, e lotes de outros estoques respondem `404`.
- **Reservado** (`reservado_kg` em lotes) agora soma as reservas de T17 **e** o peso previsto ainda não cortado das solicitações *Enviadas* e *Parciais*.

## 1. T07 Nova solicitação ✅

### Passo 2: `GET /api/lotes/compativeis` ✅

Parâmetros: `liga` (obrigatório), `formato` (`RETANGULAR`/`REDONDO`), `espessura`, `largura`, `diametro`, `comprimento`, `quantidade`, `estoque` (opcional). Resposta paginada `{ itens: [...], total }` (como `GET /api/lotes`). Traz lotes da liga **e das ligas equivalentes** (`liga_equivalente: true` → selo), cuja bitola comporta a medida acabada e com disponível > 0. Cada item tem os campos de `GET /api/lotes` mais `peso_previsto_kg`, `peso_peca_kg`, `sobremetal_pct` (estimados com 5 mm), `substituido_por_id` e `multiplo` (null = material comum; `"1110"` = múltiplo de 1.110 mm). Ordem: menor sobremetal, depois o mais antigo.

**Sugestão por liga × bitola (spec v3.5, 2026-11-11, R045/R046)** ✅. Parâmetro novo opcional `peso_necessario_kg` (o peso previsto do passo 3). A resposta ganha `grupos` (a lista `itens` continua igual):

```json
{ "grupos": [ { "chave": "H13|RETANGULAR|33X105|", "liga": "H13", "formato": "RETANGULAR", "bitola": "33X105",
    "multiplo": null, "liga_equivalente": false, "peso_previsto_kg": 82.7, "sobremetal_pct": 17.8,
    "peso_necessario_kg": 120.0, "total_disponivel_kg": 140.0, "falta_kg": 0.0, "sobra_kg": 20.0,
    "so_um_estoque": false, "frase": "Necessário 120,0 kg × disponível 140,0 kg: sobra 20,0 kg",
    "estoques": { "ITU": { "disponivel_kg": 40.0, "lotes": [ { "id": 3, "codigo": "L-000003", "estoque": "ESTOQUE_MEGA",
                                                                "conteiner": null, "codigo_mega": 78290, "tipo": "ORIGINAL",
                                                                "saldo_kg": 40.0, "reservado_kg": 0.0, "disponivel_kg": 40.0,
                                                                "indicadores": {} } ] },
                  "RJ_NO_RIO": { "disponivel_kg": 100.0, "lotes": [ ... ] } } } ] }
```

- Grupo = **liga e bitola exatas** (mesmo formato e medidas; 21x202 e 21x203 nunca se juntam), **o mesmo comprimento informado e o mesmo múltiplo** (P28, 2026-11-11: D2 Ø90 ≠ D2 Ø90X2425). `chave` é o texto da linha (ex.: `"H13 33X105"`); o código do Mega não entra. **1.2344 = H13, 1.2379 = D2 e as outras equivalências sem MOD da T22 (ex.: 12746 = 1.2746) ficam no mesmo grupo e contam como a mesma liga** (P28(1), 2026-11-12): `liga_equivalente: false`, sem selo nem "estou ciente" (`LIGA_EQUIVALENTE` não aparece na T07); só equivalência com MOD (que não junta grupo) vem com `liga_equivalente: true`. O grupo só tem `liga_equivalente: true` se todos os lotes forem equivalentes. Cada lote do grupo traz `liga`, `liga_equivalente` e `descricao`. `ITU` junta Estoque Mega e RJ em Itu (cada lote traz `codigo_mega`); `RJ_NO_RIO` lista por contêiner. Estoque sem lote vem com `lotes: []`.
- A8MOD e **CR8MOD** são ligas distintas (P24, P28): nunca entram no grupo de A8/CR8. `codigo_mega` dos lotes vem só no Estoque Mega (o RJ não tem código, spec v3.7 §1.4).
- `peso_necessario_kg` ausente → usa o `peso_previsto_kg` estimado do grupo. `falta_kg`/`sobra_kg` = necessário − total disponível. Nada é escolhido sozinho: a tela deixa marcar lotes de um ou dos dois estoques (ver "Consumo misto").

### Passos 3 e 4: `POST /api/solicitacoes/validar` e `POST /api/solicitacoes` ✅

```json
{ "op": 100592, "liga": "H13",
  "medida": { "formato": "RETANGULAR", "espessura": 30, "largura": 100, "comprimento": 250 },
  "itens": [ { "lote_id": 12, "modo": "CORTAR_RJ", "quantidade": 12,
               "sobremetal_comprimento_mm": 5, "sobremetal_largura_mm": null,
               "bruto": null, "comprimento_barra_mm": null,
               "instrucao": null, "instrucao_processo": "Retificar espessura" } ],
  "prazo": "2026-12-09", "observacao": null,
  "op_manual": null, "enviar": true, "confirmacoes": {} }
```

- `modo`: `CORTAR_RJ` ou `TRAZER_INTEIRA`. Lote em Itu → `MODO_INCOMPATIVEL` (ERRO): a tela usa "Registrar corte em Itu agora" (T13, §5) **[R005]**.
- `sobremetal_*` em branco usam os parâmetros (5 mm). `sobremetal_largura_mm` em branco = o sistema decide: se a peça usa a largura inteira da bitola, 0; senão, 5.
- `bruto` (opcional): dimensões brutas editadas pelo usuário. Em branco, o sistema calcula (bitola + sobremetal).
- `instrucao` em branco = sugerida: `"12 PEÇAS COM 255MM COMPRIMENTO"` ou `"TRAZER 01 PEÇA H13 70X610X3905"`.
- `op_manual`: `{ item_codigo, item_descricao, cliente }`, só quando o Mega está fora do ar (aparece `OP_NAO_CONFIRMADA`, ALERTA).
- `liga`: liga pedida. Lote de liga equivalente → `LIGA_EQUIVALENTE` (CIENCIA) **[P18]**.
- `enviar: false` grava rascunho sem exigir justificativas. `enviar: true` exige o `ok`.
- Um item = uma solicitação. Dois lotes para a mesma OP = dois itens no mesmo POST.
- **`consumo_misto`** (bool, padrão false; spec v3.5 T07, P26 opção A, decisão do Eduardo de 2026-11-11) ✅: marca que a OP também consome lote de **Itu**. A parte do RJ é esta solicitação (modo `CORTAR_RJ`/`TRAZER_INTEIRA`); a parte de Itu **não** entra no POST: a tela abre a T13 ("Registrar corte em Itu agora") com a mesma OP, o lote de Itu, `previsto_kg` da parte e `consumo_misto: true`. A segunda parte não gera `OP_DUPLICADA` quando a primeira foi marcada (registro sem a marca continua gerando). A conta "faltam X kg para a OP" fica na tela, com o quadro de sugestão (aviso, não bloqueia).

Resposta do `/validar` (`resultado`):

```json
{ "frase": "OP 100592: 12 peça(s), 82,7 kg previstos do lote L-000012 (H13 33X105 / CH33K), sobremetal 17,8 %. O peso previsto fica reservado no lote.",
  "efeitos": [ { "lote": "L-000012", "lote_id": 12, "material": "H13 33X105", "conteiner": "CH33K",
                 "modo": "CORTAR_RJ", "quantidade": 12,
                 "bruto": { "espessura": 33, "largura": 105, "diametro": null, "comprimento": 255 },
                 "sobremetal_largura_mm": 0, "usa_largura_inteira": true, "comprimento_corte_mm": 255,
                 "peso_peca_kg": 70.2, "peso_previsto_kg": 82.70, "sobremetal_pct": 17.8,
                 "instrucao": "12 PEÇAS COM 255MM COMPRIMENTO", "saldo_kg": 1000.0 } ],
  "op": { "numero": 100592, "item_codigo": 777, "item_descricao": "...", "cliente": "...", "pedido": "1-4521",
          "situacao": "AB", "confirmada_mega": true } }
```

Ocorrências possíveis: `OP_INEXISTENTE`, `OP_ENCERRADA`, `OP_SITUACAO_DESCONHECIDA` (ALERTA), `OP_NAO_CONFIRMADA` (ALERTA), `OP_DUPLICADA`, `MODO_INVALIDO`, `MODO_INCOMPATIVEL`, `LOTE_SEM_SALDO`, `DIMENSOES_INCOMPLETAS`, `BITOLA_MENOR_QUE_PECA`, `SOBREMETAL_ACIMA_TOLERANCIA`, `SALDO_INSUFICIENTE`, `USA_SALDO_RESERVADO`, `DESTINACAO_n`, `LIGA_EQUIVALENTE`, `LIGA_DIFERENTE` (CIENCIA, ver R024), `ITEM_SUBSTITUIDO` (ALERTA, com `dados.substituto_id`).

Gravou: `201` com `{ "solicitacoes": [ <detalhe> ] }`. O detalhe e o item da lista (§2) trazem `consumo_misto`: `null` ou `{ "itu_kg": 40.0, "rj_kg": 100.0, "texto": "OP com consumo misto: Itu 40,0 kg + RJ 100,0 kg" }` (RJ = peso real já cortado das solicitações marcadas da OP, ou o previsto enquanto não cortadas; Itu = consumo dos cortes em Itu marcados da OP). O Excel de solicitações ganha a coluna "Consumo misto".

### Rascunho

- `PUT /api/solicitacoes/{id}`: mesmo corpo, **um** item, só em `RASCUNHO`. `enviar: true` envia.
- `POST /api/solicitacoes/{id}/enviar` `{ confirmacoes }`: envia o rascunho como está.
- Excluir rascunho = `POST /api/solicitacoes/{id}/cancelar`.

## 2. T08 Solicitações ✅

`GET /api/solicitacoes?situacao=ENVIADA&situacao=CORTADA_PARCIAL&op=&cliente=&liga=&conteiner=&de=&ate=&somente_atrasadas=` (paginado). Situações: `RASCUNHO`, `ENVIADA`, `MATERIAL_INSUFICIENTE`, `CORTADA_PARCIAL`, `CORTADA`, `EM_COP`, `SA_PRONTO`, `EM_TRANSITO`, `AGUARDANDO_CORTE_ITU`, `CONCLUIDA`, `CANCELADA`. Operação RJ não vê rascunhos.

Item da lista:

```json
{ "id": 7, "numero": "S-000007", "data": "2026-11-03", "op": 100592, "item_codigo": 777, "item_descricao": "...",
  "cliente": "...", "pedido": "1-4521", "op_confirmada_mega": true,
  "lote": { "id": 12, "codigo": "L-000012", "liga": "H13", "bitola": "33X105", "conteiner": "CH33K",
            "estoque": "RJ_NO_RIO" },
  "modo": "CORTAR_RJ", "quantidade": 12, "pecas_cortadas": 0, "peso_previsto_kg": 82.7, "peso_real_kg": null,
  "reserva_kg": 82.7, "prazo": "2026-12-09", "instrucao": "...", "instrucao_processo": null,
  "situacao": "ENVIADA", "encerrada_saldo_pendente": false, "motivo": null,
  "dias_em_aberto": 0, "atraso": "NORMAL", "cops": [], "enviada_em": "...", "consumo_misto": null }
```

`atraso`: `NORMAL` (até 7 dias), `ATENCAO` (até 15), `ATRASADO` ou `null` (fora das situações Enviada/Parcial/Material insuficiente).

`GET /api/solicitacoes/{id}`: o item acima mais `medida_acabada`, `sobremetal_*`, `bruto`, `peso_peca_kg`, `sobremetal_pct`, `comprimento_barra_mm`, `observacao`, `confirmacoes`, `cortes[]` (`id, lote, lote_id, pecas, peso_real_kg, comprimento_barra_mm, data_corte, estornado, cop, cop_item_id`) e `sas[]`.

Ações (Estoque Itu):

| Botão | Endpoint | Quando |
|---|---|---|
| Cancelar | `POST /{id}/cancelar` `{ motivo }` | Rascunho, Enviada, Material insuficiente, sem corte |
| Trocar lote [R003] | `POST /{id}/trocar-lote/validar` e `POST /{id}/trocar-lote` `{ lote_id, confirmacoes }` | Material insuficiente → volta Enviada com nova reserva |
| Encerrar com saldo pendente [R004] | `POST /{id}/encerrar` `{ justificativa }` (≥ 10) | Parcial → Cortada, libera a reserva do restante |
| Trocar OP [R007] | `POST /{id}/trocar-op` `{ op, justificativa }` | Resposta traz `avisos[]` ("ajustar o SA no Mega") se o SA já estava confirmado |
| Duplicar | `POST /{id}/duplicar` | Cria um rascunho igual (`201`) |

## 3. T09 Fila RJ e T10 Registrar corte ✅

- `GET /api/fila-rj` (Operação RJ e Estoque Itu): lista de itens no formato do §2, Enviadas e Parciais, por prazo.
- `POST /api/solicitacoes/{id}/material-insuficiente` `{ observacao }` (≥ 10, Operação RJ).
- `POST /api/solicitacoes/{id}/corte/validar` e `POST /api/solicitacoes/{id}/corte` (Operação RJ):

```json
{ "linhas": [ { "lote_id": 12, "pecas": 8, "peso_real_kg": 55.0, "comprimento_barra_mm": null },
              { "lote_id": 31, "pecas": 4, "peso_real_kg": 27.6 } ],
  "data_corte": "2026-11-03", "observacao": null, "confirmacoes": {} }
```

Várias linhas = "Usar outro lote / dividir". Ocorrências: `SITUACAO_INVALIDA`, `DATA_CORTE_INVALIDA` (hoje até 7 dias atrás), `PECAS_ACIMA_SOLICITADO` (ALERTA), `LOTE_FORA_DO_RJ`, `SALDO_INSUFICIENTE`, `BITOLA_MENOR_QUE_PECA`, `LIGA_DIFERENTE` (ERRO no corte), `LOTE_TROCADO` (CIENCIA; o Fabiano é avisado), `DESTINACAO_n`, `EXCESSO_TOLERANCIA` / `ABAIXO_PREVISTO` (só no modo corte, sobre o previsto proporcional às peças, **5 %**; **peça inteira não tem faixa de 5 % nem de 8 % aqui**). **Peça inteira:** `BARRA_MAIS_LEVE_QUE_PECA` (ALERTA, não bloqueia; P26 item 2a, decisão do Eduardo de 2026-11-11) quando o peso da barra é menor que o previsto da peça (proporcional às peças): "A barra (800,0 kg) pesa menos do que a peça prevista (837,0 kg); confira a pesagem ou a bitola." `resultado.efeitos[]` traz `antes_kg`/`depois_kg` por lote e `resultado.previsto_kg`. Gravou: `201` com o detalhe da solicitação.

## 4. T11 COP ✅ (Operação RJ altera; Estoque Itu e Análise consultam)

| Ação | Endpoint |
|---|---|
| Lista | `GET /api/cops?situacao=` |
| Próximo número | `GET /api/cops/proximo-numero` → `{ numero }` |
| Cortes prontos (fora de COP) | `GET /api/cops/cortes-prontos` → `[{ liberacao_id, solicitacao_id, op, cliente, material, lote, modo, pecas, peso_kg, data_corte }]` |
| Novo COP | `POST /api/cops` `{ numero?, observacao? }` |
| Detalhe | `GET /api/cops/{id}` |
| Adicionar cortes | `POST /api/cops/{id}/itens` `{ liberacao_ids: [] }` (só Aberto) |
| Remover item | `DELETE /api/cops/{id}/itens/{item_id}` (só Aberto) |
| Fechar COP [P13] | `POST /api/cops/{id}/fechar` → gera uma linha de SA por item e avisa Itu |
| Reabrir | `POST /api/cops/{id}/reabrir` `{ justificativa }` (só sem SA confirmado; apaga as linhas de SA ainda não confirmadas) |
| NF | `POST /api/cops/{id}/nf` `{ numero, emitente: "FIO_CERTO"\|"MEDIO_VALE"\|"OUTRO", data?, item_ids? }`; sem `item_ids` vale para todos ("NF diferente para itens selecionados" = com `item_ids`) |
| Enviar | `POST /api/cops/{id}/enviar/validar` e `POST /api/cops/{id}/enviar` (`SA_PENDENTE`, `NF_PENDENTE`, `COP_NAO_FECHADO`) |

COP: `{ id, numero, situacao, data, fechado_em, enviado_em, qtd_itens, peso_total_kg, nfs[], observacao, itens[] }`. `situacao`: `ABERTO`, `FECHADO`, **`AGUARDANDO_NF`** (derivada: fechado com todos os SAs confirmados), `ENVIADO`, `RECEBIDO_PARCIAL`, `RECEBIDO`. Item: `{ id, liberacao_id, solicitacao_id, op, item_codigo, cliente, material, conteiner, lote, modo, pecas, peso_kg, situacao (EM_COP/EM_TRANSITO/RECEBIDO), sa: {id, situacao, sa_codigo}|null, nf, peso_conferido_kg, lote_itu_id, divergencias[] }`.

## 5. T12 Receber COP ✅ (Estoque Itu)

- `GET /api/recebimentos`: COPs Enviados e Recebidos parcial.
- `POST /api/cops/{id}/receber/validar` e `POST /api/cops/{id}/receber`: `{ itens: [{ cop_item_id, peso_conferido_kg? }], confirmacoes }`. Diferença acima de 2 % → `DIVERGENCIA_TRANSPORTE_<cop_item_id>` (CIENCIA, não bloqueia). Item não enviado continua em trânsito e o COP fica `RECEBIDO_PARCIAL`. Peça inteira cria o lote **RJ em Itu** filho (`itens[].lote_itu_id`) e a solicitação fica *Aguardando corte em Itu*; peça cortada fica *Concluída*.
- `POST /api/cops/{id}/divergencias` `{ cop_item_id, tipo: FALTANDO|DANIFICADO|PESO_DIFERENTE, pecas?, kg?, observacao }` → `201`. Avisa o RJ e o Admin.

## 6. T13 Corte em Itu ✅ (Estoque Itu)

- `GET /api/cortes-itu/sugestao?op=` → `{ lote_id, lote }`: peça inteira recebida para a OP.
- `POST /api/cortes-itu/validar` e `POST /api/cortes-itu`:

```json
{ "op": 100508, "lote_id": 5, "consumo_kg": 104.5, "sobra_kg": 12, "sobra_na_bitola": false, "pecas": 128,
  "peso_usado_kg": 117, "previsto_kg": null, "data_corte": null, "observacao": null, "op_manual": null,
  "confirmacoes": {} }
```

- `peso_usado_kg`: peso do material antes do corte (barra/pedaço usado). Em branco = saldo do lote. **Perda = usado − consumo − sobra.**
- `previsto_kg`: vem do T07 "Registrar corte em Itu agora". Para a peça inteira recebida, o sistema usa o previsto da solicitação.
- No `resultado`: `perda_kg`, **`perda_pct`** (% do material usado), **`perda_max_pct`** (parâmetro `PERDA_CORTE_MAX_PCT`, 6), **`perda_max_kg`**, **`peso_usado_kg`** (2026-11-04, R024; `perda_esperada_kg` saiu), `previsto_kg`, `gera_sa` (lote fiscal RJ que não é o 1º corte da peça inteira da mesma OP), `instrucao_mega` (lote Mega: "Baixar 105,0 kg do código 78290 na OP 100508. Transferir 12,0 kg do código 78290 para o código 1698 (IMP-H13 RETO).").
- **Tolerância (spec v3.5, P22(a))** ✅: lote **fiscal RJ em Itu** (peça inteira recebida, sobra e RETO RJ em Itu) usa `TOLERANCIA_EXCESSO_RJ_INTEIRO_PCT` (**8 %**); lote do **Estoque Mega** usa `TOLERANCIA_EXCESSO_PCT` (5 %). `resultado.tolerancia_excesso_pct` diz qual valeu; `EXCESSO_TOLERANCIA` tem `dados.limite_pct` e `dados.limite_de` e a mensagem termina com "Limite: 8 % para material do RJ." (ou "5 % para lote do Estoque Mega"). Redondo segue a mesma regra (Ø da barra, comprimento + 5 mm). **Não há SA complementar** do excesso na peça inteira (P26 2b): o SA da peça inteira continua com o previsto.
- **`consumo_misto`** (bool, padrão false) no corpo: parte de Itu de uma OP com consumo Itu + RJ (ver §1). Volta em `resultado.consumo_misto` e no 201.
- Ocorrências: `OP_INEXISTENTE`, `OP_ENCERRADA`, `OP_NAO_CONFIRMADA`, `LOTE_FORA_DE_ITU`, `PESO_INVALIDO`, `SALDO_INSUFICIENTE`, `EXCESSO_TOLERANCIA`, `ABAIXO_PREVISTO`, `SOMA_MAIOR_QUE_LOTE`, `PERDA_CORTE_ALTA` (CIENCIA quando a perda passa de `PERDA_CORTE_MAX_PCT` % do material usado; `dados`: `perda_kg`, `perda_pct`, `limite_kg`, `limite_pct`), `USA_SALDO_RESERVADO`, `DESTINACAO_n`, `DATA_CORTE_INVALIDA`.
- Gravou: `201` com `{ id, op, lote, consumo_kg, sobra_kg, perda_kg, lote_reto: {id, codigo}|null, sa_id, instrucao_mega, ... }`.

## 7. T14 SA ✅ (Estoque Itu altera; Operação RJ e Análise consultam; Análise edita R$/kg)

- `GET /api/sas?situacao=&origem=&op=&cop=&nao_exportados=`: sem filtro, traz os não confirmados. A resposta tem `cops_aguardando_sa[]` (para o topo da tela) e `itens[]`:

```json
{ "id": 3, "origem": "COP", "situacao": "PENDENTE", "data": "2026-11-03", "op": 100592, "cliente": "...",
  "item_codigo": 777, "item_descricao": "...", "pedido": "1-4521", "material": "H13", "dimensao": "33X105",
  "conteiner": "CH33K", "quantidade": 12, "peso_kg": 85.0, "rs_kg": null, "valor_precificador": null,
  "sa_codigo": 50001, "sa_codigo_sugerido": 50001, "sa_novo": false, "outros_codigos": [39294],
  "sa_descricao": "...", "ncm": "...", "icms": "...", "ipi": "...", "nf": { "numero": "556", "emitente": "FIO_CERTO" },
  "cop": { "id": 1, "numero": 601, "situacao": "FECHADO" }, "solicitacao_id": 7, "lote_id": 12,
  "exportado_renato_em": null, "alterado_apos_exportar": false, "atrasado": false }
```

- `sa_novo: true` → linha "SA novo – cadastrar no Mega". `atrasado: true` → vermelho (48 h sem confirmação).
- `avisos[]` (R026, v3.1; aviso cinza, não bloqueia): `{ codigo, nivel: "ALERTA", mensagem, … }`. `NF_DIFERENTE_MEGA` (NF informada ≠ NF da entrada do SA no Mega; traz `nf`, `nf_mega`) e `IPI_DIFERENTE_MEGA` (IPI do histórico ≠ IPI do NCM no Mega; traz `ipi`, `ipi_mega` em %). `IPI_DIFERENTE_MEGA` também aparece como ALERTA no `/codigo/validar`; `NF_DIFERENTE_MEGA` também no `/cops/{id}/enviar/validar` (com `dados.itens`).
- `PATCH /api/sas/{id}` `{ rs_kg, sa_descricao, ncm, icms, ipi, pedido, quantidade, peso_kg }` (Análise: só `rs_kg`; confirmado: só `rs_kg`).
- `POST /api/sas/preparar` `{ ids }` → Preparado.
- `POST /api/sas/{id}/codigo/validar` e `POST /api/sas/{id}/codigo` `{ sa_codigo, confirmacoes }`: `SA_CODIGO_TROCADO` (CIENCIA) se diferente do sugerido. Fica *Aguardando Mega* e o sistema já tenta confirmar.
- `POST /api/sas/verificar` `{ ids? }` ("Verificar no Mega agora") → `{ verificados, confirmados, erro }`.
- `POST /api/sas/nf` `{ ids, numero, emitente, data? }`: NF só fiscal do caminho B2 (linhas `CORTE_ITU`).
- 📋 F1.1: "Exportar pedidos selecionados" e "Exportar SAs novos para o Renato" (Excel, layout da planilha de SA).

## 8. T06 Entrada por NF ✅ (Operação RJ)

- `GET /api/conteineres?busca=` (lista para o campo contêiner) e `GET /api/entradas-nf`.
- `POST /api/entradas-nf/validar` e `POST /api/entradas-nf`:

```json
{ "numero": "12345", "data": "2026-11-03", "fornecedor": "EASON", "conteiner": "CH50XY",
  "itens": [ { "liga": "H13", "formato": "RETANGULAR", "espessura": 50, "largura": 610, "diametro": null,
               "descricao_nf": "...", "pecas": 4, "peso_kg": 9000, "comprimento": "2800-6000", "custo_kg": null } ],
  "confirmacoes": {} }
```

`comprimento` (opcional) faz parte da identidade do material (P28(2), R053(3), 2026-11-12): com comprimento (`"2425"`, faixa `"2800-6000"`, "mm" e espaços ignorados), o lote vai para o item "<liga> <bitola>X<comprimento>" (linha própria na T04/T07, `chave_material` com o comprimento); sem comprimento, para o item sem comprimento.

Ocorrências: `NF_DUPLICADA`, `SEM_ITENS`, `LIGA_DESCONHECIDA#n`, `BITOLA_INCOMPLETA#n`, `PESO_TEORICO_DIFERENTE#n` (ALERTA, > 20 %). Gravou: `201` com `{ id, numero, fornecedor, data, conteiner, itens: [{ lote_id, ... }] }`; cada item vira um lote RJ no Rio.

## 9. T17, T18 e T05 ✅

- `POST /api/lotes/{id}/destinacoes` `{ tipo: RESERVA|RESTRICAO, descricao, kg?, validade? }` (Estoque Itu, Análise) e `POST /api/destinacoes/{id}/encerrar`.
- `POST /api/lotes/{id}/ajuste/validar` e `POST /api/lotes/{id}/ajuste` `{ saldo_contado_kg, justificativa }` (Estoque Itu).
- `POST /api/movimentos/{id}/estorno` `{ justificativa }` (Estoque Itu; Operação RJ só o próprio corte). Corte RJ só antes de entrar em COP; o estorno do corte devolve a solicitação para Enviada/Parcial.
- `POST /api/lotes/{id}/atribuir-origem` `{ conteiner, lote_pai_id?, justificativa }` (Estoque Itu) **[P07]**.

## 10. T23 Parâmetros e notificações ✅

- `GET /api/parametros` → `[{ chave, valor, tipo, descricao, atualizado_em }]`; `PATCH /api/parametros/{chave}` `{ valor }` (Admin).
- Migração **0008** (2026-11-11) cria `TOLERANCIA_EXCESSO_RJ_INTEIRO_PCT` = 8 (T13, material inteiro do RJ, P22(a)) e `SA_JANELA_ANTES_DIAS` = 7 (confirmação do SA no Mega a partir de N dias antes da data do SA, P24; antes fixo no código).
- `GET /api/notificacoes?somente_nao_lidas=` → `{ itens: [{ id, tipo, texto, link, criado_em, lida }], nao_lidas }`; `POST /api/notificacoes/{id}/lida`; `POST /api/notificacoes/lidas`. O `link` aponta para a rota de tela sugerida (`/fila-rj?solicitacao=7`, `/sa?cop=601`, `/cops/1`, `/recebimentos/1`, `/solicitacoes/7`).

## 10.1 Mega: sincronização e OP ✅ (2026-11-03, chat BANCO E TESTES)

- `POST /api/mega/sincronizar` (Estoque Itu, Análise, Admin) → `{ estoque: <sync>, sa: <sync> }`; `409` se já houver uma rodando. `<sync>` = `{ id, tipo: ESTOQUE|SA, gatilho: AGENDADA|MANUAL, situacao: OK|ERRO, iniciado_em, terminado_em, ultimo_lancamento, detalhes }`.
- `GET /api/mega/sincronizacoes?limite=20` → `{ ultima_ok, itens[] }` (para "Mega atualizado em …").
- `GET /api/mega/op/{n}`: também `pedido`, `cliente_codigo`, `tipo`, `estrutura[]` (R027).

## 11. T03 Painel com pendências ✅ (2026-11-04)

`GET /api/painel/pendencias` (todos os perfis; o Admin recebe os três grupos). A barra de estoque continua em `GET /api/painel/resumo`.

```json
{ "perfil": "ESTOQUE",
  "grupos": { "ESTOQUE": [ { "codigo": "SA_SEGURANDO_COP", "titulo": "SAs pendentes segurando COP no RJ",
                             "quantidade": 1, "nivel": "ALERTA", "link": "/sa", "itens": [ { ... } ] } ] },
  "atrasos": { "NORMAL": 5, "ATENCAO": 1, "ATRASADO": 1 },
  "divergencias_mega": { "quantidade": 3, "limite_kg": 5 },
  "ultima_sincronizacao": { "terminado_em": "2026-11-04T13:00:41-03:00", "situacao_ultima_tentativa": "OK" } }
```

- `nivel`: `ALERTA` (destacar) ou `NORMAL`; com `quantidade` 0 vem sempre `NORMAL`. `itens` traz no máximo 10 (o `link` abre a lista completa). A ordem dos grupos é a ordem de exibição.
- **ESTOQUE** (Fabiano, Matheus): `SA_SEGURANDO_COP` (itens `{cop_id, cop, sas_pendentes, itens, fechado_em}`, sempre no topo), `COP_EM_TRANSITO` (COPs no formato da lista do §4), `PECA_INTEIRA_AGUARDANDO_CORTE` e `MATERIAL_INSUFICIENTE` (solicitações `{id, numero, op, cliente, quantidade, prazo, situacao, atraso, dias_em_aberto, material, conteiner}`), `SA_SEM_CONFIRMACAO` (`{id, op, situacao, sa_codigo, criado_em}`, passou do prazo de 48 h).
- **OPERACAO_RJ** (Marcelo): `FILA_CORTE` (por prazo), `FILA_CORTE_ATRASADA`, `CORTES_FORA_DE_COP` (formato de `cortes-prontos`), `COP_ABERTO`, `COP_AGUARDANDO_SA`, `COP_AGUARDANDO_NF`.
- **ANALISE** (Renato): `RESERVA_VENCENDO` (`{destinacao_id, lote_id, lote, tipo, descricao, kg, validade}`, próximos 7 dias), `DIVERGENCIA_MEGA` (itens da T16), `EXCECOES_SEMANA` (`{movimento_id, lote_id, tipo, kg, op, codigos, justificativa, usuario, criado_em}`).
- `atrasos`: solicitações Enviadas, Parciais e com Material insuficiente por faixa (7 / 15 dias). `divergencias_mega.quantidade` vem `null` para a Operação RJ (não enxerga o Estoque Mega).
- **Entradas Mega a classificar (T15)** ainda não existem (F1.1): o grupo não aparece.

## 12. T16 Conciliação com o Mega, versão mínima ✅ (2026-11-04, só leitura)

`GET /api/conciliacao?somente_divergentes=false` (Estoque Itu, Análise, Admin):

```json
{ "limite_kg": 5, "ultima_sincronizacao": "2026-11-04T13:00:41-03:00",
  "totais": { "codigos": 403, "ok": 400, "mega_maior": 2, "mega_menor": 1, "saldo_mega_kg": 219453.8,
              "soma_lotes_kg": 219441.3 },
  "itens": [ { "codigo": 78290, "descricao": "IMP-H13 24X62MM", "saldo_mega_kg": 5210.0, "soma_lotes_kg": 5198.0,
               "diferenca_kg": 12.0, "status": "MEGA_MAIOR", "lotes": 1 } ] }
```

- Só códigos do catálogo (`item_mp` com código Mega) e só lotes do **Estoque Mega** (ITU/ITU). `diferenca_kg` = Mega − lotes. `status`: `OK` (|diferença| ≤ `DIVERGENCIA_MEGA_KG`), `MEGA_MAIOR`, `MEGA_MENOR`. Ordem: divergentes primeiro, maior diferença primeiro.
- O saldo do Mega é o da última sincronização (06h, 13h ou "Sincronizar agora"); mostrar `ultima_sincronizacao` no topo.
- 📋 F1.1: "Ver movimentos", "Ajustar lote" e "Marcar como explicada".

## 13. Exportações em Excel ✅ (2026-11-04)

Respondem um arquivo `.xlsx` (download direto; `Content-Disposition: attachment`). Mesmos filtros e mesma visibilidade das telas.

| Botão | Endpoint | Filtros |
|---|---|---|
| T04 "Exportar para Excel" (por lote) | `GET /api/exportar/lotes.xlsx` | os de `GET /api/lotes` |
| T04 (agrupado por liga × bitola, 2026-11-11) | `GET /api/exportar/lotes-agrupado.xlsx` (colunas "Liga × bitola" e "Código(s) Itu") | os de `GET /api/lotes` |
| T08 "Exportar" | `GET /api/exportar/solicitacoes.xlsx` | os de `GET /api/solicitacoes` |
| T14 "Exportar pedidos selecionados" | `GET /api/exportar/sas.xlsx?ids=3&ids=4` | `ids`, ou os de `GET /api/sas` |

O de SA sai no **layout da planilha de SA** (DATA, OP, CLIENTE, COD. ITEM, MATERIAL, DIMENSÃO, ORIGEM, QTDE, PESO, VALOR PRECIFICADOR, COD.MEGA SEMI ACAB., DESCRIÇÃO, NCM, ICMS, IPI, PEDIDO, NF) mais COP e situação. 📋 F1.1: "Exportar SAs novos para o Renato" com a marca de exportado.

## 14. Avisos automáticos do sino ✅ (2026-11-04)

Gerados pelo agendador (a cada 5 min), **uma vez por documento**, e lidos em `GET /api/notificacoes`. Tipos novos: `SA_SEM_CONFIRMACAO` (Estoque Itu e Admin, passou de 48 h), `SOLICITACAO_ATRASADA` (Estoque Itu e Operação RJ, passou de 15 dias), `RESERVA_VENCENDO` (quem criou a reserva, 7 dias antes; `link` = `/lotes/{id}?destinacao={id}`) e `RESUMO_EXCECOES` (Admin, a partir das 07h, exceções do dia anterior; `link` = `/relatorios/excecoes?dia=AAAA-MM-DD`).

## 15. T15 Entradas Mega a classificar (mínima) ✅ (2026-11-06, migração 0007)

Perfis: lista e detalhe = Estoque Itu, Análise, Admin; criar lote e "Não é entrada" = Estoque Itu e Admin; reabrir = só Admin; Operação RJ recebe 403 em tudo.

A pendência é **por código Mega** e nasce/atualiza/fecha na sincronização (6h, 13h, "Sincronizar agora"): `diferença = saldo Mega − lotes ITU/ITU − explicadas`; acima de `DIVERGENCIA_MEGA_KG` há uma pendência ABERTA. Código que só o Mega tem ("Código novo") só entra se teve entrada (ED) na janela de 120 dias copiada do Mega.

| Endpoint | O que faz |
|---|---|
| `GET /api/entradas-mega?situacao=ABERTA\|RESOLVIDA\|DESCARTADA\|ENCERRADA\|TODAS&busca=` | `{itens, total, limite_kg, abertas, mega_indisponivel, aviso, ultima_sincronizacao}`; ordem: mais antiga primeiro |
| `GET /api/entradas-mega/{id}` | uma pendência |
| `GET /api/entradas-mega/motivos` | `[{codigo, descricao}]` do "Não é entrada" |
| `POST /api/entradas-mega/{id}/criar-lote/validar` e `POST .../criar-lote` | padrão prévia/gravação (§1.5) |
| `POST /api/entradas-mega/{id}/nao-e-entrada` | `{motivo, justificativa}` |
| `POST /api/entradas-mega/{id}/reabrir` | `{justificativa}` (Admin, só Descartada). Se já houver outra ABERTA do mesmo código (0008: só uma por código), a reaberta vira ENCERRADA e os kg voltam para a aberta |

Item da lista: `id, codigo, descricao, situacao, saldo_mega_kg, soma_lotes_kg, diferenca_kg, criado_em` (1ª sincronização em que apareceu = "há quanto tempo"), `ultima_entrada {nf, data, kg, tpm}` (null se não houver), `etiquetas` (`CODIGO_NOVO`, `CODIGO_RETO`), `aviso` (só código RETO), `item {id, liga, formato, bitola, criado_pela_t15}` ou, no código novo, `item_sugerido {legivel, liga, formato, bitola, mensagem}` para o operador conferir, e nas tratadas `motivo`, `motivo_descricao`, `justificativa`, `tratada_por`, `tratada_em`.

**criar-lote** (corpo): `peso_kg` (>0), `conteiner` **ou** `sem_conteiner: true`, `pecas?`, `data_entrada?` (padrão: data da NF no Mega; não pode ser futura), `nf?` (padrão: NF do Mega), `observacao?`, `confirmacoes`. Ocorrências: ERRO `PESO_ACIMA_DA_DIFERENCA` ("O lote não pode ter mais kg do que o Mega tem a mais (X kg). Informe um peso menor ou confira a diferença."), `CONTEINER_OBRIGATORIO`, `CONTEINER_FORMATO`, `DATA_FUTURA`, `ITEM_ILEGIVEL` ("Não consegui ler liga e bitola desta descrição. Peça ao Admin para cadastrar o item no Catálogo (T22)."), `PENDENCIA_TRATADA`; CIENCIA `CONTEINER_REPETIDO` (já existe lote ativo com o mesmo contêiner e material; exige justificativa em `confirmacoes`). A prévia traz em `resultado`: `diferenca_kg`, `diferenca_restante_kg`, `peso_sugerido_kg`, `nf`, `data_entrada` e, no código novo, `item_novo {liga, formato, bitola}`. Gravação: lote ITU/ITU, ATIVO, movimento `ENTRADA` (estornável), `origem_identificada = false` sem contêiner, tipo RETO se o item é RETO; código novo cria o item com `criado_pela_t15 = true`. Peso menor que a diferença mantém a pendência ABERTA com o resto; dentro de `DIVERGENCIA_MEGA_KG` vira RESOLVIDA. Resposta 201: `{lote {id, codigo, peso_kg}, pendencia, diferenca_restante_kg, mensagem}` (mensagem: "Lote L-000123 criado com 1.450,0 kg (código 78290). Diferença restante: 0,0 kg.").

**nao-e-entrada**: `motivo` = `ESTORNO_BAIXA_MEGA | ACERTO_INVENTARIO_MEGA | TRANSFERENCIA_CODIGOS | OUTRO`; `justificativa` com 10+ caracteres (400 "Escreva pelo menos 10 caracteres."). A pendência vira DESCARTADA e os kg ficam como diferença explicada (não volta; só o aumento posterior gera nova pendência). Pendência já tratada: 400 "Esta pendência já foi tratada por NOME às HH:MM. Atualize a lista."

Estados: `ABERTA`, `RESOLVIDA`, `DESCARTADA`, `ENCERRADA` (o Mega voltou à tolerância sem ação). Desde a 0008 (R044) o banco garante: estados e motivos só da lista (CHECK) e **uma** ENTRADA ABERTA por código (índice único parcial).

**Painel e T16.** `GET /api/painel/pendencias` ganha `entradas_mega_a_classificar {quantidade}` (null para Operação RJ) e, no grupo ESTOQUE, a pendência `ENTRADA_MEGA_A_CLASSIFICAR` (link `/entradas-mega`). Cada item de `GET /api/conciliacao` ganha `explicada_na_t15` (bool), `explicada_t15_kg`, `diferenca_nao_explicada_kg` e `explicacoes [{pendencia_id, kg, motivo, motivo_descricao, justificativa, usuario, em}]`; `diferenca_kg` continua sendo a total e `status` (OK / MEGA_MAIOR / MEGA_MENOR) é calculado sobre a **não explicada**: vermelho só para ela.

## 16. Aba "RETO por origem" da T04 ✅ (2026-11-06)

`GET /api/lotes/reto-por-origem` (todos os perfis; Operação RJ com o estoque travado em `RJ_NO_RIO`). Filtros: `estoque`, `liga` (repetível), `bitola_origem` (texto, ex. `45x610`), `bitola_de`/`bitola_ate` (1ª medida da bitola de origem), `conteiner`, `codigo_mega`, `com_saldo` (padrão true), `incluir_sobras` (padrão false: só RETO), `criado_de`/`criado_ate`.

Resposta: `{ligas [{liga, bitolas [{bitola_origem, total_kg, conteineres [{conteiner, conteiner_texto ("não informado" se só a bitola), estoque, classe, lotes, saldo_kg, reservado_kg, disponivel_kg, lotes_detalhe [{id, codigo, saldo_kg}]}]}], sem_origem {texto: "Sem origem identificada", lotes, saldo_kg, reservado_kg, disponivel_kg, por_estoque, lotes_detalhe} | null, totais}], totais, lotes [um por lote], vazio, mensagem_vazio, estoque_travado}`. `totais` = `{com_origem_kg, so_bitola_kg, sem_origem_kg, total_kg, lotes, reservado_kg, disponivel_kg}`; o `total_kg` geral é a soma dos saldos dos lotes RETO nos filtros (bate com a T04 filtrada por formato RETO). Classes: `COMPLETA` (bitola e contêiner da raiz da árvore), `SO_BITOLA` (medida anotada na carga, contêiner "não informado"; desde 2026-11-11 a medida vem **normalizada** no formato da bitola do cadastro, R044: "IMP-D2 25X610MM" → `25X610`, "30,5x610" → `30,5X610`, liga diferente da do lote fica na frente, `D2 36X510`; faixa "45x510~610" fica em maiúsculo sem espaço), `SEM_ORIGEM` (linha própria por liga, nunca somada a uma bitola). Para Operação RJ: `mensagem_vazio = "Nenhum RETO no RJ no Rio"`.

Excel: `GET /api/exportar/reto-por-origem.xlsx` (mesmos filtros), duas abas "Resumo" e "Lotes"; as 2 primeiras linhas trazem a data/hora e os filtros usados.

## 16.1 Visibilidade da Operação RJ [P10] ✅ (2026-11-06)

- `GET /api/painel/resumo`: para Operação RJ só vem `baldes.RJ_NO_RIO` (as chaves `ESTOQUE_MEGA` e `RJ_EM_ITU` não existem) e `total_kg` é só dele.
- `GET /api/painel/pendencias`: para Operação RJ, `divergencias_mega.quantidade` e `entradas_mega_a_classificar.quantidade` = null, `ultima_sincronizacao` vem com valores null.
- `GET /api/lotes/{id}/arvore`: filhos que não são do RJ no Rio (ex.: sobra e RETO em Itu) não aparecem, nem os saldos; a raiz é o ancestral mais alto ainda visível.
- T14: `GET /api/sas`, `GET /api/sas/{id}` e `/api/exportar/sas.xlsx` só devolvem SAs de itens de COP; SA de corte em Itu (B2) dá 404 no detalhe.

## 17. Ainda não implementado

📋 F1.1: tratamento da T16 (ver movimentos, ajustar, marcar como explicada), T19 Relatórios, T26, exportação para o Renato com marca, PDFs (romaneio do COP, ficha do lote). A **impressão da Fila RJ (T09)** usa `GET /api/fila-rj`; se faltar campo, o FUNCIONAL indica e eu acrescento.
