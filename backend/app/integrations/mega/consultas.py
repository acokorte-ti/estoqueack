"""Consultas SQL ao Mega (Oracle 19c, esquema ACOKORTE). Mapeadas e validadas em 2026-10-29.

Detalhes e validação em docs/integracao_mega.md. Sempre com bind variables (:nome).
"""

ESQUEMA = "ACOKORTE"
FILIAL_ITU = 3           # "00003 - AÇOKORTE - MATRIZ"
TPM_REQUISICAO_OP = 13   # Requisição Materiais Ordem de Produção (MVT_ST_NUMDOC = nº da OP)

# PRO_ORDENS.ORD_ST_SITUACAO → (descrição, aceita solicitação/corte). Domínio no comentário da coluna no Oracle
# (validado em 2026-11-03, filial 3: EN 80.351, CA 2.975, AB 1.344, FP 211, LB 15, PL 1, SI 0).
# True = aceita; False = bloqueia (OP_ENCERRADA); None = ainda não aberta → ALERTA (OP_NAO_ABERTA).
# FP/LB/PL nunca tiveram baixa de MP (TPM 13) nem data de abertura real.
SITUACOES_OP: dict[str, tuple[str, bool | None]] = {
    "AB": ("Aberta", True),
    "EN": ("Encerrada", False),
    "CA": ("Cancelada", False),
    "SI": ("Simulada", None),
    "PL": ("Planejada", None),
    "FP": ("Firme planejada", None),
    "LB": ("Liberada", None),
}

# Saldo físico por código de MP numa data de corte (soma de movimentos).
# Validado: diferença 0,000 kg contra o relatório "Inventário C.M.D." de 20/10/2026.
SALDOS_MP = f"""
SELECT m.PRO_IN_CODIGO,
       MAX(p.PRO_ST_DESCRICAO)  AS descricao,
       MAX(p.UNI_ST_UNIDADE)    AS um,
       SUM(DECODE(m.MVT_ST_ENTRSAIDA, 'ED', 1, 'SD', -1, 0) * m.MVT_RE_QUANTIDADE) AS saldo,
       MAX(p.PRO_RE_PESOESPECIFICO) AS peso_especifico
  FROM {ESQUEMA}.EST_VW_MOVIMENTOESTOQUE m
  JOIN {ESQUEMA}.EST_PRODUTOS p ON p.PRO_IN_CODIGO = m.PRO_IN_CODIGO
 WHERE m.FIL_IN_CODIGO = :filial
   AND p.PRO_ST_DEFITEM = 'MP'
   AND m.MVT_DT_MOVIMENTO < :data_corte
 GROUP BY m.PRO_IN_CODIGO
"""

# Movimentos novos desde o último lançamento lido (sincronização incremental).
MOVIMENTOS_DESDE = f"""
SELECT m.MVT_IN_LANCAM, m.MVT_DT_MOVIMENTO, m.MVT_ST_ENTRSAIDA, m.TPM_IN_CODIGO, m.TPM_ST_DESCRICAO,
       m.MVT_ST_NUMDOC, m.PRO_IN_CODIGO, m.MVT_RE_QUANTIDADE, m.PRO_IN_CODIGODEST, m.MVT_BO_ESTORNO
  FROM {ESQUEMA}.EST_VW_MOVIMENTOESTOQUE m
  JOIN {ESQUEMA}.EST_PRODUTOS p ON p.PRO_IN_CODIGO = m.PRO_IN_CODIGO
 WHERE m.FIL_IN_CODIGO = :filial
   AND p.PRO_ST_DEFITEM = 'MP'
   AND m.MVT_IN_LANCAM > :ultimo_lancamento
 ORDER BY m.MVT_IN_LANCAM
 FETCH FIRST 5000 ROWS ONLY
"""

