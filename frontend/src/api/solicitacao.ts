/** Tipos e rótulos da solicitação de corte (contrato F1 §2). */

export type SituacaoSolic =
  | "RASCUNHO" | "ENVIADA" | "MATERIAL_INSUFICIENTE" | "CORTADA_PARCIAL" | "CORTADA" | "EM_COP" | "SA_PRONTO"
  | "EM_TRANSITO" | "AGUARDANDO_CORTE_ITU" | "CONCLUIDA" | "CANCELADA";

export type Modo = "CORTAR_RJ" | "TRAZER_INTEIRA";

export interface LoteResumo { id: number; codigo: string; liga: string; bitola: string; conteiner: string | null; estoque: string }

export interface SolicItem {
  id: number; numero: string; data: string; op: number; item_codigo: number | null; item_descricao: string | null;
  cliente: string | null; pedido: string | null; op_confirmada_mega: boolean;
  lote: LoteResumo; modo: Modo; quantidade: number; pecas_cortadas: number;
  peso_previsto_kg: number | null; peso_real_kg: number | null; reserva_kg: number | null;
  prazo: string | null; instrucao: string | null; instrucao_processo: string | null;
  situacao: SituacaoSolic; encerrada_saldo_pendente: boolean; motivo: string | null;
  dias_em_aberto: number | null; atraso: "NORMAL" | "ATENCAO" | "ATRASADO" | null;
  cops: { id: number; numero: number }[] | number[]; enviada_em: string | null;
  /** P26(1) opção A: OP que consome Itu + RJ (contrato F1 §1). Campo novo, opcional. */
  consumo_misto?: ConsumoMisto | null;
}

export interface ConsumoMisto { itu_kg: number; rj_kg: number; texto: string }

export const textoMisto = (c: ConsumoMisto) =>
  c.texto || `OP com consumo misto: Itu ${c.itu_kg.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} kg + RJ ${c.rj_kg.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} kg`;

export interface Medida { formato: "RETANGULAR" | "REDONDO"; espessura: number | null; largura: number | null; diametro: number | null; comprimento: number | null }

export interface Corte { id: number; lote: string; lote_id: number; pecas: number; peso_real_kg: number; comprimento_barra_mm: number | null;
  data_corte: string; estornado: boolean; cop: number | null; cop_item_id: number | null }

export interface SolicDetalhe extends SolicItem {
  medida_acabada: Medida | null; sobremetal_comprimento_mm: number | null; sobremetal_largura_mm: number | null;
  bruto: { espessura: number | null; largura: number | null; diametro: number | null; comprimento: number | null } | null;
  peso_peca_kg: number | null; sobremetal_pct: number | null; comprimento_barra_mm: number | null; observacao: string | null;
  confirmacoes: Record<string, string> | null; cortes: Corte[];
  sas: { id: number; situacao: string; sa_codigo: number | null }[];
}

export const SITUACAO_SOLIC: Record<SituacaoSolic, { nome: string; classe: string }> = {
  RASCUNHO: { nome: "Rascunho", classe: "" },
  ENVIADA: { nome: "Enviada ao RJ", classe: "info" },
  MATERIAL_INSUFICIENTE: { nome: "Material insuficiente", classe: "ruim" },
  CORTADA_PARCIAL: { nome: "Cortada parcial", classe: "atencao" },
  CORTADA: { nome: "Cortada", classe: "ok" },
  EM_COP: { nome: "Em COP", classe: "info" },
  SA_PRONTO: { nome: "SA pronto", classe: "info" },
  EM_TRANSITO: { nome: "Em trânsito", classe: "info" },
  AGUARDANDO_CORTE_ITU: { nome: "Aguardando corte em Itu", classe: "atencao" },
  CONCLUIDA: { nome: "Concluída", classe: "ok" },
  CANCELADA: { nome: "Cancelada", classe: "" },
};

export const ATRASO: Record<string, { nome: string; classe: string }> = {
  NORMAL: { nome: "Normal", classe: "ok" },
  ATENCAO: { nome: "Atenção", classe: "atencao" },
  ATRASADO: { nome: "Atrasado", classe: "ruim" },
};

export const MODO_NOME: Record<Modo, string> = { CORTAR_RJ: "Cortar no RJ", TRAZER_INTEIRA: "Peça inteira" };

export const material = (l: LoteResumo) => `${l.liga} ${l.bitola}`;
export const numerosCop = (c: SolicItem["cops"]) =>
  c.map((x) => (typeof x === "number" ? x : x.numero)).join(", ");
