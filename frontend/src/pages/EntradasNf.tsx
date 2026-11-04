import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, data, kg, num, validacaoDoErro, type Validacao } from "../api/cliente";
import { useSessao } from "../api/sessao";
import PainelValidacao, { confirmacoesValidas, podeGravar, type Confirmacoes } from "../components/PainelValidacao";

interface EntradaItem { lote_id?: number; liga: string; formato: string; espessura: number | null; largura: number | null; diametro: number | null;
  descricao_nf: string | null; pecas: number | null; peso_kg: number; comprimento: string | null; custo_kg: number | null }
interface Entrada { id: number; numero: string; fornecedor: string; data: string; conteiner: string; itens?: EntradaItem[] }
interface Liga { codigo: string; ativo: boolean }
interface Linha { liga: string; formato: "RETANGULAR" | "REDONDO"; espessura: string; largura: string; diametro: string; descricao: string; pecas: string; peso: string; comprimento: string; custo: string }

const linhaVazia = (): Linha => ({ liga: "", formato: "RETANGULAR", espessura: "", largura: "", diametro: "", descricao: "", pecas: "", peso: "", comprimento: "", custo: "" });
const hojeIso = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

/** T06 Entrada por NF (Barra Mansa): cada linha vira um lote RJ no Rio. Depois de salvar, só se corrige por estorno. */
export default function EntradasNf() {
  const { usuario } = useSessao();
  const lanca = usuario?.perfil === "OPERACAO_RJ" || usuario?.perfil === "ADMIN";
  const [lista, setLista] = useState<Entrada[] | null>(null);
  const [nova, setNova] = useState(false);
  const [gravada, setGravada] = useState<Entrada | null>(null);
  const [erro, setErro] = useState("");

  const carregar = () => api.get<Entrada[]>("/entradas-nf").then(setLista).catch((e: Error) => setErro(e.message));
  useEffect(() => { void carregar(); }, []);

  if (nova) return <NovaEntrada aoSair={(g) => { setNova(false); if (g) { setGravada(g); void carregar(); } }} />;

  return (
    <>
      <header className="cabecalho cabecalho-acao">
        <div>
          <h1>Entrada por NF</h1>
          <p>Material que chega ao RJ. Cada item da NF vira um lote no RJ no Rio, com o peso informado.</p>
        </div>
        {lanca && <button className="primario" onClick={() => { setGravada(null); setNova(true); }}>Nova entrada</button>}
      </header>
      {erro && <p className="erro" role="alert">{erro}</p>}
      {gravada && (
        <div className="validacao ok" role="status">
          <span>NF {gravada.numero} lançada: {gravada.itens?.length ?? 0} lote(s) criado(s) no contêiner {gravada.conteiner}.</span>
          {gravada.itens?.map((i) => i.lote_id && <span key={i.lote_id}><Link to={`/estoque/${i.lote_id}`}>Ver lote {i.liga} {i.espessura ? `${i.espessura}×${i.largura}` : `Ø${i.diametro}`}</Link></span>)}
        </div>
      )}
      {lista && !lista.length ? <div className="estado-vazio"><strong>Nenhuma entrada lançada no sistema ainda</strong>As entradas antigas vieram pela carga da ESTOQUE 2026.</div> : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead><tr><th>NF</th><th>Data</th><th>Fornecedor</th><th>Contêiner</th><th className="num">Itens</th><th className="num">Peso</th></tr></thead>
            <tbody>
              {lista?.map((e) => (
                <tr key={e.id}>
                  <td><strong>{e.numero}</strong></td><td>{data(e.data)}</td><td>{e.fornecedor}</td><td>{e.conteiner}</td>
                  <td className="num">{e.itens?.length ?? "—"}</td>
                  <td className="num">{e.itens ? `${kg(e.itens.reduce((a, i) => a + i.peso_kg, 0))} kg` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function NovaEntrada({ aoSair }: { aoSair: (gravada: Entrada | null) => void }) {
  const [cab, setCab] = useState({ numero: "", data: hojeIso(), fornecedor: "", conteiner: "" });
  const [linhas, setLinhas] = useState<Linha[]>([linhaVazia()]);
  const [ligas, setLigas] = useState<string[]>([]);
  const [conts, setConts] = useState<{ id: number; codigo: string }[]>([]);
  const [v, setV] = useState<Validacao<{ frase?: string }> | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    api.get<Liga[]>("/ligas").then((l) => setLigas(l.filter((x) => x.ativo).map((x) => x.codigo))).catch(() => undefined);
  }, []);
  useEffect(() => {
    const t = window.setTimeout(() => {
      if (cab.conteiner.trim().length < 2) return;
      api.get<{ id: number; codigo: string }[]>(`/conteineres?busca=${encodeURIComponent(cab.conteiner.trim())}`).then(setConts).catch(() => undefined);
    }, 250);
    return () => window.clearTimeout(t);
  }, [cab.conteiner]);

  const mudarCab = (p: Partial<typeof cab>) => { setCab({ ...cab, ...p }); setV(null); };
  const mudar = (i: number, p: Partial<Linha>) => { setLinhas(linhas.map((l, k) => (k === i ? { ...l, ...p } : l))); setV(null); };
  const corpo = (c: Confirmacoes) => ({
    numero: cab.numero.trim(), data: cab.data, fornecedor: cab.fornecedor.trim(), conteiner: cab.conteiner.trim().toUpperCase(),
    itens: linhas.map((l) => ({ liga: l.liga, formato: l.formato, espessura: num(l.espessura) ?? null, largura: num(l.largura) ?? null,
      diametro: num(l.diametro) ?? null, descricao_nf: l.descricao.trim() || null, pecas: num(l.pecas) ?? null, peso_kg: num(l.peso) ?? 0,
      comprimento: l.comprimento.trim() || null, custo_kg: num(l.custo) ?? null })),
    confirmacoes: c,
  });
  const completo = cab.numero.trim() && cab.fornecedor.trim().length >= 2 && cab.conteiner.trim().length >= 2 &&
    linhas.every((l) => l.liga && (num(l.peso) ?? 0) > 0 && (l.formato === "REDONDO" ? num(l.diametro) : num(l.espessura) && num(l.largura)));
  const total = linhas.reduce((a, l) => a + (num(l.peso) ?? 0), 0);

  async function conferir() {
    setErro("");
    setOcupado(true);
    try { setV(await api.post<Validacao<{ frase?: string }>>("/entradas-nf/validar", corpo({}))); }
    catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível conferir."); }
    finally { setOcupado(false); }
  }
  async function salvar() {
    if (!v) return;
    setErro("");
    setOcupado(true);
    try { aoSair(await api.post<Entrada>("/entradas-nf", corpo(confirmacoesValidas(v.ocorrencias, conf)))); }
    catch (e) {
      const x = validacaoDoErro<{ frase?: string }>(e);
      if (x) setV(x); else setErro(e instanceof Error ? e.message : "Não foi possível salvar.");
    } finally { setOcupado(false); }
  }

  return (
    <>
      <p><button className="link" onClick={() => aoSair(null)}>← Entradas por NF</button></p>
      <header className="cabecalho"><h1>Nova entrada por NF</h1></header>

      <section className="painel-form">
        <div className="grade-form">
          <label>Nº da NF<input autoFocus value={cab.numero} onChange={(e) => mudarCab({ numero: e.target.value })} /></label>
          <label>Data<input type="date" value={cab.data} max={hojeIso()} onChange={(e) => mudarCab({ data: e.target.value })} /></label>
          <label>Fornecedor<input value={cab.fornecedor} onChange={(e) => mudarCab({ fornecedor: e.target.value })} placeholder="EASON" /></label>
          <label>Contêiner<input list="conteineres-nf" value={cab.conteiner} onChange={(e) => mudarCab({ conteiner: e.target.value.toUpperCase() })} placeholder="CH50XY" />
            <datalist id="conteineres-nf">{conts.map((c) => <option key={c.id} value={c.codigo} />)}</datalist>
            <small className="dica">Se não existir, o contêiner é criado.</small></label>
        </div>
      </section>

      {linhas.map((l, i) => (
        <section key={i} className="painel-form" style={{ marginTop: "var(--esp-3)" }} aria-label={`Item ${i + 1}`}>
          <div className="linha-titulo">
            <h2>Item {i + 1}</h2>
            {linhas.length > 1 && <button className="link" onClick={() => { setLinhas(linhas.filter((_, k) => k !== i)); setV(null); }}>Remover</button>}
          </div>
          <div className="grade-form">
            <label>Liga
              <select value={l.liga} onChange={(e) => mudar(i, { liga: e.target.value })}>
                <option value="">Escolha</option>
                {ligas.map((x) => <option key={x} value={x}>{x}</option>)}
              </select>
            </label>
            <label>Descrição como na NF<input value={l.descricao} onChange={(e) => mudar(i, { descricao: e.target.value })} placeholder="H13 50x610x2800-6000" /></label>
          </div>
          <fieldset className="formatos">
            <legend>Formato</legend>
            {(["RETANGULAR", "REDONDO"] as const).map((fm) => (
              <label key={fm} className={l.formato === fm ? "opcao marcada" : "opcao"}>
                <input type="radio" name={`formato-${i}`} checked={l.formato === fm} onChange={() => mudar(i, { formato: fm })} />{fm === "RETANGULAR" ? "Chapa / barra retangular" : "Barra redonda"}
              </label>
            ))}
          </fieldset>
          <div className="grade-medidas">
            {l.formato === "RETANGULAR" ? (
              <>
                <label>Espessura (mm)<input inputMode="decimal" value={l.espessura} onChange={(e) => mudar(i, { espessura: e.target.value })} /></label>
                <label>Largura (mm)<input inputMode="decimal" value={l.largura} onChange={(e) => mudar(i, { largura: e.target.value })} /></label>
              </>
            ) : <label>Diâmetro (mm)<input inputMode="decimal" value={l.diametro} onChange={(e) => mudar(i, { diametro: e.target.value })} /></label>}
            <label>Barras / chapas<input inputMode="numeric" value={l.pecas} onChange={(e) => mudar(i, { pecas: e.target.value })} /></label>
            <label>Peso (kg)<input inputMode="decimal" className="campo-grande" value={l.peso} onChange={(e) => mudar(i, { peso: e.target.value })} /></label>
            <label>Comprimento (opcional)<input value={l.comprimento} onChange={(e) => mudar(i, { comprimento: e.target.value })} placeholder="2800-6000" /></label>
            <label>R$/kg (opcional)<input inputMode="decimal" value={l.custo} onChange={(e) => mudar(i, { custo: e.target.value })} /></label>
          </div>
        </section>
      ))}
      <div className="botoes" style={{ marginTop: "var(--esp-3)" }}>
        <button className="secundario" onClick={() => { setLinhas([...linhas, { ...linhaVazia(), liga: linhas[linhas.length - 1].liga }]); setV(null); }}>Adicionar item</button>
      </div>

      {v && (
        <div className="bloco-passo" style={{ marginTop: "var(--esp-4)" }}>
          {v.resultado?.frase && <p className="frase-resultado resultado-frase">{v.resultado.frase}</p>}
          <PainelValidacao ocorrencias={v.ocorrencias} confirmacoes={conf} aoMudar={setConf} semOcorrencias="Tudo certo para lançar." />
        </div>
      )}
      {erro && <p className="erro" role="alert">{erro}</p>}

      <div className="rodape-acao">
        <span className="resultado-frase">{linhas.length} item(ns) · {kg(total)} kg</span>
        <button className="secundario" onClick={() => aoSair(null)}>Cancelar</button>
        {!v ? <button className="primario" disabled={!completo || ocupado} onClick={() => void conferir()}>{ocupado ? "Conferindo…" : "Conferir entrada"}</button>
          : <button className="primario" disabled={ocupado || !podeGravar(v.ocorrencias, conf)} onClick={() => void salvar()}>{ocupado ? "Salvando…" : "Salvar entrada"}</button>}
      </div>
    </>
  );
}
