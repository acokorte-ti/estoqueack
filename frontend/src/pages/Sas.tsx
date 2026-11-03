import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api, data, kg, num, qs, validacaoDoErro, type Validacao } from "../api/cliente";
import { useSessao } from "../api/sessao";
import PainelValidacao, { confirmacoesValidas, podeGravar, type Confirmacoes } from "../components/PainelValidacao";

/* ------------------------------------------------------------------ tipos */

type SituacaoSa = "PENDENTE" | "PREPARADO" | "AGUARDANDO_MEGA" | "CONFIRMADO";
interface Sa {
  id: number; origem: "COP" | "CORTE_ITU" | "CARGA"; situacao: SituacaoSa; data: string; op: number; cliente: string | null;
  item_codigo: number | null; item_descricao: string | null; pedido: string | null; material: string | null; dimensao: string | null;
  conteiner: string | null; quantidade: number; peso_kg: number; rs_kg: number | null; valor_precificador: number | null;
  sa_codigo: number | null; sa_codigo_sugerido: number | null; sa_novo: boolean; outros_codigos: number[];
  sa_descricao: string | null; ncm: string | null; icms: string | null; ipi: string | null;
  nf: { numero: string; emitente: string } | null; cop: { id: number; numero: number; situacao: string } | null;
  exportado_renato_em: string | null; alterado_apos_exportar: boolean; atrasado: boolean;
}
interface CopResumo { id: number; numero: number; situacao: string; qtd_itens: number; peso_total_kg: number }
interface Lista { itens: Sa[]; total: number; cops_aguardando_sa: CopResumo[] }

const SITUACAO: Record<SituacaoSa, { nome: string; classe: string }> = {
  PENDENTE: { nome: "Pendente", classe: "" },
  PREPARADO: { nome: "Preparado", classe: "info" },
  AGUARDANDO_MEGA: { nome: "Aguardando Mega", classe: "atencao" },
  CONFIRMADO: { nome: "Confirmado", classe: "ok" },
};
const FILTROS: { chave: string; nome: string; situacao: SituacaoSa[] }[] = [
  { chave: "abertos", nome: "Em aberto", situacao: [] },
  { chave: "PENDENTE", nome: "Pendentes", situacao: ["PENDENTE"] },
  { chave: "PREPARADO", nome: "Preparados", situacao: ["PREPARADO"] },
  { chave: "AGUARDANDO_MEGA", nome: "Aguardando Mega", situacao: ["AGUARDANDO_MEGA"] },
  { chave: "CONFIRMADO", nome: "Confirmados", situacao: ["CONFIRMADO"] },
];
const EMITENTES = [
  { valor: "FIO_CERTO", nome: "Fio Certo" },
  { valor: "MEDIO_VALE", nome: "Médio Vale" },
  { valor: "OUTRO", nome: "Outro" },
];
const nomeEmitente = (v: string) => EMITENTES.find((e) => e.valor === v)?.nome ?? v;

/* ------------------------------------------------------------------ tela */

