-- ============================================================================
-- EstoqueACK — usuário SOMENTE LEITURA no Oracle 19c do Mega
-- Executar como DBA (SYS/SYSTEM ou usuário com privilégio de administração),
-- conectado ao PDB onde está o esquema do Mega.
--
-- Passo 1: troque <SENHA_FORTE> (mín. 16 caracteres) e rode o bloco A.
-- Passo 2: rode o bloco B para dar acesso de leitura ao dicionário (descoberta).
-- Passo 3: depois do mapeamento, rode o bloco C (GRANT SELECT só nas tabelas
--          necessárias) e o bloco D (revoga o acesso amplo da descoberta).
-- ============================================================================

-- A) Usuário e perfil com limites (evita consulta pesada derrubar o ERP)
CREATE PROFILE estoqueack_ro_perfil LIMIT
  SESSIONS_PER_USER       4
  CPU_PER_CALL            30000      -- centésimos de segundo (5 min)
  LOGICAL_READS_PER_CALL  5000000
  IDLE_TIME               30         -- minutos
  FAILED_LOGIN_ATTEMPTS   5
  PASSWORD_LOCK_TIME      1/96;      -- 15 minutos

CREATE USER estoqueack_ro IDENTIFIED BY "<SENHA_FORTE>" PROFILE estoqueack_ro_perfil;
GRANT CREATE SESSION TO estoqueack_ro;

-- B) Somente durante a DESCOBERTA: ler qualquer tabela/visão e o dicionário.
--    (SELECT ANY TABLE não permite alterar nada; revogado no bloco D.)
GRANT SELECT ANY TABLE      TO estoqueack_ro;
GRANT SELECT ANY DICTIONARY TO estoqueack_ro;

-- C) Depois do mapeamento — exemplo (substituir pelos nomes reais encontrados):
-- GRANT SELECT ON <ESQUEMA>.<TABELA_PRODUTO>   TO estoqueack_ro;
-- GRANT SELECT ON <ESQUEMA>.<TABELA_SALDO>     TO estoqueack_ro;
-- GRANT SELECT ON <ESQUEMA>.<TABELA_OP>        TO estoqueack_ro;
-- GRANT SELECT ON <ESQUEMA>.<TABELA_MOVIMENTO> TO estoqueack_ro;

-- D) Encerrar a descoberta (OBRIGATÓRIO antes de ir para produção):
-- REVOKE SELECT ANY TABLE      FROM estoqueack_ro;
-- REVOKE SELECT ANY DICTIONARY FROM estoqueack_ro;

-- Conferência: o usuário NÃO pode ter nenhum privilégio de escrita
-- SELECT * FROM dba_sys_privs WHERE grantee = 'ESTOQUEACK_RO';
-- SELECT * FROM dba_tab_privs WHERE grantee = 'ESTOQUEACK_RO' AND privilege <> 'SELECT';
