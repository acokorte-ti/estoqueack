# Controle de Matéria-Prima AçoKorte — Análise do Processo Atual

Documento de levantamento (versão 1, 28/10/2026). Fontes: as quatro planilhas da pasta do projeto e a explicação do Eduardo.

---

## 1. Visão geral do cenário

A empresa tem duas plantas: **AçoKorte Matriz (Itu)**, que é a filial 3 no ERP Mega, e **AçoKorte Barra Mansa (RJ)**. Do ponto de vista do estoque, a matéria-prima (MP) fica em três "baldes":

| Balde | Fiscal | Físico | Fonte do saldo | Como baixa |
|---|---|---|---|---|
| ESTOQUE MEGA | Itu | Itu | ERP Mega (relatório "Inventário C.M.D.", atualizado semanalmente) | Baixa direta na OP, no ERP |
| ESTOQUE RJ (no Rio) | RJ | RJ | Planilha manual | Cadastro de SA → gera saldo no ERP → baixa na OP; a planilha é abatida à mão |
| ESTOQUE RJ (em Itu) | RJ | Itu | Planilha manual | Igual ao anterior. Vem de peças inteiras trazidas do RJ ("TRAZER 01 PEÇA…"), cortadas em Itu, e a sobra fica em Itu |

O fluxo RJ, que é o mais complexo, funciona assim:

```
Solicitação de corte (Itu preenche)  →  Corte no RJ (Fio Certo) ou peça inteira vem p/ Itu
        │                                        │
        ▼                                        ▼
 Liberação pós-corte (peso real, qtde, COP)  →  Recebimento em Itu (check final)
        │
        ▼
 Cadastro de SA (código Mega do semiacabado, peso, valor, NCM, ICMS/IPI, NF transf.)
        │
        ▼
 Atualização manual: ESTOQUE 2026 (por contêiner, OP no comentário da célula)
                     + Estoque Geral (colunas RJ no Rio / RJ em Itu, por material)
```

---

## 2. O que cada planilha faz hoje

### 2.1 CONTROLE DE CORTE – RIO DE JANEIRO (aba "CONTROLE - CORTE RJ", tabela `CONTROLE_RJ`, cerca de 804 linhas desde mar/2025)

- **Itu preenche:** data, OP, item (puxado por PROCV/XLOOKUP de `historicos_pcp.xlsx`, a base Mega no SharePoint do PCP), medida acabada, quantidade, MP, contêiner (CT), peso, cliente, instrução de corte e prazo.
- **O RJ (Fio Certo) preenche:** peças cortadas, data de liberação, observação (geralmente o **COP nº**, que parece ser o romaneio ou lote de envio), PESO2 (peso real) e "liberação feita".
- **Itu confirma:** "Recebido ACK?", e a coluna STATUS calcula os dias em aberto (Normal ≤7, Atenção ≤15, Atrasado acima disso).
- Cerca de 100 linhas são do tipo "TRAZER 01 PEÇA…", ou seja, a barra ou chapa inteira vai para Itu e vira **RJ em Itu**.
- Aba "calculo de peso": calcula o peso teórico de reto (C×L×E×7,85) e de redondo/anel. Há uma nota que fala em densidade **7,9**, e a fórmula usa **7,85**.

### 2.2 ATUAL_PLANILHA_CADASTRO PRODUTOS SEMI ACABADO (abas 2016 a 2025)

- Cada linha é um SA: data, OP, cliente, código do item, material, dimensão (bitola ou "RETO"), **ORIGEM = contêiner**, quantidade, peso, valor (R$/kg da MP × peso ÷ quantidade), **código Mega do SA**, descrição, NCM, ICMS, IPI, pedido, NF Fio Certo/Médio Vale, NF de transferência, NF Renafer e regularização Rio.
- A aba "2025" na verdade já contém dados até **28/10/2026** (cerca de 1.775 linhas).
- **Cruzamento:** das 303 OPs de corte de 2025, 297 aparecem no SA. O vínculo OP ↔ corte ↔ SA existe na prática, mas ninguém o garante.

### 2.3 ESTOQUE 2026 (planta RJ)

