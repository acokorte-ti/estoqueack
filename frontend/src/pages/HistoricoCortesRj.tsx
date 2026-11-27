import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, data, kg, qs } from "../api/cliente";
import { MODO_NOME, type Modo } from "../api/solicitacao";
import Janela, { fecharJanela } from "../components/Janela";
import Icone from "../components/Icone";

/** T28 Histórico de cortes do RJ (spec v3.26, contrato §16.8): só Admin, só leitura. */
type Situacao = "CORTE_PRONTO" | "EM_COP" | "EM_TRANSITO" | "RECEBIDO" | "ESTORNADO";
interface Corte {
  id: number; data_corte: string; registrado_em: string; registrado_por: string | null;
  origem: "SISTEMA" | "PLANILHA"; origem_nome: string; origem_ref: { arquivo?: string; aba?: string; linha?: number } | null;
  solicitacao_id: number; solicitacao: string; op: number; cliente: string | null; item_descricao: string | null; modo: Modo;
  lote_id: number; lote: string; liga: string; bitola: string; conteiner: string | null; lote_trocado: boolean;
  pecas: number; peso_real_kg: number; previsto_kg: number | null; diferenca_pct: number | null;
  comprimento_barra_mm: number | null; observacao: string | null;
  cop: number | null; cop_id: number | null; situacao: Situacao; situacao_nome: string; estornado: boolean; corrigido: boolean;
}
interface Resposta {
  itens: Corte[]; total: number; pagina: number; por_pagina: number;
  totais: { cortes: number; pecas: number; peso_real_kg: number; estornados: number; sistema: number; planilha: number };
  periodo: { de: string; ate: string } | null;
}
interface Detalhe extends Corte {
  confirmacoes: Record<string, string>;
  movimentos: { id: number; tipo: string; tipo_descricao: string; kg: number; lote: string | null; lote_id: number; data: string;
    registrado_em: string; usuario: string | null; justificativa: string | null; da_carga: boolean }[];
  correcoes: { quando: string; usuario: string | null; antes: Record<string, unknown>; depois: Record<string, unknown>; motivo: string | null }[];
}

const SITUACOES: { valor: Situacao | ""; nome: string }[] = [
  { valor: "", nome: "Todas" }, { valor: "CORTE_PRONTO", nome: "Corte pronto (fora de COP)" }, { valor: "EM_COP", nome: "No COP" },
  { valor: "EM_TRANSITO", nome: "Enviado a Itu" }, { valor: "RECEBIDO", nome: "Recebido em Itu" }, { valor: "ESTORNADO", nome: "Estornado" },
];
const CLASSE: Record<Situacao, string> = { CORTE_PRONTO: "atencao", EM_COP: "info", EM_TRANSITO: "info", RECEBIDO: "ok", ESTORNADO: "ruim" };
const POR_PAGINA = 100;

