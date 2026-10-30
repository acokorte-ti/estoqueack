# Contrato da API do EstoqueACK

Versão 1, de 2026-10-29, escrita pelo chat TÉCNICO em resposta ao pedido R010 do FRONTEND.

A referência executável é o OpenAPI em `https://estoque.acokorte.com.br/api/docs`, disponível só em homologação. Este documento explica as **convenções** e o **contrato por tela**. Os campos e as regras seguem a `03_especificacao_funcional.md`. Se alguma coisa divergir, vale a especificação, e o TÉCNICO corrige a API.

Situação dos endpoints: ✅ no ar · 🛠 em construção · 📋 contrato definido, ainda não implementado.

---

## 1. Convenções

### 1.1 Base, sessão e CSRF

- Todos os endpoints ficam sob `/api`.
- A sessão é mantida por cookie `HttpOnly`, criado em `POST /api/auth/login`.
- Todo `POST`, `PATCH` e `DELETE` precisa do header `X-CSRF-Token` com o valor do cookie `ack_csrf`. O `api/cliente.ts` do frontend já faz isso.
- Códigos de autenticação:
  - `401`: sessão expirou. O frontend leva para T01.
  - `403`: o perfil não tem permissão, ou a senha é temporária e precisa ser trocada.

### 1.2 Tipos

| Tipo | Formato no JSON | Exemplo |
|---|---|---|
| Peso | `number` em kg, até 3 casas | `1288.0` |
| Medida | `number` em mm | `70`, `610` |
| Data | `string` ISO `AAAA-MM-DD` | `"2026-12-09"` |
| Data/hora | `string` ISO 8601 com fuso | `"2026-10-29T14:03:11-03:00"` |
| Estoque (balde) | `"ESTOQUE_MEGA"`, `"RJ_NO_RIO"` ou `"RJ_EM_ITU"` | |
| Tipo de lote | `"ORIGINAL"`, `"SOBRA"` ou `"RETO"` | |

Números vão para o JSON **sem formatação**. Quem formata para a tela é o frontend (`kg()` em `cliente.ts`). A exceção são os textos prontos para leitura, como `mensagem` e `frase`, que já vêm em formato brasileiro ("1.288,0 kg", "5 %"). Isso atende ao pedido R011.

### 1.3 Erros

```json
{ "detail": "Mensagem pronta para mostrar ao usuário." }
```

| Código | Significado |
|---|---|
| `422` | Campo inválido. `detail` é uma lista no formato do Pydantic; o frontend mostra "Confira os campos preenchidos". |
| `409` | Conflito (duplicidade) ou validação pendente (ver §1.5). |
| `404` | O recurso não existe. |

### 1.4 Listas paginadas

Os parâmetros são `?pagina=1&por_pagina=50`, com no máximo 200 por página. A resposta tem este formato:

```json
{ "itens": [ ... ], "total": 210, "pagina": 1, "por_pagina": 50 }
```

Também aceitam `?ordem=campo` ou `?ordem=-campo` (o `-` indica ordem decrescente).

### 1.5 Prévia e validação sem gravar

Toda ação que grava algo no estoque tem **dois endpoints**:

| Endpoint | O que faz |
|---|---|
| `POST /api/<ação>/validar` | **Não grava nada.** Devolve as ocorrências e a frase de resultado |
| `POST /api/<ação>` | Grava. Repete as mesmas validações no servidor, porque nunca confia só na prévia |

Resposta do `/validar`, sempre `200`:

```json
{
  "ok": false,
  "ocorrencias": [
    { "codigo": "EXCESSO_TOLERANCIA", "nivel": "CIENCIA",
      "mensagem": "Peso real 90,0 kg está 8,0 % acima do previsto (83,3 kg). Limite: 5 %. Justifique o uso de 6,7 kg a mais de matéria-prima.",
      "dados": { "previsto_kg": 83.3, "real_kg": 90.0, "excedente_kg": 6.7, "desvio_pct": 8.04 } }
  ],
  "resultado": {
    "frase": "Lote L-000451 passa de 1.288,0 kg para 0 kg. Novo lote RETO L-000452 com 446,0 kg, origem H13 70×610 / CH25K.",
    "efeitos": [ { "lote": "L-000451", "antes_kg": 1288.0, "depois_kg": 0.0 },
                 { "lote": "(novo RETO)", "antes_kg": 0.0, "depois_kg": 446.0 } ]
  }
}
```

