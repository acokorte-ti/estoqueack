"""Consultas SQL ao Mega (Oracle 19c, esquema ACOKORTE). Mapeadas e validadas em 2026-10-29.

Detalhes e validação em docs/integracao_mega.md. Sempre com bind variables (:nome).
"""

ESQUEMA = "ACOKORTE"
FILIAL_ITU = 3           # "00003 - AÇOKORTE - MATRIZ"
TPM_REQUISICAO_OP = 13   # Requisição Materiais Ordem de Produção (MVT_ST_NUMDOC = nº da OP)

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

# Ordem de produção. Cliente: a mapear (via pedido/demanda). Situação 'AB' = aberta.
ORDEM_PRODUCAO = f"""
SELECT o.ORD_IN_CODIGO, o.PRO_IN_CODIGO, p.PRO_ST_DESCRICAO, CAST(NULL AS VARCHAR2(120)) AS cliente,
       o.ORD_ST_SITUACAO, o.ORD_DT_ABERTURA_REAL, o.ORD_RE_QTDE_ORDEM, o.ORD_DT_RECEBIMENTO
  FROM {ESQUEMA}.PRO_ORDENS o
  LEFT JOIN {ESQUEMA}.EST_PRODUTOS p ON p.PRO_IN_CODIGO = o.PRO_IN_CODIGO
 WHERE o.ORD_IN_CODIGO = :numero AND o.FIL_IN_CODIGO = :filial
"""

# Baixas de MP feitas no Mega para uma OP (para conciliação com o EstoqueACK).
BAIXAS_DA_OP = f"""
SELECT m.MVT_DT_MOVIMENTO, m.PRO_IN_CODIGO, m.PRO_ST_DESCRICAO, m.MVT_RE_QUANTIDADE, m.MVT_BO_ESTORNO
  FROM {ESQUEMA}.EST_VW_MOVIMENTOESTOQUE m
 WHERE m.FIL_IN_CODIGO = :filial AND m.TPM_IN_CODIGO = {TPM_REQUISICAO_OP} AND m.MVT_ST_NUMDOC = :op
"""

# Produtos SA (semiacabados) por texto da descrição.
BUSCAR_SA = f"""
SELECT p.PRO_IN_CODIGO, p.PRO_ST_DESCRICAO, p.PRO_DT_INCLUSAO
  FROM {ESQUEMA}.EST_PRODUTOS p
 WHERE UPPER(p.PRO_ST_DESCRICAO) LIKE :texto
   AND UPPER(p.PRO_ST_DESCRICAO) LIKE 'SA %'
 FETCH FIRST 50 ROWS ONLY
"""
