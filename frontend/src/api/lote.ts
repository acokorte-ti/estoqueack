/** Tipos do lote (contrato v1 §3 e §4, F1 §9). */

export interface Lote {
  id: number; codigo: string; conteiner: string | null; liga: string; formato: string; bitola: string; descricao: string | null;
  codigo_mega: number | null; estoque: "ESTOQUE_MEGA" | "RJ_NO_RIO" | "RJ_EM_ITU"; tipo: "ORIGINAL" | "SOBRA" | "RETO";
  saldo_kg: number; reservado_kg: number; disponivel_kg: number;
  origem: { lote: string; conteiner: string | null; bitola: string } | null;
  indicadores: { destinacao: boolean; nota: boolean; origem_nao_identificada: boolean };
}

export interface LoteDetalhe extends Lote {
  peso_inicial_kg: number | null; pecas_iniciais: number | null; documento_entrada: string | null; data_entrada: string | null;
  custo_kg: number | null; status: string; criado_em: string;
}

export interface NoArvore { id: number; codigo: string; tipo: string; bitola: string; conteiner: string | null; saldo_kg: number; estoque?: string; filhos: NoArvore[] }

export interface Movimento {
  id: number; data: string; tipo: string; tipo_descricao: string; kg: number; saldo_apos_kg: number;
  op: number | null; cop: number | null; sa: number | null; documento: string | null; usuario: string | null;
  justificativa: string | null; estorno_de: number | null;
  /** R036: a API diz se aceita estorno (carga, corte RJ já em COP e já estornado = false). */
  estornavel?: boolean; da_carga?: boolean;
}

export interface Destinacao { id: number; tipo: "RESERVA" | "RESTRICAO"; descricao: string; kg: number | null; validade: string | null; criado_por: string | null; criado_em: string }
export interface Nota { id: number; texto: string; usuario: string | null; criado_em: string }

export interface Agrupado { liga: string; formato: string; bitola: string; lotes: number; saldo_kg: number; reservado_kg: number; disponivel_kg: number;
  por_estoque: Record<string, number> }

export const TIPO_LOTE: Record<string, string> = { ORIGINAL: "Original", SOBRA: "Sobra", RETO: "RETO" };
