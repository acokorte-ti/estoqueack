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

Parâmetros: `liga` (obrigatório), `formato` (`RETANGULAR`/`REDONDO`), `espessura`, `largura`, `diametro`, `comprimento`, `quantidade`, `estoque` (opcional). Resposta paginada `{ itens: [...], total }` (como `GET /api/lotes`). Traz lotes da liga **e das ligas equivalentes** (`liga_equivalente: true` → selo), cuja bitola comporta a medida acabada e com disponível > 0. Cada item tem os campos de `GET /api/lotes` mais `peso_previsto_kg`, `peso_peca_kg`, `sobremetal_pct` (estimados com 5 mm) e `substituido_por_id`. Ordem: menor sobremetal, depois o mais antigo.

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

Gravou: `201` com `{ "solicitacoes": [ <detalhe> ] }`.

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
  "dias_em_aberto": 0, "atraso": "NORMAL", "cops": [], "enviada_em": "..." }
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

Várias linhas = "Usar outro lote / dividir". Ocorrências: `SITUACAO_INVALIDA`, `DATA_CORTE_INVALIDA` (hoje até 7 dias atrás), `PECAS_ACIMA_SOLICITADO` (ALERTA), `LOTE_FORA_DO_RJ`, `SALDO_INSUFICIENTE`, `BITOLA_MENOR_QUE_PECA`, `LIGA_DIFERENTE` (ERRO no corte), `LOTE_TROCADO` (CIENCIA; o Fabiano é avisado), `DESTINACAO_n`, `EXCESSO_TOLERANCIA` / `ABAIXO_PREVISTO` (só no modo corte, sobre o previsto proporcional às peças; **peça inteira não tem regra dos 5 % aqui**). `resultado.efeitos[]` traz `antes_kg`/`depois_kg` por lote e `resultado.previsto_kg`. Gravou: `201` com o detalhe da solicitação.

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
- No `resultado`: `perda_kg`, `perda_esperada_kg`, `previsto_kg`, `gera_sa` (lote fiscal RJ que não é o 1º corte da peça inteira da mesma OP), `instrucao_mega` (lote Mega: "Baixar 105,0 kg do código 78290 na OP 100508. Transferir 12,0 kg do código 78290 para o código 1698 (IMP-H13 RETO).").
- Ocorrências: `OP_INEXISTENTE`, `OP_ENCERRADA`, `OP_NAO_CONFIRMADA`, `LOTE_FORA_DE_ITU`, `PESO_INVALIDO`, `SALDO_INSUFICIENTE`, `EXCESSO_TOLERANCIA`, `ABAIXO_PREVISTO`, `SOMA_MAIOR_QUE_LOTE`, `PERDA_CORTE_ALTA`, `USA_SALDO_RESERVADO`, `DESTINACAO_n`, `DATA_CORTE_INVALIDA`.
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

Ocorrências: `NF_DUPLICADA`, `SEM_ITENS`, `LIGA_DESCONHECIDA#n`, `BITOLA_INCOMPLETA#n`, `PESO_TEORICO_DIFERENTE#n` (ALERTA, > 20 %). Gravou: `201` com `{ id, numero, fornecedor, data, conteiner, itens: [{ lote_id, ... }] }`; cada item vira um lote RJ no Rio.

## 9. T17, T18 e T05 ✅

- `POST /api/lotes/{id}/destinacoes` `{ tipo: RESERVA|RESTRICAO, descricao, kg?, validade? }` (Estoque Itu, Análise) e `POST /api/destinacoes/{id}/encerrar`.
- `POST /api/lotes/{id}/ajuste/validar` e `POST /api/lotes/{id}/ajuste` `{ saldo_contado_kg, justificativa }` (Estoque Itu).
- `POST /api/movimentos/{id}/estorno` `{ justificativa }` (Estoque Itu; Operação RJ só o próprio corte). Corte RJ só antes de entrar em COP; o estorno do corte devolve a solicitação para Enviada/Parcial.
- `POST /api/lotes/{id}/atribuir-origem` `{ conteiner, lote_pai_id?, justificativa }` (Estoque Itu) **[P07]**.

## 10. T23 Parâmetros e notificações ✅

- `GET /api/parametros` → `[{ chave, valor, tipo, descricao, atualizado_em }]`; `PATCH /api/parametros/{chave}` `{ valor }` (Admin).
- `GET /api/notificacoes?somente_nao_lidas=` → `{ itens: [{ id, tipo, texto, link, criado_em, lida }], nao_lidas }`; `POST /api/notificacoes/{id}/lida`; `POST /api/notificacoes/lidas`. O `link` aponta para a rota de tela sugerida (`/fila-rj?solicitacao=7`, `/sa?cop=601`, `/cops/1`, `/recebimentos/1`, `/solicitacoes/7`).

## 10.1 Mega: sincronização e OP ✅ (2026-11-03, chat BANCO E TESTES)

- `POST /api/mega/sincronizar` (Estoque Itu, Análise, Admin) → `{ estoque: <sync>, sa: <sync> }`; `409` se já houver uma rodando. `<sync>` = `{ id, tipo: ESTOQUE|SA, gatilho: AGENDADA|MANUAL, situacao: OK|ERRO, iniciado_em, terminado_em, ultimo_lancamento, detalhes }`.
- `GET /api/mega/sincronizacoes?limite=20` → `{ ultima_ok, itens[] }` (para "Mega atualizado em …").
- `GET /api/mega/op/{n}`: também `pedido`, `cliente_codigo`, `tipo`, `estrutura[]` (R027).

## 11. Ainda não implementado (próximos)

📋 Painel com pendências por perfil (T03), T25 carga inicial, exportações em Excel, impressões em PDF (lista de corte, romaneio, ficha do lote).
