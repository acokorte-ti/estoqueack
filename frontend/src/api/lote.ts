/** Tipos do lote (contrato v1 §3 e §4, F1 §9). */

export interface Lote {
  id: number; codigo: string; conteiner: string | null; liga: string; formato: string; bitola: string; descricao: string | null;
  codigo_mega: number | null; estoque: "ESTOQUE_MEGA" | "RJ_NO_RIO" | "RJ_EM_ITU"; tipo: "ORIGINAL" | "SOBRA" | "RETO";
  saldo_kg: number; reservado_kg: number; disponivel_kg: number;
  origem: { lote: string; conteiner: string | null; bitola: string } | null;
  indicadores: { destinacao: boolean; nota: boolean; origem_nao_identificada: boolean };
  /** spec v3.7 §1.4 / P28: identidade liga × bitola (× comprimento × múltiplo). Campo novo, opcional. */
  chave_material?: string | null;
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

/** Linha do "agrupado por liga × bitola" (contrato v1 §3, spec v3.7 §1.4). `chave`, `codigos_itu` e `ligas` são novos (opcionais). */
export interface Agrupado { liga: string; formato: string; bitola: string; lotes: number; saldo_kg: number; reservado_kg: number; disponivel_kg: number;
  por_estoque: Record<string, number>; chave?: string; codigos_itu?: number[]; ligas?: string[]; codigo_mega?: number | null }

export const chaveAgrupado = (g: Agrupado) => g.chave ?? `${g.liga} ${g.bitola}`;

/** Filtros de /lotes que trazem os lotes de uma linha agrupada (a lista é refinada pela chave_material). */
export function filtrosDaLinha(g: Agrupado): Record<string, string | number | undefined>[] {
  const nums = (g.bitola.match(/\d+(?:[.,]\d+)?/g) ?? []).map((x) => Number(x.replace(",", ".")));
  const med: Record<string, number | undefined> =
    g.formato === "REDONDO" ? { diametro_de: nums[0], diametro_ate: nums[0] }
    : g.formato === "RETANGULAR" ? { espessura_de: nums[0], espessura_ate: nums[0], largura_de: nums[1], largura_ate: nums[1] } : {};
  return (g.ligas?.length ? g.ligas : [g.liga]).map((liga) => ({ liga, formato: g.formato, ...med }));
}

export const TIPO_LOTE: Record<string, string> = { ORIGINAL: "Original", SOBRA: "Sobra", RETO: "RETO" };
