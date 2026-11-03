import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/cliente";

interface Notificacao { id: number; tipo: string; texto: string; link: string | null; criado_em: string; lida: boolean }
interface Lista { itens: Notificacao[]; nao_lidas: number }

const quando = (iso: string) => {
  const d = new Date(iso);
  const hoje = new Date().toDateString() === d.toDateString();
  return hoje ? d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : d.toLocaleDateString("pt-BR");
};

/** Sino de avisos do sistema (§6). Atualiza a cada minuto; clicar no aviso marca como lido e abre a tela. */
export default function Sino() {
  const [l, setL] = useState<Lista | null>(null);
  const [aberto, setAberto] = useState(false);
  const caixa = useRef<HTMLDivElement>(null);
  const nav = useNavigate();

  const carregar = useCallback(() => api.get<Lista>("/notificacoes").then(setL).catch(() => undefined), []);
  useEffect(() => {
    void carregar();
    const t = window.setInterval(() => void carregar(), 60_000);
    return () => window.clearInterval(t);
  }, [carregar]);

  useEffect(() => {
    if (!aberto) return;
    const fora = (e: MouseEvent) => caixa.current && !caixa.current.contains(e.target as Node) && setAberto(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false);
    document.addEventListener("mousedown", fora);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", fora); document.removeEventListener("keydown", esc); };
  }, [aberto]);

  async function abrir(n: Notificacao) {
    if (!n.lida) await api.post(`/notificacoes/${n.id}/lida`).catch(() => undefined);
    setAberto(false);
    void carregar();
    if (n.link) nav(n.link);
  }

  async function todasLidas() {
    await api.post("/notificacoes/lidas").catch(() => undefined);
    void carregar();
  }

  const n = l?.nao_lidas ?? 0;
  return (
    <div className="sino" ref={caixa}>
      <button className="sino-botao" aria-expanded={aberto} aria-haspopup="true"
        aria-label={n ? `Avisos: ${n} não lido(s)` : "Avisos"} onClick={() => setAberto(!aberto)}>
        <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {n > 0 && <span className="sino-contador">{n > 99 ? "99+" : n}</span>}
      </button>
      {aberto && (
        <div className="sino-painel" role="dialog" aria-label="Avisos">
          <div className="sino-cabeca">
            <strong>Avisos</strong>
            {n > 0 && <button className="link" onClick={() => void todasLidas()}>Marcar todos como lidos</button>}
          </div>
          {!l?.itens.length ? (
            <p className="desc sino-vazio">Nenhum aviso.</p>
          ) : (
            <ul>
              {l.itens.slice(0, 30).map((x) => (
                <li key={x.id}>
                  <button className={x.lida ? "sino-item" : "sino-item nao-lida"} onClick={() => void abrir(x)}>
                    <span>{x.texto}</span>
                    <small>{quando(x.criado_em)}</small>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