Os níveis de ocorrência são `ERRO` (bloqueia), `CIENCIA` (exige "estou ciente" com justificativa de pelo menos 10 caracteres) e `ALERTA` (só aviso). O `ok` só é `true` quando não há `ERRO` nem `CIENCIA` pendente. O `resultado` aparece mesmo com alertas, para a tela mostrar como vai ficar.

Para gravar, o corpo do `POST` leva os mesmos dados mais as confirmações:

```json
{ "...dados da ação...": "...",
  "confirmacoes": { "EXCESSO_TOLERANCIA": "Só havia bitola 50x610, OP urgente" } }
```

- Gravou: `201`, com o registro criado.
- Ainda há pendências (ERRO, ou CIENCIA sem justificativa válida): `409`, com o **mesmo corpo do `/validar`**. O frontend mostra de novo o painel de validações.

Toda justificativa aceita é gravada no movimento (`confirmacoes`) e na auditoria.

---

## 2. Endpoints que já existem

| Método e caminho | Tela | Perfil | Situação |
|---|---|---|---|
| `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/eu`, `POST /api/auth/trocar-senha` | T01, T02 | todos | ✅ |
| `GET/POST /api/usuarios`, `PATCH /api/usuarios/{id}`, `POST /api/usuarios/{id}/redefinir-senha` | T21 | ADMIN | ✅ |
| `GET/POST /api/ligas`, `PATCH /api/ligas/{id}` | T22 | leitura: todos; escrita: ADMIN | ✅ |
| `POST /api/calculadora/peso`, `POST /api/calculadora/validar-peso-real` | T20 | todos | ✅ |
| `GET /api/painel/resumo` | T03 | todos | ✅ |

---

## 2.1 Usuários, login e recuperação de senha (2026-10-30, pedido do Eduardo)

**Login no padrão `nome.sobrenome`**, minúsculo e sem acento (ex.: `fabiano.camargo`). O backend converte para minúsculo e recusa outros formatos com `422`.

| Método e caminho | O que faz |
|---|---|
| `POST /api/auth/login` ✅ | Corpo `{ login, senha, lembrar }`. `lembrar: true` ("Manter conectado") faz a sessão durar 30 dias; sem ele, dura 10 h. **O sistema não guarda a senha:** para lembrar a senha, use o gerenciador do navegador (os campos já têm `autocomplete="username"` e `"current-password"`) |
| `POST /api/usuarios` ✅ (ADMIN) | Corpo `{ login, nome, email, perfil, planta, senha, trocar_senha }`. `senha` vazia faz o sistema gerar uma temporária, que volta em `senha_temporaria` (é a única vez que ela aparece). `senha` preenchida precisa ter pelo menos `SENHA_TAMANHO_MINIMO` caracteres (padrão 6; pode ser só números), senão volta `400`. `trocar_senha` (padrão `true`) obriga a troca no próximo acesso; **com senha temporária a troca é sempre obrigatória** (o `trocar_senha: false` é ignorado). O mesmo vale em `/redefinir-senha`. Login ou e-mail repetido devolve `409` |
| `PATCH /api/usuarios/{id}` ✅ (ADMIN) | Também aceita `trocar_senha` e `email` |
| `POST /api/usuarios/{id}/redefinir-senha` ✅ (ADMIN) | Corpo **opcional** `{ senha, trocar_senha }`, com as mesmas regras. Encerra as sessões abertas do usuário |
| `POST /api/auth/recuperar` ✅ | Corpo `{ identificador }` (login ou e-mail). Responde **sempre** `202` com a mesma `mensagem`, exista o usuário ou não. Se existir, estiver ativo e tiver e-mail, envia o link `https://estoque.acokorte.com.br/redefinir-senha?token=…`, que vale **30 min** e é de **uso único**. Limites: 3 por usuário por hora e 10 por IP por hora |
| `POST /api/auth/recuperar/verificar` ✅ | `{ token }` → `{ valido: true, login }` ou `{ valido: false, mensagem }`. A tela de redefinição chama isso ao abrir |
| `POST /api/auth/recuperar/redefinir` ✅ | `{ token, nova_senha }` → `204`, ou `400` com a mensagem (política de senha, link inválido ou expirado). Encerra todas as sessões do usuário. Depois, o usuário entra pela tela de login normal |

