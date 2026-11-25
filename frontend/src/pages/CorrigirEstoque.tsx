import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, data, ESTOQUE_NOME, kg, num, qs, rsKg, validacaoDoErro, type Validacao } from "../api/cliente";
import { TIPO_LOTE, type Lote } from "../api/lote";
import Janela, { fecharJanela } from "../components/Janela";
import PainelValidacao, { confirmacoesValidas, podeGravar, type Confirmacoes } from "../components/PainelValidacao";
import Icone from "../components/Icone";

/** T27 Corrigir estoque (spec v3.22, contrato §16.7): só Admin, lotes que não são do Estoque Mega. */
interface LoteCorrigir extends Lote {
  item_id: number; espessura: number | null; largura: number | null; diametro: number | null;
  comprimento_fixado: string | null; planta_fiscal: string; local_fisico: "RJ" | "ITU";
  documento_entrada: string | null; origem_carga: { arquivo: string | null; aba: string | null; linha: number | null } | null;
  corrigido: boolean; corrigido_em: string | null;
}
interface Liga { id: number; codigo: string; ativo: boolean }
interface Efeito { campo: string; rotulo: string; antes: unknown; depois: unknown }
type Previa = Validacao<{ frase?: string; efeitos?: Efeito[] }>;

const ESTOQUES = [
  { valor: "", nome: "Todos (RJ no Rio e RJ em Itu)" },
  { valor: "RJ_NO_RIO", nome: "RJ no Rio" },
  { valor: "RJ_EM_ITU", nome: "RJ em Itu" },
];
const AVISO_BUSCA = "Liga e bitola são a chave da busca do Pedir corte: se trocar, este lote deixa de aparecer para pedidos do material antigo (ex.: trocar A8 por outra liga e uma OP de A8 não acha mais este lote).";
const AVISO_DESCRICAO = "A descrição aparece nas telas e na busca por texto; o comprimento e o \"múltiplo\" do material são lidos dela.";

const texto = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v).replace(".", ","));

function origemTexto(l: LoteCorrigir): string {
  if (l.origem_carga) return `Planilha${l.origem_carga.aba ? ` · ${l.origem_carga.aba}` : ""}${l.origem_carga.linha ? ` linha ${l.origem_carga.linha}` : ""}`;
  if (l.origem) return `De ${l.origem.lote}`;
  if (l.documento_entrada) return /^NF/i.test(l.documento_entrada) ? l.documento_entrada : `NF ${l.documento_entrada}`;
  return "—";
}