- Uma linha por **contêiner + bitola**: contêiner, MP, valor unitário (R$/kg), quantidade de chapas/barras, peso inicial e saldo.
- As colunas G em diante recebem os **kg consumidos**, e o **nº da OP e a data ficam em comentários da célula** (cerca de 500 comentários). O saldo é `=E - G - H - …`.
- Aba HISTORICO: entradas desde 2017 (data, CT, descrição, quantidade, peso, saídas, sucata, histórico em texto).
- São 38 contêineres e 210 linhas, com cerca de 245 t em saldo.

### 2.4 Materia Prima Geral 20out

- **Estoque Geral** (cerca de 591 materiais): código Mega, descrição, comprimento fixado, ESTOQUE MEGA (PROCV na aba "estoque atual"), UM, RJ no Rio, RJ em Itu, observações, clientes/uso.
- **estoque atual**: relatório do Mega colado na planilha (inventário C.M.D., 20/10/2026), com código, descrição, UM, saldo físico, preço médio e valor total.
- **Quant consider**: conferência para achar códigos do Mega que não estão no Estoque Geral.
- Totais: Mega cerca de 187 t, RJ no Rio cerca de 240 t e RJ em Itu cerca de 28 t.

---

## 3. Problemas encontrados (riscos e por que um sistema resolve)

1. **Rastreabilidade das sobras e do RETO se perde.** "RJ em Itu" e "RETO" são somados **por material**, sem guardar a origem (contêiner + bitola original). Esse é o problema principal que você descreveu. O H13 RETO, por exemplo, tem 2.240 kg no Mega e 5.658 kg em RJ/Itu, e ninguém sabe de quais bitolas e contêineres vieram.
2. **Dados críticos em comentários de célula.** A OP e a data de cada consumo ficam em comentários, então não dá para consultar, totalizar nem auditar.
3. **Fórmulas quebradas ou inconsistentes.** A coluna UM do Estoque Geral está toda com `#REF!`. Na ESTOQUE 2026, as fórmulas de saldo têm intervalos diferentes por linha (algumas terminam em T, outras em Y, outras em `-AE`), o que pode deixar consumos fora do saldo sem ninguém perceber.
4. **Cadastro de materiais sem padrão.** O mesmo aço aparece como "CR12MOV", "CR12 MOV" e "Cr12MoV"; "DC53C" e "DC53-C"; "12746", "1.2746" e "DIN 1.2746"; "Ø", "RED" e "REDØ". Cerca de 140 linhas do Estoque Geral não têm código. Sem um cadastro mestre, não dá para cruzar com segurança.
5. **Retrabalho e dupla digitação.** O mesmo consumo é lançado no Corte, no SA, no ESTOQUE 2026 e no Estoque Geral. Os totais das planilhas não batem exatamente entre si (cerca de 240 t no Estoque Geral contra cerca de 245 t no ESTOQUE 2026).
6. **Dependência de arquivo externo.** O Controle de Corte depende de `historicos_pcp.xlsx` no SharePoint. Se o arquivo mudar de lugar, as fórmulas quebram.
7. **Sem controle de acesso nem trilha de auditoria.** Qualquer pessoa altera qualquer número e não fica registrado quem mudou, quando ou por quê.
8. **Uma aba por ano no SA**, e a aba 2025 já recebe dados de 2026. Isso fragmenta o histórico.
9. **Densidade e peso teórico** sem padrão (7,85 na fórmula e 7,9 na nota), e não fica claro quando o peso é pesado na balança e quando é calculado.

---

## 4. Conceito central proposto (para validar)

O sistema passa a controlar **LOTES** de MP, e não "saldo por material":

- **Lote de origem:** entrada de NF por contêiner + material + bitola. Guarda peso inicial, peças, R$/kg, planta fiscal e local físico.
- **Lote derivado (sobra/RETO):** criado sempre que um corte gera sobra, e **aponta para o lote pai**. A pergunta "quantos kg de H13 RETO vieram da bitola 35×610 do contêiner CH11EA?" passa a ter resposta exata.
- **Movimentos:** entrada, solicitação de corte, corte, transferência física RJ→Itu, cadastro de SA, baixa por OP, ajuste de inventário e sucata/perda de corte. Cada um com usuário, data/hora e documento (OP, SA, COP, NF).
- O saldo de cada balde (Mega, RJ no Rio, RJ em Itu) passa a ser **calculado** a partir dos movimentos, e não digitado.

---

## 5. Perguntas em aberto

Estão listadas na conversa. As respostas serão incorporadas na versão 2 deste documento, junto com a proposta de arquitetura, as telas, o fluxo de aprovações e o modelo de dados.
