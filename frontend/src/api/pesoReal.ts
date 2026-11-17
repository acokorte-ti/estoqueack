import { useCallback, useEffect, useState } from "react";
import { api, qs } from "./cliente";

/**
 * Pendência "Informar o peso real" da peça inteira do RJ (spec v3.11 §2.2 passo 7, T03, T07, T13; R058/R059).
 * Vem no grupo ESTOQUE de `GET /api/painel/pendencias`. Tudo opcional: enquanto a API do R058 não estiver no ar,
 * a tela aceita o código novo (`PESO_REAL_PENDENTE`) ou o antigo (`PECA_INTEIRA_AGUARDANDO_CORTE`, sem data de
 * recebimento: aparece, mas não conta para o bloqueio).
 */
export interface PecaPesoReal {
  pendencia_id?: number | null;
  /** solicitação (o item antigo usa `id`) */
  solicitacao_id?: number | null;
  id?: number | null;
  op?: number | null;
  lote_id?: number | null;
  lote?: string | null;
  material?: string | null;
  conteiner?: string | null;
  cop?: number | string | null;
  recebido_em?: string | null;
  dias?: number | null;
  vencida?: boolean | null;
}

export interface PendenciaPesoReal {
  codigo: string;
  titulo?: string;
  quantidade: number;
  nivel?: string;
  link?: string | null;
  itens: PecaPesoReal[];
  limite_dias?: number | null;
  vencidas?: number | null;
}

export const CODIGOS_PESO_REAL = ["PESO_REAL_PENDENTE", "PECA_INTEIRA_AGUARDANDO_PESO_REAL", "PECA_INTEIRA_AGUARDANDO_CORTE"];
/** `PENDENCIA_PESO_REAL_DIAS` da T23; vale só se a API não mandar `limite_dias`. */
export const LIMITE_PADRAO_DIAS = 7;

const DIA = 86_400_000;
const meiaNoite = (iso: string) => new Date(iso.length === 10 ? `${iso}T00:00:00` : iso).setHours(0, 0, 0, 0);

/** Dias desde o recebimento do COP (da API, ou contados pela data de recebimento). */
export function diasDe(p: PecaPesoReal): number | null {
  if (typeof p.dias === "number") return p.dias;
  if (!p.recebido_em) return null;
  return Math.max(0, Math.round((new Date().setHours(0, 0, 0, 0) - meiaNoite(p.recebido_em)) / DIA));
}

/** Data em que passa a bloquear (mais de N dias desde o recebimento), "DD/MM". */
export function bloqueiaEm(p: PecaPesoReal, limite: number): string | null {
  if (!p.recebido_em) return null;
  const d = new Date(meiaNoite(p.recebido_em) + (limite + 1) * DIA);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

export const vencida = (p: PecaPesoReal, limite: number) => p.vencida ?? ((diasDe(p) ?? -1) > limite);

/** Link da T13 com a peça sugerida (OP + lote RJ em Itu). */
export const linkPeca = (p: PecaPesoReal | null | undefined) =>
  `/corte-itu${p ? qs({ op: p.op ?? undefined, lote_id: p.lote_id ?? undefined, peso_real: 1 }) : ""}`;

export interface ResumoPesoReal {
  pendencia: PendenciaPesoReal | null;
  limite: number;
  /** peças com data de recebimento (as que contam para o bloqueio), da mais antiga para a mais nova */
  pecas: PecaPesoReal[];
  vencidas: number;
  maisAntiga: PecaPesoReal | null;
}

export function resumirPesoReal(grupos: Record<string, PendenciaPesoReal[]> | undefined): ResumoPesoReal {
  const todas = Object.values(grupos ?? {}).flat();
  const pend = CODIGOS_PESO_REAL.map((c) => todas.find((p) => p.codigo === c)).find((p) => p) ?? null;
  const limite = pend?.limite_dias ?? LIMITE_PADRAO_DIAS;
  const pecas = (pend?.itens ?? []).filter((i) => diasDe(i) !== null).sort((a, b) => (diasDe(b) ?? 0) - (diasDe(a) ?? 0));
  const vencidas = pend?.vencidas ?? pecas.filter((p) => vencida(p, limite)).length;
  return { pendencia: pend, limite, pecas, vencidas, maisAntiga: pecas[0] ?? null };
}

/** Lê o painel e devolve só a pendência do peso real (T07 e T13). Falha da API = sem pendência (não quebra a tela). */
export function usePesoReal() {
  const [r, setR] = useState<ResumoPesoReal | null>(null);
  const carregar = useCallback(
    () => api.get<{ grupos: Record<string, PendenciaPesoReal[]> }>("/painel/pendencias")
      .then((x) => setR(resumirPesoReal(x.grupos)))
      .catch(() => setR(resumirPesoReal(undefined))),
    [],
  );
  useEffect(() => { void carregar(); }, [carregar]);
  return { resumo: r, recarregar: carregar };
}

/** Texto curto da peça: "OP 90010, H13 70×610, recebida em 03/11". */
export function textoPeca(p: PecaPesoReal): string {
  const rec = p.recebido_em ? new Date(meiaNoite(p.recebido_em)).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }) : null;
  return [p.op ? `OP ${p.op}` : null, p.material, rec ? `recebida em ${rec}` : null].filter(Boolean).join(", ");
}

/** "Encerrar pendência" (peça que não vai mais ser cortada), com justificativa (auditoria). */
export const encerrarPendenciaPesoReal = (id: number, justificativa: string) =>
  api.post(`/pendencias-peso-real/${id}/encerrar`, { justificativa });