export default function CorrigirEstoque() {
  const [estoque, setEstoque] = useState("");
  const [busca, setBusca] = useState("");
  const [liga, setLiga] = useState("");
  const [conteiner, setConteiner] = useState("");
  const [comSaldo, setComSaldo] = useState(true);
  const [lista, setLista] = useState<LoteCorrigir[] | null>(null);
  const [ligas, setLigas] = useState<Liga[]>([]);
  const [aberto, setAberto] = useState<LoteCorrigir | null>(null);
  const [msg, setMsg] = useState("");
  const [erro, setErro] = useState("");
  const [versao, setVersao] = useState(0);

  useEffect(() => { void api.get<Liga[]>("/ligas").then(setLigas).catch(() => setLigas([])); }, []);
  useEffect(() => {
    let vivo = true;
    const t = window.setTimeout(async () => {
      setErro("");
      try {
        const r = await api.get<{ itens: LoteCorrigir[] }>(`/admin/estoque${qs({ estoque: estoque || undefined, busca: busca.trim() || undefined,
          liga: liga.trim() || undefined, conteiner: conteiner.trim() || undefined, com_saldo: comSaldo })}`);
        if (vivo) setLista(r.itens);
      } catch (e) {
        if (vivo) setErro(e instanceof Error ? e.message : "Não foi possível carregar o estoque.");
      }
    }, 300);
    return () => { vivo = false; window.clearTimeout(t); };
  }, [estoque, busca, liga, conteiner, comSaldo, versao]);

  const soma = useMemo(() => (lista ?? []).reduce((a, l) => a + l.saldo_kg, 0), [lista]);

  return (
    <>
      <header className="cabecalho">
        <h1>Corrigir estoque</h1>
        <p>Todos os lotes que não são do Estoque Mega (o Estoque Mega vem do Mega). Use na conferência física: achou diferença, clique em "Corrigir" e grave o que está certo.</p>
      </header>
      <div className="aviso-topo" role="note">
        <strong>Enquanto a carga das planilhas continuar, a recarga apaga estas correções</strong> (os lotes são recriados das planilhas).
        O saldo corrigido entra como ajuste de inventário: o histórico do lote não some.
      </div>

      <div className="chips" role="group" aria-label="Estoque" style={{ marginBottom: "var(--esp-3)" }}>
        {ESTOQUES.map((e) => (
          <button key={e.valor} type="button" className="chip" aria-pressed={estoque === e.valor} onClick={() => setEstoque(e.valor)}>{e.nome}</button>
        ))}
      </div>
      <div className="barra-filtros">
        <label style={{ flexBasis: "18rem" }}>Buscar<input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="lote, contêiner ou descrição" /></label>
        <label>Liga<input value={liga} onChange={(e) => setLiga(e.target.value.toUpperCase())} placeholder="H13" /></label>
        <label>Contêiner<input value={conteiner} onChange={(e) => setConteiner(e.target.value.toUpperCase())} /></label>
        <label className="marcar"><input type="checkbox" checked={comSaldo} onChange={(e) => setComSaldo(e.target.checked)} /><span>Só com saldo</span></label>
      </div>

      <div className="barra-acoes">
        <span className="contagem">{lista ? `${lista.length.toLocaleString("pt-BR")} lote(s) · ${kg(soma)} kg` : ""}</span>
      </div>
      {msg && <p className="validacao ok" role="status">{msg}</p>}
      {erro && <p className="erro" role="alert">{erro}</p>}

      {lista && (lista.length ? (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead><tr><th>Lote</th><th>Estoque</th><th>Contêiner</th><th>Material</th><th className="num">Saldo (kg)</th><th className="num">R$/kg</th><th>De onde veio</th><th><span className="sr-only">Ação</span></th></tr></thead>
            <tbody>
              {lista.map((l) => (
                <tr key={l.id}>
                  <td><Link to={`/estoque/${l.id}`}>{l.codigo}</Link>{l.tipo !== "ORIGINAL" && <><br /><span className="etiqueta">{TIPO_LOTE[l.tipo]}</span></>}
                    {l.corrigido && <><br /><span className="etiqueta info" title={l.corrigido_em ? `Corrigido em ${data(l.corrigido_em)}` : undefined}>corrigido</span></>}</td>
                  <td><span className={`estoque-tag ${l.estoque}`}>{ESTOQUE_NOME[l.estoque]}</span></td>
                  <td>{l.conteiner ?? "—"}</td>
                  <td><strong>{l.liga} {l.bitola}</strong><br /><span className="desc">{l.descricao ?? ""}</span></td>
                  <td className="num">{kg(l.saldo_kg)}</td>
                  <td className="num">{l.custo_kg !== null && l.custo_kg !== undefined ? rsKg(l.custo_kg) : "—"}</td>
                  <td><span className="desc">{origemTexto(l)}</span></td>
                  <td><button type="button" className="secundario pequeno" onClick={() => { setMsg(""); setAberto(l); }}><Icone nome="editar" />Corrigir</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className="estado-vazio"><strong>Nenhum lote com esses filtros</strong>Tire algum filtro ou desmarque "Só com saldo".</div>)}

      {aberto && (
        <JanelaCorrigir lote={aberto} ligas={ligas} aoFechar={() => setAberto(null)}
          aoGravar={(m) => { setAberto(null); setMsg(m); setVersao((v) => v + 1); }} />
      )}
    </>
  );
}

function JanelaCorrigir({ lote, ligas, aoFechar, aoGravar }: { lote: LoteCorrigir; ligas: Liga[]; aoFechar: () => void; aoGravar: (m: string) => void }) {
  const inicial = useMemo(() => ({
    conteiner: lote.conteiner ?? "", liga: lote.liga, formato: lote.formato, espessura: texto(lote.espessura), largura: texto(lote.largura),
    diametro: texto(lote.diametro), comprimento_fixado: lote.comprimento_fixado ?? "", descricao: lote.descricao ?? "",
    local_fisico: lote.local_fisico, saldo_kg: texto(lote.saldo_kg), custo_kg: texto(lote.custo_kg ?? null),
  }), [lote]);
  const [f, setF] = useState(inicial);
  const [obs, setObs] = useState("");
  const [v, setV] = useState<Previa | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [erro, setErro] = useState("");
  const [gravando, setGravando] = useState(false);
  const mudar = (p: Partial<typeof f>) => { setF({ ...f, ...p }); setV(null); setErro(""); };

  /** Só os campos que mudaram (campo ausente = não muda; contrato §16.7). */
  function corpo(c: Confirmacoes) {
    const b: Record<string, unknown> = { confirmacoes: c };
    const n = (s: string) => num(s) ?? null;
    if (f.conteiner.trim().toUpperCase() !== (lote.conteiner ?? "")) b.conteiner = f.conteiner.trim().toUpperCase() || null;
    if (f.liga !== lote.liga) b.liga = f.liga;
    if (f.formato !== lote.formato) b.formato = f.formato;
    for (const k of ["espessura", "largura", "diametro"] as const) if (f[k] !== inicial[k]) b[k] = n(f[k]);
    if (f.comprimento_fixado.trim() !== (lote.comprimento_fixado ?? "")) b.comprimento_fixado = f.comprimento_fixado.trim() || null;
    if (f.descricao.trim() !== (lote.descricao ?? "")) b.descricao = f.descricao.trim();
    if (f.local_fisico !== lote.local_fisico) b.local_fisico = f.local_fisico;
    if (f.saldo_kg !== inicial.saldo_kg) b.saldo_kg = n(f.saldo_kg);
    if (f.custo_kg !== inicial.custo_kg) b.custo_kg = n(f.custo_kg);
    if (obs.trim()) b.observacao = obs.trim();
    return b;
  }
  const algoMudou = Object.keys(corpo({})).some((k) => k !== "confirmacoes" && k !== "observacao");

  async function conferir() {
    setErro("");
    try { setV(await api.post<Previa>(`/admin/lotes/${lote.id}/correcao/validar`, corpo({}))); }
    catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível conferir."); }
  }
  async function gravar() {
    if (!v) return;
    setGravando(true);
    try {
      await api.post(`/admin/lotes/${lote.id}/correcao`, corpo(confirmacoesValidas(v.ocorrencias, conf)));
      aoGravar(`Lote ${lote.codigo} corrigido.`);
    } catch (e) {
      const x = validacaoDoErro<{ frase?: string; efeitos?: Efeito[] }>(e);
      if (x) setV(x); else setErro(e instanceof Error ? e.message : "Não foi possível gravar.");
    } finally {
      setGravando(false);
    }
  }

  const listaLigas = ligas.some((l) => l.codigo === lote.liga) ? ligas : [{ id: -1, codigo: lote.liga, ativo: true }, ...ligas];
  return (
    <Janela titulo={`Corrigir · ${lote.codigo}`} aoFechar={aoFechar} larga>
      <p className="desc">{ESTOQUE_NOME[lote.estoque]} · {origemTexto(lote)}. Mude só o que estiver diferente do físico; não precisa de justificativa.</p>
      <div className="barra-filtros">
        <label>Contêiner<input value={f.conteiner} onChange={(e) => mudar({ conteiner: e.target.value.toUpperCase() })} placeholder="sem contêiner" /></label>
        <label>Local
          <select value={f.local_fisico} onChange={(e) => mudar({ local_fisico: e.target.value as "RJ" | "ITU" })}>
            <option value="RJ">RJ no Rio</option><option value="ITU">RJ em Itu</option>
          </select>
        </label>
        <label>Saldo (kg)<input inputMode="decimal" value={f.saldo_kg} onChange={(e) => mudar({ saldo_kg: e.target.value })} /></label>
        <label>R$/kg<input inputMode="decimal" value={f.custo_kg} onChange={(e) => mudar({ custo_kg: e.target.value })} placeholder="sem valor" /></label>
      </div>
      <fieldset className="campo-sa">
        <legend>Material</legend>
        <p className="dica aviso-busca" role="note"><Icone nome="alerta" /> {AVISO_BUSCA}</p>
        <div className="barra-filtros">
          <label>Liga
            <select value={f.liga} onChange={(e) => mudar({ liga: e.target.value })}>
              {listaLigas.map((l) => <option key={l.codigo} value={l.codigo}>{l.codigo}{l.ativo ? "" : " (inativa)"}</option>)}
            </select>
          </label>
          <label>Formato
            <select value={f.formato} onChange={(e) => mudar({ formato: e.target.value })}>
              <option value="RETANGULAR">Retangular</option><option value="REDONDO">Redondo</option><option value="RETO">RETO</option>
            </select>
          </label>
          {f.formato !== "REDONDO" && <>
            <label>Espessura (mm)<input inputMode="decimal" value={f.espessura} onChange={(e) => mudar({ espessura: e.target.value })} /></label>
            <label>Largura (mm)<input inputMode="decimal" value={f.largura} onChange={(e) => mudar({ largura: e.target.value })} /></label>
          </>}
          {f.formato === "REDONDO" && <label>Diâmetro (mm)<input inputMode="decimal" value={f.diametro} onChange={(e) => mudar({ diametro: e.target.value })} /></label>}
          <label>Comprimento<input value={f.comprimento_fixado} onChange={(e) => mudar({ comprimento_fixado: e.target.value })} placeholder="opcional" /></label>
        </div>
        <label>Descrição<input value={f.descricao} onChange={(e) => mudar({ descricao: e.target.value })} maxLength={200} /></label>
        <p className="dica" role="note"><Icone nome="info" /> {AVISO_DESCRICAO}</p>
      </fieldset>
      <label>Observação (opcional)<textarea rows={2} value={obs} onChange={(e) => { setObs(e.target.value); setV(null); }} placeholder="Ex.: conferência física de 25/11" /></label>

      {v?.resultado?.frase && <p className="frase-resultado">{v.resultado.frase}</p>}
      {v && <PainelValidacao ocorrencias={v.ocorrencias} confirmacoes={conf} aoMudar={setConf} semOcorrencias="Pode gravar." />}
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        {!v ? <button className="primario" disabled={!algoMudou} onClick={() => void conferir()}>Ver o que muda</button>
          : <button className="primario" disabled={gravando || !podeGravar(v.ocorrencias, conf)} onClick={() => void gravar()}>Gravar correção</button>}
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}
