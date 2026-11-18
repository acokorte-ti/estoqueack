/** Tipos e rótulos do COP e do recebimento (contrato F1 §4 e §5). */
import type { Modo } from "./solicitacao";

export type SituacaoCop = "ABERTO" | "FECHADO" | "AGUARDANDO_NF" | "ENVIADO" | "RECEBIDO_PARCIAL" | "RECEBIDO";

export interface CopItem {
  id: number; liberacao_id: number; solicitacao_id: number; op: number; item_codigo: number | null; cliente: string | null;
  material: string; conteiner: string | null; lote: string; modo: Modo; pecas: number; peso_kg: number;
  situacao: "EM_COP" | "EM_TRANSITO" | "RECEBIDO";
  /** SA do item (contrato F1 §4); opcional para tolerar resposta sem o campo. */
  sa?: {
    id: number; situacao: string; sa_codigo: number | null;
    /** contrato §4 (spec v3.16, 2026-11-18): R$/kg do precificador e valor por peça; opcionais para tolerar API antiga */
    rs_kg?: number | null; valor_precificador?: number | null;
  } | null;
  nf: { numero: string; emitente: string } | null;
  peso_conferido_kg: number | null; lote_itu_id: number | null;
  divergencias: { tipo: string; pecas: number | null; kg: number | null; observacao: string }[];
}

export interface Cop {
  id: number; numero: number; situacao: SituacaoCop; data: string; fechado_em: string | null; enviado_em: string | null;
  qtd_itens: number; peso_total_kg: number; nfs: string[]; observacao: string | null; itens?: CopItem[];
}

export interface CortePronto { liberacao_id: number; solicitacao_id: number; op: number; cliente: string | null; material: string;
  lote: string; modo: Modo; pecas: number; peso_kg: number; data_corte: string }

export const SITUACAO_COP: Record<SituacaoCop, { nome: string; classe: string }> = {
  ABERTO: { nome: "Aberto", classe: "" },
  FECHADO: { nome: "Fechado · SA e precificador em Itu", classe: "atencao" },
  AGUARDANDO_NF: { nome: "SA e precificador prontos · falta NF", classe: "info" },
  ENVIADO: { nome: "Enviado · em trânsito", classe: "info" },
  RECEBIDO_PARCIAL: { nome: "Recebido parcial", classe: "atencao" },
  RECEBIDO: { nome: "Recebido", classe: "ok" },
};

export const EMITENTES = [
  { valor: "FIO_CERTO", nome: "Fio Certo" },
  { valor: "MEDIO_VALE", nome: "Médio Vale" },
  { valor: "OUTRO", nome: "Outro" },
] as const;
export const nomeEmitente = (v: string) => EMITENTES.find((e) => e.valor === v)?.nome ?? v;
/** Opções ao lançar NF de transferência: só Fio Certo (Eduardo, 2026-11-17). O histórico mostra o emitente como veio. */
export const EMITENTES_LANCAMENTO = EMITENTES.filter((e) => e.valor === "FIO_CERTO");
/** "556 (FIO_CERTO)" → "556 · Fio Certo" */
export const nfTexto = (s: string) => s.replace(/\((\w+)\)/, (_, e: string) => `· ${nomeEmitente(e)}`);

/** Spec v3.16 T11: R$/kg do precificador preenchido (zero conta como vazio). */
export const temPrecificador = (i: CopItem) => (i.sa?.rs_kg ?? 0) > 0;
/** Spec v3.16 T11: a NF só libera com SA confirmado e R$/kg em todos os itens alvo. */
export function faltasNf(itens: CopItem[]) {
  return { sa: itens.filter((i) => i.sa?.situacao !== "CONFIRMADO").length, rs: itens.filter((i) => !temPrecificador(i)).length };
}
export const reais = (v: number) => v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const SA_ITEM: Record<string, { nome: string; classe: string }> = {
  PENDENTE: { nome: "SA pendente", classe: "" },
  PREPARADO: { nome: "SA preparado", classe: "info" },
  AGUARDANDO_MEGA: { nome: "SA aguardando Mega", classe: "atencao" },
  CONFIRMADO: { nome: "SA confirmado", classe: "ok" },
};