const dataHora = (iso: string) => new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
const pct = (v: number) => `${v > 0 ? "+" : ""}${v.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
const origemTexto = (c: Corte) =>
  c.origem === "PLANILHA" ? `Planilha${c.origem_ref?.aba ? ` · ${c.origem_ref.aba}` : ""}${c.origem_ref?.linha ? ` linha ${c.origem_ref.linha}` : ""}` : "Sistema";

export default function HistoricoCortesRj() {
  const [de, setDe] = useState("");
  const [ate, setAte] = useState("");
  const [busca, setBusca] = useState("");
  const [origem, setOrigem] = useState("");
  const [situacao, setSituacao] = useState<Situacao | "">("");
  const [estornados, setEstornados] = useState(true);
  const [pag, setPag] = useState(1);
  const [r, setR] = useState<Resposta | null>(null);
  const [erro, setErro] = useState("");
  const [aberto, setAberto] = useState<number | null>(null);

  const filtros = { de: de || undefined, ate: ate || undefined, busca: busca.trim() || undefined, origem: origem || undefined,
    situacao: situacao || undefined, estornados };
  const chave = JSON.stringify(filtros);
  useEffect(() => { setPag(1); }, [chave]);
  useEffect(() => {
    let vivo = true;
    const t = window.setTimeout(async () => {
      setErro("");
      try {
        const x = await api.get<Resposta>(`/admin/cortes-rj${qs({ ...JSON.parse(chave), pagina: pag, por_pagina: POR_PAGINA })}`);
        if (vivo) setR(x);
      } catch (e) {
        if (vivo) setErro(e instanceof Error ? e.message : "Não foi possível carregar o histórico.");
      }
    }, 300);
    return () => { vivo = false; window.clearTimeout(t); };
  }, [chave, pag]);

  const paginas = r ? Math.max(1, Math.ceil(r.total / POR_PAGINA)) : 1;
  const t = r?.totais;

  return (
    <>
      <header className="cabecalho">
        <h1>Histórico de cortes do RJ</h1>
        <p>Todos os cortes registrados no RJ: os lançados no sistema e os que vieram do Controle de Corte (planilha). Clique em "Histórico" para ver os movimentos e as correções de cada corte.</p>
      </header>
      <div className="aviso-topo" role="note">
        Enquanto a carga das planilhas continuar, a recarga refaz este histórico a partir do Controle de Corte: os cortes lançados no sistema desde a última carga somem.
      </div>

      <div className="barra-filtros">
        <label>De<input type="date" value={de} onChange={(e) => setDe(e.target.value)} /></label>
        <label>Até<input type="date" value={ate} onChange={(e) => setAte(e.target.value)} /></label>
        <label style={{ flexBasis: "18rem" }}>Buscar<input type="search" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="OP, cliente, material, contêiner, lote, COP ou quem lançou" /></label>
        <label>Origem
          <select value={origem} onChange={(e) => setOrigem(e.target.value)}>
            <option value="">Sistema e planilha</option><option value="SISTEMA">Só sistema</option><option value="PLANILHA">Só planilha</option>
          </select>
        </label>
        <label>Situação
          <select value={situacao} onChange={(e) => setSituacao(e.target.value as Situacao | "")}>
            {SITUACOES.map((s) => <option key={s.valor} value={s.valor}>{s.nome}</option>)}
          </select>
        </label>
        <label className="marcar"><input type="checkbox" checked={estornados} onChange={(e) => setEstornados(e.target.checked)} /><span>Mostrar estornados</span></label>
      </div>

      <div className="barra-acoes">
        <span className="contagem">
          {t ? `${t.cortes.toLocaleString("pt-BR")} corte(s) · ${t.pecas.toLocaleString("pt-BR")} peça(s) · ${kg(t.peso_real_kg)} kg` : ""}
          {t && <span className="desc"> · sistema {t.sistema}, planilha {t.planilha}{t.estornados ? ` · ${t.estornados} estornado(s), fora da soma` : ""}{r?.periodo ? ` · de ${data(r.periodo.de)} a ${data(r.periodo.ate)}` : ""}</span>}
        </span>
        <a className="secundario" href={`/api/admin/cortes-rj.xlsx${qs(filtros)}`} download><Icone nome="baixar" /> Exportar para Excel</a>
      </div>
      {erro && <p className="erro" role="alert">{erro}</p>}

      {r && (r.itens.length ? (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                <th>Data do corte</th><th>OP / cliente</th><th>Material · contêiner · lote</th><th className="num">Peças</th>
                <th className="num">Peso real (kg)</th><th>COP / situação</th><th>Lançado por</th><th><span className="sr-only">Ação</span></th>
              </tr>
            </thead>
            <tbody>
              {r.itens.map((c) => (
                <tr key={c.id} className={c.estornado ? "inativo" : ""}>
                  <td className="sem-quebra">{data(c.data_corte)}</td>
                  <td><Link to={`/solicitacoes/${c.solicitacao_id}`}><strong>{c.op}</strong></Link><br /><span className="desc">{c.cliente ?? "—"}</span></td>
                  <td>
                    <strong>{c.liga} {c.bitola}</strong>
                    <br /><span className="desc">{c.conteiner ?? "sem contêiner"} · <Link to={`/estoque/${c.lote_id}`}>{c.lote}</Link>{c.modo === "TRAZER_INTEIRA" ? " · peça inteira" : ""}</span>
                    {c.lote_trocado && <><br /><span className="etiqueta atencao">outro lote que o pedido</span></>}
                  </td>
                  <td className="num">{c.pecas}</td>
                  <td className="num">
                    {kg(c.peso_real_kg)}
                    {c.previsto_kg !== null && <><br /><span className="desc">previsto {kg(c.previsto_kg)}{c.diferenca_pct !== null ? ` (${pct(c.diferenca_pct)})` : ""}</span></>}
                  </td>
                  <td>
                    {c.cop !== null ? <><Link to={`/cops/${c.cop_id}`}>COP {c.cop}</Link><br /></> : null}
                    <span className={`etiqueta ${CLASSE[c.situacao] ?? ""}`}>{c.situacao_nome}</span>
                    {c.corrigido && <><br /><span className="etiqueta">corrigido no COP</span></>}
                  </td>
                  <td>{c.registrado_por ?? "—"}<br /><span className="desc">{origemTexto(c)}</span></td>
                  <td><button type="button" className="secundario pequeno" onClick={() => setAberto(c.id)}><Icone nome="relogio" />Histórico</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className="estado-vazio"><strong>Nenhum corte com esses filtros</strong>Tire algum filtro ou aumente o período.</div>)}

      {r && paginas > 1 && (
        <div className="paginacao">
          <button className="secundario" disabled={pag <= 1} onClick={() => setPag(pag - 1)}>Anterior</button>
          <span>Página {pag} de {paginas}</span>
          <button className="secundario" disabled={pag >= paginas} onClick={() => setPag(pag + 1)}>Próxima</button>
        </div>
      )}

      {aberto !== null && <JanelaHistorico id={aberto} aoFechar={() => setAberto(null)} />}
    </>
  );
}

const ROTULO_CAMPO: Record<string, string> = { op: "OP", cliente: "cliente", pecas: "peças", peso_kg: "peso" };
function valorCampo(k: string, v: unknown) {
  if (v === null || v === undefined) return "—";
  return k === "peso_kg" && typeof v === "number" ? `${kg(v)} kg` : String(v);
}

function JanelaHistorico({ id, aoFechar }: { id: number; aoFechar: () => void }) {
  const [d, setD] = useState<Detalhe | null>(null);
  const [erro, setErro] = useState("");
  useEffect(() => { api.get<Detalhe>(`/admin/cortes-rj/${id}`).then(setD).catch((e: Error) => setErro(e.message)); }, [id]);
  const just = d ? Object.entries(d.confirmacoes) : [];
  return (
    <Janela titulo={d ? `Corte da OP ${d.op} · ${data(d.data_corte)}` : "Histórico do corte"} aoFechar={aoFechar} larga>
      {!d ? (erro ? <p className="erro" role="alert">{erro}</p> : <p className="carregando">Carregando…</p>) : (
        <>
          <dl className="dados">
            <div><dt>Pedido</dt><dd><Link to={`/solicitacoes/${d.solicitacao_id}`}>{d.solicitacao}</Link> · {MODO_NOME[d.modo]}</dd></div>
            <div><dt>Material</dt><dd>{d.liga} {d.bitola}</dd></div>
            <div><dt>Contêiner · lote</dt><dd>{d.conteiner ?? "—"} · {d.lote}</dd></div>
            <div><dt>Peças · peso real</dt><dd>{d.pecas} pç · {kg(d.peso_real_kg)} kg</dd></div>
            <div><dt>Situação</dt><dd>{d.situacao_nome}{d.cop !== null ? ` · COP ${d.cop}` : ""}</dd></div>
            <div><dt>Lançado</dt><dd>{d.registrado_por ?? origemTexto(d)} · {dataHora(d.registrado_em)}</dd></div>
            {d.comprimento_barra_mm !== null && <div><dt>Barra</dt><dd>{d.comprimento_barra_mm} mm</dd></div>}
            <div className="largo"><dt>Item / cliente</dt><dd>{d.item_descricao ?? "—"} · {d.cliente ?? "—"}</dd></div>
            {d.observacao && <div className="largo"><dt>Observação</dt><dd>{d.observacao}</dd></div>}
          </dl>
          {just.length > 0 && (
            <>
              <h3>Justificativas no lançamento</h3>
              <ul>{just.map(([k, v]) => <li key={k}><strong>{k}</strong>: {v}</li>)}</ul>
            </>
          )}
          <h3>Movimentos do corte</h3>
          {d.movimentos.length ? (
            <div className="tabela-rolagem">
              <table className="tabela">
                <thead><tr><th>Data</th><th>Movimento</th><th className="num">kg</th><th>Lote</th><th>Quem</th><th>Justificativa</th></tr></thead>
                <tbody>
                  {d.movimentos.map((m) => (
                    <tr key={m.id}>
                      <td className="sem-quebra">{data(m.data)}</td>
                      <td>{m.tipo_descricao}{m.da_carga && <><br /><span className="desc">da carga</span></>}</td>
                      <td className="num">{kg(m.kg)}</td>
                      <td>{m.lote ?? "—"}</td>
                      <td>{m.usuario ?? "—"}<br /><span className="desc">{dataHora(m.registrado_em)}</span></td>
                      <td><span className="desc">{m.justificativa ?? ""}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p className="desc">Nenhum movimento ligado a este corte.</p>}
          {d.correcoes.length > 0 && (
            <>
              <h3>Correções no COP</h3>
              <ul>
                {d.correcoes.map((c, i) => (
                  <li key={i}>
                    {dataHora(c.quando)} · {c.usuario ?? "—"}:{" "}
                    {Object.keys(ROTULO_CAMPO).filter((k) => c.antes[k] !== c.depois[k])
                      .map((k) => `${ROTULO_CAMPO[k]} ${valorCampo(k, c.antes[k])} → ${valorCampo(k, c.depois[k])}`).join("; ") || "sem mudança"}
                    {c.motivo ? ` (${c.motivo})` : ""}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
      <div className="botoes">
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Fechar</button>
      </div>
    </Janela>
  );
}