# Ordem de produção com pedido e cliente (validado em 2026-11-03 contra as 79 OPs da planilha de corte desde
# 01/09/2026: cliente bate em 79/79). Caminho: PRO_ORIGEM tipo 'D' (pedido de venda) → VEN_PEDIDOVENDA →
# GLO_AGENTES (nome fantasia). Desde 2025, toda OP com origem 'D' tem 1 cliente só; 37 OPs têm 2–4 linhas de
# origem (mesmo cliente) → vale a de menor ORI_IN_SEQUENCIA. Sem origem 'D' (146 OPs em 2026, ex.: 100591), o
# ORD_ST_ALTERNATIVO guarda o nº do pedido (série '1'). OP016 (estoque) e OS001 sem pedido → cliente NULL.
ORDEM_PRODUCAO = f"""
SELECT o.ORD_IN_CODIGO, o.PRO_IN_CODIGO, p.PRO_ST_DESCRICAO, ag.AGN_ST_FANTASIA AS cliente,
       o.ORD_ST_SITUACAO, o.ORD_DT_ABERTURA_REAL, o.ORD_RE_QTDE_ORDEM, o.ORD_DT_RECEBIMENTO,
       NVL(vo.PED_IN_CODIGO, va.PED_IN_CODIGO) AS pedido,
       NVL(vo.CLI_IN_CODIGO, va.CLI_IN_CODIGO) AS cliente_codigo,
       o.TPO_ST_CODIGO_TIPO
  FROM {ESQUEMA}.PRO_ORDENS o
  LEFT JOIN {ESQUEMA}.EST_PRODUTOS p ON p.PRO_IN_CODIGO = o.PRO_IN_CODIGO
  LEFT JOIN (SELECT ori.ORG_TAB_IN_CODIGO, ori.ORG_PAD_IN_CODIGO, ori.ORG_IN_CODIGO, ori.ORG_TAU_ST_CODIGO,
                    ori.ORD_TAB_IN_CODIGO, ori.ORD_SEQ_IN_CODIGO, ori.ORD_IN_CODIGO,
                    MIN(ori.PED_SER_ST_CODIGO) KEEP (DENSE_RANK FIRST ORDER BY ori.ORI_IN_SEQUENCIA)
                        AS PED_SER_ST_CODIGO,
                    MIN(ori.PED_IN_CODIGO) KEEP (DENSE_RANK FIRST ORDER BY ori.ORI_IN_SEQUENCIA)
                        AS PED_IN_CODIGO
               FROM {ESQUEMA}.PRO_ORIGEM ori
              WHERE ori.ORI_CH_TIPOORIGEM = 'D' AND ori.ORD_IN_CODIGO = :numero
              GROUP BY ori.ORG_TAB_IN_CODIGO, ori.ORG_PAD_IN_CODIGO, ori.ORG_IN_CODIGO, ori.ORG_TAU_ST_CODIGO,
                       ori.ORD_TAB_IN_CODIGO, ori.ORD_SEQ_IN_CODIGO, ori.ORD_IN_CODIGO) ori
    ON ori.ORG_TAB_IN_CODIGO = o.ORG_TAB_IN_CODIGO AND ori.ORG_PAD_IN_CODIGO = o.ORG_PAD_IN_CODIGO
   AND ori.ORG_IN_CODIGO = o.ORG_IN_CODIGO AND ori.ORG_TAU_ST_CODIGO = o.ORG_TAU_ST_CODIGO
   AND ori.ORD_TAB_IN_CODIGO = o.ORD_TAB_IN_CODIGO AND ori.ORD_SEQ_IN_CODIGO = o.ORD_SEQ_IN_CODIGO
   AND ori.ORD_IN_CODIGO = o.ORD_IN_CODIGO
  LEFT JOIN {ESQUEMA}.VEN_PEDIDOVENDA vo
    ON vo.ORG_TAB_IN_CODIGO = ori.ORG_TAB_IN_CODIGO AND vo.ORG_PAD_IN_CODIGO = ori.ORG_PAD_IN_CODIGO
   AND vo.ORG_IN_CODIGO = ori.ORG_IN_CODIGO AND vo.ORG_TAU_ST_CODIGO = ori.ORG_TAU_ST_CODIGO
   AND vo.SER_ST_CODIGO = ori.PED_SER_ST_CODIGO AND vo.PED_IN_CODIGO = ori.PED_IN_CODIGO
  LEFT JOIN {ESQUEMA}.VEN_PEDIDOVENDA va
    ON ori.PED_IN_CODIGO IS NULL
   AND va.ORG_TAB_IN_CODIGO = o.ORG_TAB_IN_CODIGO AND va.ORG_PAD_IN_CODIGO = o.ORG_PAD_IN_CODIGO
   AND va.ORG_IN_CODIGO = o.ORG_IN_CODIGO AND va.ORG_TAU_ST_CODIGO = o.ORG_TAU_ST_CODIGO
   AND va.SER_ST_CODIGO = '1' AND TO_CHAR(va.PED_IN_CODIGO) = o.ORD_ST_ALTERNATIVO
  LEFT JOIN {ESQUEMA}.GLO_AGENTES ag
    ON ag.AGN_TAB_IN_CODIGO = NVL(vo.CLI_TAB_IN_CODIGO, va.CLI_TAB_IN_CODIGO)
   AND ag.AGN_PAD_IN_CODIGO = NVL(vo.CLI_PAD_IN_CODIGO, va.CLI_PAD_IN_CODIGO)
   AND ag.AGN_IN_CODIGO = NVL(vo.CLI_IN_CODIGO, va.CLI_IN_CODIGO)
 WHERE o.ORD_IN_CODIGO = :numero AND o.FIL_IN_CODIGO = :filial
"""