export default function Sas() {
  const { usuario } = useSessao();
  const altera = usuario?.perfil === "ESTOQUE" || usuario?.perfil === "ADMIN";
  const editaRs = altera || usuario?.perfil === "ANALISE";

  const [params] = useSearchParams();
  const copFiltro = params.get("cop");
  const [filtro, setFiltro] = useState("abertos");
  const [opFiltro, setOpFiltro] = useState("");
  const [lista, setLista] = useState<Lista | null>(null);
  const [sel, setSel] = useState<number[]>([]);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const carregar = useCallback(async () => {
    setErro("");
    const f = FILTROS.find((x) => x.chave === filtro)!;
    try {
      const r = await api.get<Lista>(`/sas${qs({ situacao: f.situacao, op: num(opFiltro), cop: copFiltro ?? undefined })}`);
      setLista(r);
      setSel((s) => s.filter((id) => r.itens.some((i) => i.id === id)));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível carregar a fila de SA.");
    }
  }, [filtro, opFiltro, copFiltro]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const itens = lista?.itens ?? [];
  const selecionados = itens.filter((i) => sel.includes(i.id));
  const alternar = (id: number) => setSel(sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]);

  async function acao(fn: () => Promise<string>) {
    setErro("");
    setAviso("");
    setOcupado(true);
    try {
      setAviso(await fn());
      await carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível concluir.");
    } finally {
      setOcupado(false);
    }
  }

  const preparar = () =>
    acao(async () => {
      const r = await api.post<Sa[]>("/sas/preparar", { ids: sel });
      setSel([]);
      return `${r.length} pedido(s) marcado(s) como preparado(s).`;
    });

  const verificar = () =>
    acao(async () => {
      const r = await api.post<{ verificados: number; confirmados: number; erro?: string | null }>("/sas/verificar", sel.length ? { ids: sel } : {});
      if (r.erro) throw new Error(`Mega: ${r.erro}`);
      return `${r.verificados} SA(s) verificado(s) no Mega, ${r.confirmados} confirmado(s).`;
    });

  // janelas
  const [codigoDe, setCodigoDe] = useState<Sa | null>(null);
  const [editarDe, setEditarDe] = useState<Sa | null>(null);
  const [nfAberta, setNfAberta] = useState(false);
  const selB2 = selecionados.filter((s) => s.origem === "CORTE_ITU");

  return (
    <>
      <header className="cabecalho">
        <h1>SA</h1>
        <p>Pedidos de SA que nascem do COP fechado e do corte em Itu de material RJ. Informe o código e confirme no Mega.</p>
      </header>

      {!!lista?.cops_aguardando_sa.length && (
        <div className="aviso-topo" role="status">
          <strong>COPs aguardando SA para serem enviados</strong>
          <ul>
            {lista.cops_aguardando_sa.map((c) => (
              <li key={c.id}>COP {c.numero}: {c.qtd_itens} item(ns), {kg(c.peso_total_kg)} kg</li>
            ))}
          </ul>
        </div>
      )}

      {erro && <p className="erro" role="alert">{erro}</p>}
      {aviso && <p className="validacao ok" role="status">{aviso}</p>}

      <div className="barra-filtros">
        <div className="chips" role="group" aria-label="Situação">
          {FILTROS.map((f) => (
            <button key={f.chave} type="button" className="chip" aria-pressed={filtro === f.chave} onClick={() => setFiltro(f.chave)}>{f.nome}</button>
          ))}
        </div>
        <label>
          OP
          <input inputMode="numeric" value={opFiltro} onChange={(e) => setOpFiltro(e.target.value)} placeholder="todas" />
        </label>
        {copFiltro && <span className="etiqueta info">Só o COP {copFiltro}</span>}
      </div>

      {altera && (
        <div className="barra-acoes">
          <span className="contagem">{sel.length ? `${sel.length} selecionado(s)` : `${lista?.total ?? 0} pedido(s)`}</span>
          <button className="secundario" disabled={!sel.length || ocupado} onClick={() => void preparar()}>Marcar como preparado</button>
          <button className="secundario" disabled={!selB2.length || ocupado} onClick={() => setNfAberta(true)} title="Só para linhas de corte em Itu (B2)">
            Informar NF (corte em Itu)
          </button>
          <button className="primario" disabled={ocupado} onClick={() => void verificar()}>
            {ocupado ? "Consultando…" : sel.length ? "Verificar selecionados no Mega" : "Verificar no Mega agora"}
          </button>
        </div>
      )}

      {lista && !itens.length ? (
        <div className="estado-vazio">
          <strong>Nenhum pedido de SA nesta situação</strong>
          Os pedidos aparecem aqui quando o RJ fecha um COP ou quando há corte em Itu de material RJ.
        </div>
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela tabela-sa">
            <thead>
              <tr>
                {altera && <th><span className="sr-only">Selecionar</span></th>}
                <th>OP</th><th>Cliente / pedido</th><th>Item</th><th>Material</th><th className="num">Qtd</th><th className="num">Peso</th>
                <th>Código do SA</th><th>Situação</th><th>COP / NF</th><th className="num">R$/kg</th><th><span className="sr-only">Ações</span></th>
              </tr>
            </thead>
            <tbody>
              {itens.map((s) => (
                <tr key={s.id} className={[s.atrasado ? "atrasado" : "", sel.includes(s.id) ? "selecionada" : ""].join(" ")}>
                  {altera && (
                    <td><input type="checkbox" aria-label={`Selecionar OP ${s.op}`} checked={sel.includes(s.id)} onChange={() => alternar(s.id)} /></td>
                  )}
                  <td><strong>{s.op}</strong><br /><span className="desc">{data(s.data)}</span></td>
                  <td>{s.cliente ?? "—"}<br /><span className="desc">{s.pedido ? `pedido ${s.pedido}` : "sem pedido"}</span></td>
                  <td>{s.item_codigo ?? "—"}<br /><span className="desc">{s.item_descricao ?? ""}</span></td>
                  <td>{s.material} {s.dimensao}<br /><span className="desc">{s.conteiner ?? "—"}</span></td>
                  <td className="num">{s.quantidade}</td>
                  <td className="num">{kg(s.peso_kg)} kg</td>
                  <td>
                    {s.sa_codigo ? <strong>{s.sa_codigo}</strong> : s.sa_novo ? <span className="etiqueta atencao">SA novo – cadastrar no Mega</span> : "—"}
                    {s.sa_codigo && s.sa_codigo_sugerido && s.sa_codigo !== s.sa_codigo_sugerido && <><br /><span className="desc">sugerido {s.sa_codigo_sugerido}</span></>}
                  </td>
                  <td>
                    <span className={`etiqueta ${SITUACAO[s.situacao].classe}`}>{SITUACAO[s.situacao].nome}</span>
                    {s.atrasado && <><br /><span className="etiqueta ruim">mais de 48 h</span></>}
                  </td>
                  <td>
                    {s.cop ? `COP ${s.cop.numero}` : s.origem === "CORTE_ITU" ? "Corte em Itu" : "—"}
                    <br /><span className="desc">{s.nf ? `NF ${s.nf.numero} (${nomeEmitente(s.nf.emitente)})` : "sem NF"}</span>
                  </td>
                  <td className="num">{s.rs_kg !== null ? s.rs_kg.toLocaleString("pt-BR", { minimumFractionDigits: 2 }) : "—"}</td>
                  <td className="acoes">
                    {altera && s.situacao !== "CONFIRMADO" && <button className="link" onClick={() => setCodigoDe(s)}>Informar código</button>}
                    {editaRs && <button className="link" onClick={() => setEditarDe(s)}>{altera && s.situacao !== "CONFIRMADO" ? "Editar" : "R$/kg"}</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {codigoDe && <JanelaCodigo sa={codigoDe} aoFechar={() => setCodigoDe(null)} aoGravar={(m) => { setCodigoDe(null); setAviso(m); void carregar(); }} />}
      {editarDe && (
        <JanelaEditar sa={editarDe} soRs={!altera || editarDe.situacao === "CONFIRMADO"} aoFechar={() => setEditarDe(null)}
          aoGravar={() => { setEditarDe(null); setAviso("Pedido de SA atualizado."); void carregar(); }} />
      )}
      {nfAberta && (
        <JanelaNf ids={selB2.map((s) => s.id)} aoFechar={() => setNfAberta(false)}
          aoGravar={(n) => { setNfAberta(false); setSel([]); setAviso(`NF ${n} informada em ${selB2.length} linha(s).`); void carregar(); }} />
      )}
    </>
  );
}

/* ------------------------------------------------------------------ janelas */

function useJanela() {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return ref;
}

function JanelaCodigo({ sa, aoFechar, aoGravar }: { sa: Sa; aoFechar: () => void; aoGravar: (msg: string) => void }) {
  const ref = useJanela();
  const [codigo, setCodigo] = useState(String(sa.sa_codigo ?? sa.sa_codigo_sugerido ?? ""));
  const [validacao, setValidacao] = useState<Validacao | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function conferir(e?: FormEvent) {
    e?.preventDefault();
    setErro("");
    const n = Number(codigo);
    if (!Number.isInteger(n) || n <= 0) return setErro("Digite o código do SA (só números).");
    setOcupado(true);
    try {
      setValidacao(await api.post<Validacao>(`/sas/${sa.id}/codigo/validar`, { sa_codigo: n, confirmacoes: {} }));
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível conferir o código.");
    } finally {
      setOcupado(false);
    }
  }

  async function gravar() {
    if (!validacao) return;
    setErro("");
    setOcupado(true);
    try {
      const r = await api.post<Sa>(`/sas/${sa.id}/codigo`, { sa_codigo: Number(codigo), confirmacoes: confirmacoesValidas(validacao.ocorrencias, conf) });
      aoGravar(r.situacao === "CONFIRMADO" ? `SA ${codigo} confirmado no Mega para a OP ${sa.op}.` : `Código ${codigo} informado para a OP ${sa.op}. Aguardando a confirmação no Mega.`);
    } catch (err) {
      const v = validacaoDoErro<Record<string, unknown>>(err);
      if (v) setValidacao(v);
      else setErro(err instanceof Error ? err.message : "Não foi possível gravar o código.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <dialog ref={ref} className="janela" aria-labelledby="titulo-codigo" onClose={aoFechar}>
      <div className="painel-form">
        <h2 id="titulo-codigo">Código do SA · OP {sa.op}</h2>
        <p className="desc">{sa.item_codigo} · {sa.item_descricao}</p>
        {sa.sa_novo && !sa.sa_codigo_sugerido && (
          <p className="validacao alerta">Esta peça nunca teve SA. Cadastre o SA novo no Mega e digite o código aqui.</p>
        )}
        <form className="linha-form" style={{ marginBottom: 0 }} onSubmit={(e) => void conferir(e)}>
          <label>
            <span className="rotulo">Código do SA {sa.sa_codigo_sugerido && Number(codigo) === sa.sa_codigo_sugerido && <span className="sugerido">último SA desta peça</span>}</span>
            <input inputMode="numeric" autoFocus value={codigo} onChange={(e) => { setCodigo(e.target.value); setValidacao(null); setConf({}); }} required />
          </label>
          <button className="secundario" disabled={ocupado}>Conferir</button>
        </form>
        {!!sa.outros_codigos.length && <p className="dica">Outros códigos já usados nesta peça: {sa.outros_codigos.join(", ")}.</p>}
        {validacao && (
          <PainelValidacao ocorrencias={validacao.ocorrencias} confirmacoes={conf} aoMudar={setConf} semOcorrencias="Código conferido no Mega." />
        )}
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario" disabled={!validacao || ocupado || !podeGravar(validacao.ocorrencias, conf)} onClick={() => void gravar()}>
            Gravar código
          </button>
          <button type="button" className="secundario" onClick={() => ref.current?.close()}>Cancelar</button>
        </div>
      </div>
    </dialog>
  );
}

function JanelaEditar({ sa, soRs, aoFechar, aoGravar }: { sa: Sa; soRs: boolean; aoFechar: () => void; aoGravar: () => void }) {
  const ref = useJanela();
  const [f, setF] = useState({
    rs_kg: sa.rs_kg !== null ? String(sa.rs_kg).replace(".", ",") : "",
    sa_descricao: sa.sa_descricao ?? "", ncm: sa.ncm ?? "", icms: sa.icms ?? "", ipi: sa.ipi ?? "", pedido: sa.pedido ?? "",
  });
  const [erro, setErro] = useState("");

  async function salvar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    const corpo: Record<string, unknown> = { rs_kg: num(f.rs_kg) ?? null };
    if (!soRs) Object.assign(corpo, { sa_descricao: f.sa_descricao || null, ncm: f.ncm || null, icms: f.icms || null, ipi: f.ipi || null, pedido: f.pedido || null });
    try {
      await api.patch(`/sas/${sa.id}`, corpo);
      aoGravar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível salvar.");
    }
  }

  const valor = num(f.rs_kg) !== undefined && sa.quantidade ? ((num(f.rs_kg) ?? 0) * sa.peso_kg) / sa.quantidade : null;

  return (
    <dialog ref={ref} className="janela" aria-labelledby="titulo-editar-sa" onClose={aoFechar}>
      <form className="painel-form" onSubmit={(e) => void salvar(e)}>
        <h2 id="titulo-editar-sa">Pedido de SA · OP {sa.op}</h2>
        {sa.exportado_renato_em && <p className="validacao alerta">Já exportado para o Renato em {data(sa.exportado_renato_em)}. A alteração avisa o Renato.</p>}
        <label>
          R$/kg (opcional)
          <input inputMode="decimal" value={f.rs_kg} onChange={(e) => setF({ ...f, rs_kg: e.target.value })} autoFocus />
          <small className="dica">{valor !== null ? `Valor precificador: R$ ${valor.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} por peça` : "Preenchido por quem cuida do custo; o sistema não calcula."}</small>
        </label>
        {!soRs && (
          <>
            <label>Descrição do SA<input value={f.sa_descricao} onChange={(e) => setF({ ...f, sa_descricao: e.target.value })} /></label>
            <div className="grade-form">
              <label>NCM<input value={f.ncm} onChange={(e) => setF({ ...f, ncm: e.target.value })} /></label>
              <label>ICMS<input value={f.icms} onChange={(e) => setF({ ...f, icms: e.target.value })} /></label>
              <label>IPI<input value={f.ipi} onChange={(e) => setF({ ...f, ipi: e.target.value })} /></label>
              <label>Pedido<input value={f.pedido} onChange={(e) => setF({ ...f, pedido: e.target.value })} /></label>
            </div>
          </>
        )}
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario">Salvar alterações</button>
          <button type="button" className="secundario" onClick={() => ref.current?.close()}>Cancelar</button>
        </div>
      </form>
    </dialog>
  );
}

function JanelaNf({ ids, aoFechar, aoGravar }: { ids: number[]; aoFechar: () => void; aoGravar: (numero: string) => void }) {
  const ref = useJanela();
  const [f, setF] = useState({ numero: "", emitente: "FIO_CERTO", data: "" });
  const [erro, setErro] = useState("");

  async function salvar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    try {
      await api.post("/sas/nf", { ids, numero: f.numero.trim(), emitente: f.emitente, data: f.data || null });
      aoGravar(f.numero.trim());
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível informar a NF.");
    }
  }

  return (
    <dialog ref={ref} className="janela" aria-labelledby="titulo-nf" onClose={aoFechar}>
      <form className="painel-form" onSubmit={(e) => void salvar(e)}>
        <h2 id="titulo-nf">NF de transferência · {ids.length} linha(s) de corte em Itu</h2>
        <label>Nº da NF<input value={f.numero} onChange={(e) => setF({ ...f, numero: e.target.value })} autoFocus required /></label>
        <fieldset className="formatos">
          <legend>Emitente</legend>
          {EMITENTES.map((x) => (
            <label key={x.valor} className={f.emitente === x.valor ? "opcao marcada" : "opcao"}>
              <input type="radio" name="emitente" checked={f.emitente === x.valor} onChange={() => setF({ ...f, emitente: x.valor })} />
              {x.nome}
            </label>
          ))}
        </fieldset>
        <label>Data da NF (opcional)<input type="date" value={f.data} onChange={(e) => setF({ ...f, data: e.target.value })} /></label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario">Informar NF</button>
          <button type="button" className="secundario" onClick={() => ref.current?.close()}>Cancelar</button>
        </div>
      </form>
    </dialog>
  );
}
