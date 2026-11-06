#!/usr/bin/env bash
# Conferência independente do banco (implantação e qualquer recarga), só leitura.
# Complementa a conferência (a)–(d) do relatório da carga com contas feitas direto no PostgreSQL:
#   1. nenhum lote com saldo negativo
#   2. em todo lote, saldo = soma dos movimentos
#   3. (a) Estoque Mega: soma dos lotes ITU/ITU por código × saldo do Mega (mega_saldo), tolerância 5 kg
#   4. totais por estoque (RJ no Rio, RJ em Itu, Estoque Mega) e contagens de solicitações, COPs e SAs
# Uso no system-lab: deploy/implantacao/conferir.sh      (sai com código 1 se 1, 2 ou 3 falharem)
set -euo pipefail
cd "$(dirname "$0")/../.."
PSQL=${PSQL_CMD:-docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -AtF " | " -f -'}
q() { eval "$PSQL"; }

LOTES_MEGA="SELECT i.codigo_mega AS codigo, SUM(l.saldo_kg) AS kg FROM lote l JOIN item_mp i ON i.id = l.item_mp_id
             WHERE l.planta_fiscal = 'ITU' AND l.local_fisico = 'ITU' AND i.codigo_mega IS NOT NULL GROUP BY i.codigo_mega"
NEG=$(q <<<"SELECT count(*) FROM lote WHERE saldo_kg < 0;")
DIF=$(q <<<"SELECT count(*) FROM (SELECT l.id FROM lote l LEFT JOIN movimento m ON m.lote_id = l.id
            GROUP BY l.id, l.saldo_kg HAVING abs(l.saldo_kg - COALESCE(SUM(m.kg), 0)) > 0.001) x;")
MEGA=$(q <<<"WITH x AS ($LOTES_MEGA) SELECT count(*) FROM x JOIN mega_saldo s ON s.codigo = x.codigo
             WHERE abs(x.kg - s.saldo_kg) > 5;")
echo "1. lotes com saldo negativo ............. $NEG"
echo "2. lotes com saldo ≠ soma dos movimentos . $DIF"
echo "3. códigos Mega com diferença > 5 kg ..... $MEGA"
echo "4. lotes ativos por estoque (estoque | lotes | kg):"
q <<<"SELECT CASE WHEN planta_fiscal = 'RJ' AND local_fisico = 'RJ' THEN 'RJ no Rio'
                  WHEN planta_fiscal = 'RJ' THEN 'RJ em Itu' ELSE 'Estoque Mega' END, count(*), round(sum(saldo_kg), 1)
        FROM lote WHERE status = 'ATIVO' GROUP BY 1 ORDER BY 1;" | sed 's/^/     /'
echo "   contagens:"
q <<<"SELECT 'solicitações', count(*) FROM solicitacao_corte
      UNION ALL SELECT 'fila RJ (enviadas/parciais)', count(*) FROM solicitacao_corte
                 WHERE situacao IN ('ENVIADA', 'CORTADA_PARCIAL')
      UNION ALL SELECT 'COPs', count(*) FROM cop
      UNION ALL SELECT 'SAs', count(*) FROM cadastro_sa
      UNION ALL SELECT 'movimentos', count(*) FROM movimento
      UNION ALL SELECT 'usuários ativos', count(*) FROM usuario WHERE ativo;" | sed 's/^/     /'
if [ "$MEGA" != "0" ]; then
  echo "   códigos com diferença (código | lotes | Mega), até 20:"
  q <<<"WITH x AS ($LOTES_MEGA) SELECT x.codigo, round(x.kg, 1), round(s.saldo_kg, 1) FROM x
          JOIN mega_saldo s ON s.codigo = x.codigo WHERE abs(x.kg - s.saldo_kg) > 5
         ORDER BY abs(x.kg - s.saldo_kg) DESC LIMIT 20;" | sed 's/^/     /'
fi
if [ "$NEG" = "0" ] && [ "$DIF" = "0" ] && [ "$MEGA" = "0" ]; then echo "CONFERENCIA_OK"; exit 0; fi
echo "CONFERENCIA_COM_DIFERENCA"; exit 1
