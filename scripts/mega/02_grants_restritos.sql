-- EstoqueACK: troca o acesso amplo do estoqueack_ro (descoberta) por SELECT só nos objetos usados.
-- Rodar como DBA (SYS/ADMIN) ou como ACOKORTE, no PDB DBMEGAXT_PDB1. Gerado em 2026-11-03 (chat BANCO E TESTES).
-- Objetos = os de backend/app/integrations/mega/consultas.py. Todos são do ACOKORTE, inclusive as tabelas de base da
-- visão EST_VW_MOVIMENTOESTOQUE (EST_MOVIMENTO, EST_MOVPENDENTE, EST_PRODUTOS, EST_TIPOMOVTO, GLO_GRUPO_USUARIO),
-- então o GRANT na visão funciona sem GRANT OPTION.
-- Sem linhas em branco (PL/SQL Developer). Para desfazer: GRANT SELECT ANY TABLE, SELECT ANY DICTIONARY TO estoqueack_ro;
GRANT SELECT ON ACOKORTE.EST_PRODUTOS            TO estoqueack_ro;
GRANT SELECT ON ACOKORTE.EST_VW_MOVIMENTOESTOQUE TO estoqueack_ro;
GRANT SELECT ON ACOKORTE.EST_SALDOFIN            TO estoqueack_ro;
GRANT SELECT ON ACOKORTE.PRO_ORDENS              TO estoqueack_ro;
GRANT SELECT ON ACOKORTE.PRO_ORIGEM              TO estoqueack_ro;
GRANT SELECT ON ACOKORTE.PRO_DEMANDA_DEP         TO estoqueack_ro;
GRANT SELECT ON ACOKORTE.VEN_PEDIDOVENDA         TO estoqueack_ro;
GRANT SELECT ON ACOKORTE.GLO_AGENTES             TO estoqueack_ro;
GRANT SELECT ON ACOKORTE.TRF_NCM                 TO estoqueack_ro;
REVOKE SELECT ANY TABLE      FROM estoqueack_ro;
REVOKE SELECT ANY DICTIONARY FROM estoqueack_ro;
-- Conferência (deve listar só CREATE SESSION e os 9 objetos acima):
SELECT 'SYS' AS tipo, privilege AS privilegio, NULL AS objeto FROM dba_sys_privs WHERE grantee = 'ESTOQUEACK_RO' UNION ALL SELECT 'OBJ', privilege, owner || '.' || table_name FROM dba_tab_privs WHERE grantee = 'ESTOQUEACK_RO' ORDER BY 1, 3;
