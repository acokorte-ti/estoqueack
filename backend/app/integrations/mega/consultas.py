"""Consultas SQL ao Mega (Oracle 19c).

!!! ATENÇÃO: os nomes de tabelas/colunas abaixo são MARCADORES e precisam ser
substituídos pelos nomes reais do dicionário de dados do Mega. Roteiro em
docs/integracao_mega.md (como descobrir as tabelas a partir do relatório
"Inventário do Tipo - C.M.D." e da tela de OP).

Todas as consultas usam bind variables (:nome) — nunca concatenar texto do usuário.
"""

FILIAL_ITU = 3   # "00003 - AÇOKORTE - MATRIZ" no relatório de inventário

SALDOS_MP = """
SELECT pro.codigo, pro.descricao, pro.unidade, sal.saldo_fisico, sal.preco_medio
  FROM MEGA_PRODUTO pro            -- TODO: tabela real de produtos
  JOIN MEGA_SALDO_ESTOQUE sal      -- TODO: tabela real de saldo por filial
    ON sal.produto = pro.codigo
 WHERE sal.filial = :filial
   AND pro.grupo IN ('000975')     -- TODO: grupo "Matéria Prima Importada" / subgrupo "000986 - Aço"
"""

ORDEM_PRODUCAO = """
SELECT op.numero, op.item, it.descricao, cli.nome, op.situacao, op.data_emissao
  FROM MEGA_ORDEM_PRODUCAO op      -- TODO
  LEFT JOIN MEGA_PRODUTO it ON it.codigo = op.item
  LEFT JOIN MEGA_CLIENTE cli ON cli.codigo = op.cliente
 WHERE op.numero = :numero
"""

BUSCAR_SA = """
SELECT pro.codigo, pro.descricao, pro.data_cadastro
  FROM MEGA_PRODUTO pro            -- TODO
 WHERE UPPER(pro.descricao) LIKE :texto
   AND pro.descricao LIKE 'SA %'
 FETCH FIRST 50 ROWS ONLY
"""