As rotas de recuperação **não exigem sessão nem CSRF**, porque o usuário não está logado. Todas as ações ficam na auditoria.

## 3. T04: Consulta de estoque

### `GET /api/lotes` ✅

| Parâmetro | Tipo | Observação |
|---|---|---|
| `estoque` | `ESTOQUE_MEGA` / `RJ_NO_RIO` / `RJ_EM_ITU` | omitido = todos |
| `liga` | código, ex.: `H13` | |
| `formato` | `RETANGULAR` / `REDONDO` / `RETO` | |
| `espessura_de`, `espessura_ate`, `largura_de`, `largura_ate`, `diametro_de`, `diametro_ate` | mm | faixa |
| `conteiner` | código, ex.: `CH11EA` | |
| `codigo_mega` | inteiro | |
| `com_saldo` | `true`/`false` | padrão `true` |
| `com_destinacao` | `true` | só com reserva ou restrição vigente |
| `origem_nao_identificada` | `true` | |
| `busca` | texto | lote, contêiner ou descrição |
| `pagina`, `por_pagina`, `ordem` | | ordem padrão: `liga,bitola,conteiner` |

Cada item da lista:

```json
{ "id": 451, "codigo": "L-000451", "conteiner": "CH25K",
  "liga": "H13", "formato": "RETANGULAR", "bitola": "70X610", "descricao": "H13 70x610",
  "codigo_mega": null, "estoque": "RJ_EM_ITU", "tipo": "ORIGINAL",
  "saldo_kg": 1288.0, "reservado_kg": 0.0, "disponivel_kg": 1288.0,
  "origem": { "lote": "L-000123", "conteiner": "CH25K", "bitola": "70X610" },
  "indicadores": { "destinacao": false, "nota": false, "origem_nao_identificada": false } }
```

`origem` é `null` em lote `ORIGINAL`. `reservado_kg` soma as solicitações *Enviadas* e as reservas com kg. Até a tabela de solicitações existir, conta só as reservas.

### `GET /api/lotes/agrupado` ✅

Mesmos filtros, agrupado por liga + formato + bitola, como no Estoque Geral de hoje:

```json
{ "itens": [ { "liga": "H13", "formato": "RETO", "bitola": "RETO", "lotes": 7,
               "saldo_kg": 7897.8, "reservado_kg": 0.0, "disponivel_kg": 7897.8,
               "por_estoque": { "ESTOQUE_MEGA": 2240.0, "RJ_NO_RIO": 0.0, "RJ_EM_ITU": 5657.8 } } ],
  "total": 1, "pagina": 1, "por_pagina": 50 }
```

### `GET /api/lotes.xlsx` 📋

Mesmos filtros. Gera o arquivo Excel da lista (botão "Exportar para Excel").

---

## 4. T05: Detalhe do lote

| Método e caminho | Situação | Resposta |
|---|---|---|
| `GET /api/lotes/{id}` | ✅ | Cabeçalho completo: os campos do item de lista mais `peso_inicial_kg`, `pecas_iniciais`, `documento_entrada`, `data_entrada`, `custo_kg` e `criado_em` |
| `GET /api/lotes/{id}/arvore` | ✅ | `{ "raiz": {nó}, "atual_id": 451 }`, em que cada nó é `{ id, codigo, tipo, bitola, conteiner, saldo_kg, filhos: [nó] }` |
| `GET /api/lotes/{id}/movimentos` | ✅ | Paginado, em ordem cronológica. Cada item: `{ id, data, tipo, tipo_descricao, kg, saldo_apos_kg, op, cop, sa, documento, usuario, justificativa, estorno_de }` |
| `GET /api/lotes/{id}/destinacoes` | ✅ | `[{ id, tipo, descricao, kg, validade, criado_por, criado_em }]`, só as vigentes |
| `GET /api/lotes/{id}/notas` | ✅ | `[{ id, texto, usuario, criado_em }]` |
| `POST /api/lotes/{id}/notas` | ✅ | `{ "texto": "..." }` → `201`. Todos os perfis |
| `GET /api/lotes/{id}/ficha.pdf` | 📋 | "Imprimir ficha do lote" |

