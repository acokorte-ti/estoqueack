import { useSyncExternalStore } from "react";
import { api } from "./cliente";

/** GET /api/painel/pendencias (contrato F1 §11). Uma leitura serve o Painel e os contadores do menu. */
export type ItemPendencia = Record<string, unknown>;
export interface Pendencia {
  codigo: string; titulo: string; quantidade: number; nivel: "ALERTA" | "NORMAL"; link: string | null; itens: ItemPendencia[];
  limite_dias?: number | null; vencidas?: number | null; // os dois últimos: só na pendência do peso real (R058)
}
export interface RespostaPendencias {
  perfil: string;
  grupos: Record<string, Pendencia[]>;
  atrasos: { NORMAL: number; ATENCAO: number; ATRASADO: number };
  divergencias_mega: { quantidade: number | null; limite_kg: number };
  entradas_mega_a_classificar?: { quantidade: number | null } | null; // null para Operação RJ (P10)
}

interface Estado { dados: RespostaPendencias | null; erro: string; lidoEm: number }
const VAZIO: Estado = { dados: null, erro: "", lidoEm: 0 };
let estado: Estado = VAZIO;
let emCurso: Promise<void> | null = null;
const ouvintes = new Set<() => void>();
const avisar = () => ouvintes.forEach((f) => f());

/** Lê de novo (uma leitura por vez; quem chamar durante a leitura recebe a mesma). */
export function recarregarPendencias(): Promise<void> {
  if (emCurso) return emCurso;
  emCurso = api
    .get<RespostaPendencias>("/painel/pendencias")
    .then((dados) => { estado = { dados, erro: "", lidoEm: Date.now() }; })
    .catch((e: Error) => { estado = { ...estado, erro: e.message, lidoEm: Date.now() }; })
    .finally(() => { emCurso = null; avisar(); });
  return emCurso;
}

/** Ao sair: o próximo usuário não vê as pendências do anterior. */
export function limparPendencias() {
  estado = VAZIO;
  avisar();
}

/** Lê se o que está guardado for mais velho que `idadeMaxMs`. */
export function lerSeVelho(idadeMaxMs: number) {
  if (Date.now() - estado.lidoEm > idadeMaxMs) void recarregarPendencias();
}

export function usePendencias(): Estado {
  return useSyncExternalStore(
    (f) => { ouvintes.add(f); return () => { ouvintes.delete(f); }; },
    () => estado,
  );
}

export interface Contador { qtd: number; urgente: boolean }

/** Contador de cada item do menu: soma das pendências cujo `link` abre aquela tela; vermelho se alguma for ALERTA. */
export function contadoresDoMenu(r: RespostaPendencias | null): Record<string, Contador> {
  const c: Record<string, Contador> = {};
  if (!r) return c;
  const somar = (para: string, qtd: number, urgente: boolean) => {
    const atual = c[para] ?? { qtd: 0, urgente: false };
    c[para] = { qtd: atual.qtd + qtd, urgente: atual.urgente || urgente };
  };
  for (const lista of Object.values(r.grupos)) {
    for (const p of lista) {
      if (p.quantidade <= 0) continue;
      const urgente = p.nivel === "ALERTA";
      somar("/", p.quantidade, urgente);
      if (p.link) somar(p.link.split("?")[0], p.quantidade, urgente);
    }
  }
  // números de fora dos cartões, só se nenhum cartão já contou aquela tela
  const entradas = r.entradas_mega_a_classificar?.quantidade ?? 0;
  if (entradas > 0 && !c["/entradas-mega"]) somar("/entradas-mega", entradas, false);
  const divergencias = r.divergencias_mega.quantidade ?? 0;
  if (divergencias > 0 && !c["/conciliacao"]) somar("/conciliacao", divergencias, false);
  return c;
}
