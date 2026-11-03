import { useCallback, useEffect, useState } from "react";
import { api, ErroApi } from "../api/cliente";
import { useSessao } from "../api/sessao";

interface Sync { id: number; tipo: "ESTOQUE" | "SA"; gatilho: "AGENDADA" | "MANUAL"; situacao: "OK" | "ERRO";
  iniciado_em: string; terminado_em: string | null; detalhes: unknown }
interface Historico { ultima_ok: Sync | null; itens: Sync[] }

const PODE_SINCRONIZAR = ["ESTOQUE", "ANALISE", "ADMIN"];
const quando = (iso: string) =>
  new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

/** "Mega atualizado em …" + botão "Sincronizar agora" (P04 / R028). Sincroniza sozinho às 6h e às 13h. */
export default function SyncMega() {
  const { usuario } = useSessao();
  const [h, setH] = useState<Historico | null>(null);
  const [rodando, setRodando] = useState(false);
  const [msg, setMsg] = useState<{ tipo: "ok" | "erro" | "alerta"; texto: string } | null>(null);

  const carregar = useCallback(() => api.get<Historico>("/mega/sincronizacoes?limite=5").then(setH).catch(() => setH(null)), []);
  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function sincronizar() {
    setMsg(null);
    setRodando(true);
    try {
      const r = await api.post<{ estoque: Sync; sa: Sync }>("/mega/sincronizar");
      const falhou = [r.estoque, r.sa].filter((s) => s?.situacao === "ERRO");
      setMsg(falhou.length
        ? { tipo: "erro", texto: `A sincronização terminou com erro (${falhou.map((s) => (s.tipo === "SA" ? "SA" : "estoque")).join(" e ")}). Tente de novo em alguns minutos.` }
        : { tipo: "ok", texto: "Saldos e SAs atualizados com o Mega." });
      await carregar();
    } catch (e) {
      if (e instanceof ErroApi && e.status === 409) setMsg({ tipo: "alerta", texto: "Já há uma sincronização em andamento. Aguarde terminar." });
      else setMsg({ tipo: "erro", texto: e instanceof Error ? e.message : "Não foi possível sincronizar." });
    } finally {
      setRodando(false);
    }
  }

  const ultima = h?.ultima_ok?.terminado_em;
  const ultimaFalhou = h?.itens?.[0]?.situacao === "ERRO";
  return (
    <div className="sync-mega" aria-live="polite">
      <span className={ultimaFalhou ? "sync-texto ruim" : "sync-texto"}>
        {ultima ? `Mega atualizado em ${quando(ultima)}` : "Mega ainda não sincronizado"}
        {ultimaFalhou && " · a última tentativa falhou"}
      </span>
      {usuario && PODE_SINCRONIZAR.includes(usuario.perfil) && (
        <button className="secundario" onClick={() => void sincronizar()} disabled={rodando}>
          {rodando ? "Sincronizando…" : "Sincronizar agora"}
        </button>
      )}
      {msg && <p className={`validacao ${msg.tipo === "ok" ? "ok" : msg.tipo === "erro" ? "erro" : "alerta"}`}>{msg.texto}</p>}
    </div>
  );
}
