import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, ESTOQUE_NOME, kg, qs } from "../api/cliente";

interface LoteDet { id: number; codigo: string; saldo_kg: number }
interface Conteiner { conteiner: string | null; conteiner_texto: string; estoque: string; classe: "COMPLETA" | "SO_BITOLA" | "SEM_ORIGEM"; lotes: number;
  saldo_kg: number; reservado_kg: number; disponivel_kg: number; lotes_detalhe: LoteDet[] }
interface Totais { com_origem_kg: number; so_bitola_kg: number; sem_origem_kg: number; total_kg: number; lotes?: number; reservado_kg?: number; disponivel_kg?: number }
interface SemOrigem { texto: string; lotes: number; saldo_kg: number; reservado_kg: number; disponivel_kg: number; lotes_detalhe: LoteDet[] }
interface Liga { liga: string; bitolas: { bitola_origem: string; total_kg: number; conteineres: Conteiner[] }[]; sem_origem: SemOrigem | null; totais: Totais }
interface Resposta { ligas: Liga[]; totais: Totais; vazio?: boolean; mensagem_vazio?: string | null; estoque_travado?: string | null }

const CLASSE = { COMPLETA: { nome: "origem completa", c: "ok" }, SO_BITOLA: { nome: "só a bitola", c: "atencao" }, SEM_ORIGEM: { nome: "sem origem", c: "ruim" } } as const;
const ESTOQUES = [{ v: "", n: "Todos" }, { v: "ESTOQUE_MEGA", n: "Estoque Mega" }, { v: "RJ_EM_ITU", n: "RJ em Itu" }];
const linhaTotais = (t: Totais) => `Com origem ${kg(t.com_origem_kg)} kg · Só bitola ${kg(t.so_bitola_kg)} kg · Sem origem ${kg(t.sem_origem_kg)} kg · Total RETO ${kg(t.total_kg)} kg`;

function Lotes({ l }: { l: LoteDet[] }) {
  return <>{l.map((x, i) => <span key={x.id}>{i > 0 && ", "}<Link to={`/estoque/${x.id}`} title={`${kg(x.saldo_kg)} kg`}>{x.codigo}</Link></span>)}</>;
}