# Baixas de MP feitas no Mega para uma OP (para conciliação com o EstoqueACK).
BAIXAS_DA_OP = f"""
SELECT m.MVT_DT_MOVIMENTO, m.PRO_IN_CODIGO, m.PRO_ST_DESCRICAO, m.MVT_RE_QUANTIDADE, m.MVT_BO_ESTORNO
  FROM {ESQUEMA}.EST_VW_MOVIMENTOESTOQUE m
 WHERE m.FIL_IN_CODIGO = :filial AND m.TPM_IN_CODIGO = {TPM_REQUISICAO_OP} AND m.MVT_ST_NUMDOC = :op
"""

# SA: cadastro + entradas (ED) na filial 3 desde a data = carga de saldo. A VALIDAR com SAs reais (F1-F).
SITUACAO_SA = f"""
SELECT p.PRO_IN_CODIGO, p.PRO_ST_DESCRICAO, p.PRO_DT_INCLUSAO,
       (SELECT NVL(SUM(m.MVT_RE_QUANTIDADE), 0)
          FROM {ESQUEMA}.EST_VW_MOVIMENTOESTOQUE m
         WHERE m.PRO_IN_CODIGO = p.PRO_IN_CODIGO AND m.FIL_IN_CODIGO = :filial
           AND m.MVT_ST_ENTRSAIDA = 'ED' AND m.MVT_DT_MOVIMENTO >= :desde) AS kg_entrada
  FROM {ESQUEMA}.EST_PRODUTOS p
 WHERE p.PRO_IN_CODIGO = :codigo
"""

# Produtos SA (semiacabados) por texto da descrição.
BUSCAR_SA = f"""
SELECT p.PRO_IN_CODIGO, p.PRO_ST_DESCRICAO, p.PRO_DT_INCLUSAO
  FROM {ESQUEMA}.EST_PRODUTOS p
 WHERE UPPER(p.PRO_ST_DESCRICAO) LIKE :texto
   AND UPPER(p.PRO_ST_DESCRICAO) LIKE 'SA %'
 FETCH FIRST 50 ROWS ONLY
"""