"Adicionar reserva ou restrição" (T17) e "Ajustar saldo" (T18) seguem o padrão do §1.5 e serão detalhados quando essas telas forem construídas.

---

## 5. T07: Nova solicitação de corte

### Passo 1: `GET /api/mega/op/{numero}` ✅

O backend lê do Mega na hora (`PRO_ORDENS`):

```json
{ "numero": 100508, "item_codigo": 68092, "item_descricao": "PARTE/ACESSORIO (POS 1) 12X54X90MM",
  "cliente": null, "situacao": "AB", "situacao_descricao": "Aberta", "aberta": true,
  "quantidade": 128, "data_recebimento": "2026-12-09",
  "medida_sugerida": { "formato": "RETANGULAR", "espessura": 12, "largura": 54, "comprimento": 90 },
  "historico": { "solicitacoes": [], "sas": [] },
  "fonte": "MEGA" }
```

- OP inexistente: `404` com `"OP não encontrada no Mega."`.
- Mega fora do ar ou integração desligada: `503` com `{ "detail": "Mega indisponível…", "pode_digitar": true }`. O frontend libera a digitação manual com o aviso "dado não confirmado no Mega" (§7 da especificação).
- `cliente` vem `null` até o mapeamento do cliente terminar. `medida_sugerida` é interpretada a partir da descrição do item e pode vir `null`.

### Passo 2: `GET /api/lotes/compativeis` 📋

Parâmetros: `liga`, `formato`, `espessura`, `largura` (ou `diametro`), `comprimento` e `quantidade`. A resposta tem a forma do item de `GET /api/lotes`, mais `sobremetal_pct` e `peso_bruto_kg`. A ordem é a da especificação: menor sobremetal, depois o lote mais antigo.

### Passos 3 e 4: `POST /api/solicitacoes/validar` e `POST /api/solicitacoes` 📋

Corpo:

```json
{ "op": 100508,
  "medida": { "formato": "RETANGULAR", "espessura": 12, "largura": 54, "comprimento": 90 },
  "itens": [ { "lote_id": 451, "modo": "CORTAR_RJ", "quantidade": 128, "comprimento_corte": 95,
               "instrucao": "128 PEÇAS COM 95MM COMPRIMENTO" } ],
  "prazo": "2026-12-09", "observacao": null,
  "enviar": true,
  "confirmacoes": {} }
```

- `modo`: `CORTAR_RJ`, `TRAZER_INTEIRA` ou `CORTAR_ITU`.
- `enviar`: `false` salva como rascunho; `true` envia ao RJ.

O `/validar` devolve no `resultado` o `peso_peca_kg`, o `peso_bruto_kg` e o `sobremetal_pct` de cada item. As ocorrências possíveis são `OP_INEXISTENTE`, `OP_ENCERRADA`, `OP_DUPLICADA`, `BITOLA_MENOR_QUE_PECA`, `SOBREMETAL_ACIMA_TOLERANCIA`, `SALDO_INSUFICIENTE`, `USA_SALDO_RESERVADO` e `DESTINACAO_n`.

Isso depende da tabela `solicitacao_corte` (migração 0002), que entra na Fase 1 junto com T08 a T12.

---

## 6. Próximos contratos

Na ordem da Fase 1:

1. T08 a T12: solicitações, fila RJ, corte, COP e recebimento.
2. T13: corte em Itu.
3. T14: SA.
4. T17 e T18: reservas e ajustes.
5. T25: carga inicial.

Cada um entra neste documento **antes** de ser implementado, para o FRONTEND poder montar a tela em paralelo.