/** Aba "RETO por origem" da T04: kg de RETO por liga, bitola de origem e contêiner de origem. */
export default function RetoPorOrigem({ soRj, estoqueInicial, aoVoltar }: { soRj: boolean; estoqueInicial: string; aoVoltar: (v: "lote" | "item") => void }) {
  const [f, setF] = useState({ estoque: estoqueInicial === "RJ_NO_RIO" ? "" : estoqueInicial, liga: "", bitola: "", conteiner: "", codigo: "", saldo: true, sobras: false, de: "", ate: "" });
  const [r, setR] = useState<Resposta | null>(null);
  const [erro, setErro] = useState("");
  const q = useMemo(() => ({
    estoque: soRj ? "RJ_NO_RIO" : f.estoque || undefined,
    liga: f.liga.split(/[,\s]+/).filter(Boolean).map((x) => x.toUpperCase()),
    bitola_origem: f.bitola.trim(), conteiner: f.conteiner.trim(), codigo_mega: f.codigo.trim(),
    com_saldo: f.saldo, incluir_sobras: f.sobras || undefined, criado_de: f.de, criado_ate: f.ate,
  }), [f, soRj]);

  useEffect(() => {
    const t = window.setTimeout(() => {
      setErro("");
      api.get<Resposta>(`/lotes/reto-por-origem${qs(q)}`).then(setR).catch((e: Error) => setErro(e.message));
    }, 300);
    return () => window.clearTimeout(t);
  }, [q]);
  const m = (p: Partial<typeof f>) => setF({ ...f, ...p });

  return (
    <>
      <header className="cabecalho">
        <h1>Consulta de estoque</h1>
        <p>RETO por origem: quantos kg de RETO vieram de cada bitola e contêiner.</p>
      </header>
      <div className="barra-acoes">
        <span className="contagem">{r ? `${r.totais.lotes ?? 0} lote(s)` : ""}</span>
        <div className="chips" role="group" aria-label="Visão">
          <button type="button" className="chip" aria-pressed={false} onClick={() => aoVoltar("lote")}>Por lote</button>
          <button type="button" className="chip" aria-pressed={false} onClick={() => aoVoltar("item")}>Agrupado por liga × bitola</button>
          <button type="button" className="chip" aria-pressed={true}>RETO por origem</button>
        </div>
        <a className="secundario" href={`/api/exportar/reto-por-origem.xlsx${qs(q)}`} download>Exportar para Excel</a>
      </div>
      <div className="barra-filtros">
        {!soRj && (
          <label>Estoque
            <select value={f.estoque} onChange={(e) => m({ estoque: e.target.value })}>{ESTOQUES.map((e) => <option key={e.v} value={e.v}>{e.n}</option>)}</select>
          </label>
        )}
        <label>Liga<input value={f.liga} onChange={(e) => m({ liga: e.target.value.toUpperCase() })} placeholder="H13" /></label>
        <label>Bitola de origem<input value={f.bitola} onChange={(e) => m({ bitola: e.target.value })} placeholder="45x610" /></label>
        <label>Contêiner de origem<input value={f.conteiner} onChange={(e) => m({ conteiner: e.target.value.toUpperCase() })} /></label>
        {!soRj && <label>Código Mega<input inputMode="numeric" value={f.codigo} onChange={(e) => m({ codigo: e.target.value })} /></label>}
        <label>Criado de<input type="date" value={f.de} onChange={(e) => m({ de: e.target.value })} /></label>
        <label>até<input type="date" value={f.ate} onChange={(e) => m({ ate: e.target.value })} /></label>
        <label className="marcar"><input type="checkbox" checked={f.saldo} onChange={(e) => m({ saldo: e.target.checked })} /><span>Só com saldo</span></label>
        <label className="marcar"><input type="checkbox" checked={f.sobras} onChange={(e) => m({ sobras: e.target.checked })} /><span>Incluir sobras com bitola original</span></label>
      </div>

      {erro && <p className="erro" role="alert">{erro}</p>}
      {r && (r.vazio || !r.ligas.length) && <div className="estado-vazio"><strong>{r.mensagem_vazio ?? "Nenhum RETO com esses filtros"}</strong>{!r.mensagem_vazio && "Tire algum filtro."}</div>}

      {r?.ligas.map((l) => (
        <section key={l.liga} className="painel-form" style={{ marginBottom: "var(--esp-4)" }} aria-label={`Liga ${l.liga}`}>
          <h2>{l.liga}</h2>
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead><tr><th>Bitola de origem</th><th>Contêiner de origem</th><th>Estoque</th><th className="num">Lotes</th><th className="num">Saldo kg</th><th className="num">Reservado</th><th className="num">Disponível</th></tr></thead>
              <tbody>
                {l.bitolas.map((b) => <BitolaLinhas key={b.bitola_origem} b={b} />)}
                {l.sem_origem && (
                  <tr>
                    <td colSpan={2}><span className="etiqueta ruim">{l.sem_origem.texto}</span> <Lotes l={l.sem_origem.lotes_detalhe} /></td>
                    <td></td><td className="num">{l.sem_origem.lotes}</td><td className="num"><strong>{kg(l.sem_origem.saldo_kg)}</strong></td>
                    <td className="num">{kg(l.sem_origem.reservado_kg)}</td><td className="num">{kg(l.sem_origem.disponivel_kg)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="desc" style={{ marginTop: "var(--esp-2)" }}><strong>{l.liga}:</strong> {linhaTotais(l.totais)}</p>
        </section>
      ))}
      {r && r.ligas.length > 0 && <p className="validacao ok"><strong>Total geral:</strong> {linhaTotais(r.totais)}</p>}
    </>
  );
}

function BitolaLinhas({ b }: { b: Liga["bitolas"][number] }) {
  return (
    <>
      <tr><td colSpan={4}><strong>{b.bitola_origem}</strong></td><td className="num"><strong>{kg(b.total_kg)}</strong></td><td></td><td></td></tr>
      {b.conteineres.map((c, i) => (
        <tr key={i}>
          <td></td>
          <td>{c.conteiner_texto} <span className={`etiqueta ${CLASSE[c.classe].c}`}>{CLASSE[c.classe].nome}</span><br /><span className="desc"><Lotes l={c.lotes_detalhe} /></span></td>
          <td><span className={`estoque-tag ${c.estoque}`}>{ESTOQUE_NOME[c.estoque] ?? c.estoque}</span></td>
          <td className="num">{c.lotes}</td><td className="num">{kg(c.saldo_kg)}</td><td className="num">{kg(c.reservado_kg)}</td><td className="num">{kg(c.disponivel_kg)}</td>
        </tr>
      ))}
    </>
  );
}
