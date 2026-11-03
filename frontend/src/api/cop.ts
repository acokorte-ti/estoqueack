/** Tipos e rótulos do COP e do recebimento (contrato F1 §4 e §5). */
import type { Modo } from "./solicitacao";

export type SituacaoCop = "ABERTO" | "FECHADO" | "AGUARDANDO_NF" | "ENVIADO" | "RECEBIDO_PARCIAL" | "RECEBIDO";

export interface CopItem {
  id: number; liberacao_id: number; solicitacao_id: number; op: number; item_codigo: number | null; cliente: string | null;
  material: string; conteiner: string | null; lote: string; modo: Modo; pecas: number; peso_kg: number;
  situacao: "EM_COP" | "EM_TRANSITO" | "RECEBIDO";
  sa: { id: number; situacao: string; sa_codigo: number | null } | null;
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
  FECHADO: { nome: "Fechado · SAs em Itu", classe: "atencao" },
  AGUARDANDO_NF: { nome: "SAs prontos · falta NF", classe: "info" },
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
/** "556 (FIO_CERTO)" → "556 · Fio Certo" */
export const nfTexto = (s: string) => s.replace(/\((\w+)\)/, (_, e: string) => `· ${nomeEmitente(e)}`);

export const SA_ITEM: Record<string, { nome: string; classe: string }> = {
  PENDENTE: { nome: "SA pendente", classe: "" },
  PREPARADO: { nome: "SA preparado", classe: "info" },
  AGUARDANDO_MEGA: { nome: "SA aguardando Mega", classe: "atencao" },
  CONFIRMADO: { nome: "SA confirmado", classe: "ok" },
};
