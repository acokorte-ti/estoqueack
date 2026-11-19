import { Fragment, useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, data, kg, num, qs, reais, rsKg, validacaoDoErro, type Validacao } from "../api/cliente";
import { useSessao } from "../api/sessao";
import Janela, { fecharJanela } from "../components/Janela";
import Icone from "../components/Icone";
import PainelValidacao, { confirmacoesValidas, podeGravar, type Confirmacoes } from "../components/PainelValidacao";
import { EMITENTES_LANCAMENTO, nomeEmitente } from "../api/cop";

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
  avisos?: { codigo: string; nivel: string; mensagem: string }[];
  /** contrato §7.1 (R070): confirmado pela ferramenta de teste, sem ler o Mega */
  confirmacao_teste?: boolean;
}
interface CopResumo { id: number; numero: number; situacao: string; qtd_itens: number; peso_total_kg: number }
interface Lista { itens: Sa[]; total: number; cops_aguardando_sa: CopResumo[] }

const SITUACAO: Record<SituacaoSa, { nome: string; classe: string; dica: string }> = {
  PENDENTE: { nome: "Pendente", classe: "", dica: "Fabiano confere e pede o SA" },
  PREPARADO: { nome: "Preparado", classe: "info", dica: "aguardando cadastro do SA (Amanda)" },
  AGUARDANDO_MEGA: { nome: "Aguardando Mega", classe: "atencao", dica: "código informado; o sistema confere no Mega" },
  CONFIRMADO: { nome: "Confirmado", classe: "ok", dica: "" },
};
const FILTROS: { chave: string; nome: string; situacao: SituacaoSa[] }[] = [
  { chave: "abertos", nome: "Em aberto", situacao: [] },
  { chave: "PENDENTE", nome: "Pendentes", situacao: ["PENDENTE"] },
  { chave: "PREPARADO", nome: "Preparados", situacao: ["PREPARADO"] },
  { chave: "AGUARDANDO_MEGA", nome: "Aguardando Mega", situacao: ["AGUARDANDO_MEGA"] },
  { chave: "CONFIRMADO", nome: "Confirmados", situacao: ["CONFIRMADO"] },
];

/** "SA confirmado 1 de 3" com a barrinha (layout A): mostra por que a NF do COP está bloqueada sem abrir o COP. */
function Progresso({ rotulo, feito, total }: { rotulo: string; feito: number; total: number }) {
  const pct = total ? (feito / total) * 100 : 0;
  return (
    <div className="progresso">
      <span>{rotulo} {feito} de {total}</span>
      <span className="trilho" aria-hidden="true"><i className={feito < total ? "parcial" : undefined} style={{ width: `${pct}%` }} /></span>
    </div>
  );
}

/* ------------------------------------------------------------------ tela */

export default function Sas() {
  const { usuario, modoTeste } = useSessao();
  // contrato §7.1 (R070): ferramenta só da homologação, só ADMIN
  const confirmaTeste = modoTeste && usuario?.perfil === "ADMIN";
  const altera = usuario?.perfil === "ESTOQUE" || usuario?.perfil === "ADMIN";
  const editaRs = altera || usuario?.perfil === "ANALISE";
  // spec v3.13 T14 / contrato §7 [P36]: a Amanda (perfil Análise) também informa o código do SA depois de cadastrar no Mega
  const informaCodigo = altera || usuario?.perfil === "ANALISE";

  // spec v3.16 T14 (Eduardo, 2026-11-18): a fila é vista e filtrada por COP (um COP tem várias OPs), não por OP;
  // o número do COP fica na URL (?cop=), o mesmo link do aviso "COP fechado: SA a fazer"
  const [params, setParams] = useSearchParams();
  const copFiltro = params.get("cop") ?? "";
  const mudarCop = (v: string) => setParams(v.trim() ? { cop: v.trim() } : {}, { replace: true });
  const [filtro, setFiltro] = useState("abertos");
  const [historico, setHistorico] = useState(false);
  const [pag, setPag] = useState(1);
  const [lista, setLista] = useState<Lista | null>(null);
  const [sel, setSel] = useState<number[]>([]);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const carregar = useCallback(async () => {
    setErro("");
    const f = FILTROS.find((x) => x.chave === filtro)!;
    try {
      const r = await api.get<Lista>(`/sas${qs({ situacao: f.situacao, cop: num(copFiltro),
        origem: historico ? ["COP", "CORTE_ITU", "CARGA"] : undefined, pagina: pag, por_pagina: 100 })}`);
      setLista(r);
      setSel((s) => s.filter((id) => r.itens.some((i) => i.id === id)));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível carregar a fila de SA.");
    }
  }, [filtro, copFiltro, historico, pag]);

  useEffect(() => {
    void carregar();
  }, [carregar]);
  useEffect(() => setPag(1), [filtro, copFiltro, historico]);

  const itens = lista?.itens ?? [];
  const selecionados = itens.filter((i) => sel.includes(i.id));
  const fAtual = FILTROS.find((x) => x.chave === filtro)!;
  const exportarTudo = `/api/exportar/sas.xlsx${qs({ situacao: fAtual.situacao, cop: num(copFiltro),
    origem: historico ? ["COP", "CORTE_ITU", "CARGA"] : undefined })}`;
  const exportarSelecionados = `/api/exportar/sas.xlsx${qs({ ids: sel })}`;
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
      return `${r.length} pedido(s) marcado(s) como preparado(s): aguardando cadastro do SA no Mega pela Amanda.`;
    });

  /** sem ids: verifica todos os aguardando Mega; com ids: só os marcados */
  const verificar = (ids: number[]) =>
    acao(async () => {
      const r = await api.post<{ verificados: number; confirmados: number; erro?: string | null }>("/sas/verificar", ids.length ? { ids } : {});
      if (r.erro) throw new Error(`Mega: ${r.erro}`);
      return `${r.verificados} SA(s) verificado(s) no Mega, ${r.confirmados} confirmado(s).`;
    });

  const atualizarLinha = (r: Sa) => setLista((l) => (l ? { ...l, itens: l.itens.map((i) => (i.id === r.id ? { ...i, ...r } : i)) } : l));

  const confirmarTeste = (s: Sa) => {
    if (!s.sa_codigo) return setTesteDe(s);
    void acao(async () => {
      const r = await api.post<Sa>(`/sas/${s.id}/confirmar-teste`, {});
      atualizarLinha(r);
      return `SA ${r.sa_codigo ?? s.sa_codigo} da OP ${s.op} confirmado em teste (sem ler o Mega).`;
    });
  };

  // janelas
  const [testeDe, setTesteDe] = useState<Sa | null>(null);
  const [codigoDe, setCodigoDe] = useState<Sa | null>(null);
  // soRs: o botão da coluna R$/kg abre só o R$/kg; "Dados do SA" abre descrição, NCM, ICMS, IPI e pedido também
  const [editarDe, setEditarDe] = useState<{ sa: Sa; soRs: boolean } | null>(null);
  const [nfAberta, setNfAberta] = useState(false);
  const selB2 = selecionados.filter((s) => s.origem === "CORTE_ITU");

  // spec v3.16 T14: um grupo por COP, na ordem em que aparecem; corte em Itu (B2) num grupo próprio
  const NCOL = altera ? 9 : 8;
  const grupos: { chave: string; titulo: string; cop: Sa["cop"]; itens: Sa[] }[] = [];
  for (const s of itens) {
    const chave = s.cop ? `cop-${s.cop.id}` : s.origem === "CORTE_ITU" ? "corte-itu" : "outros";
    let g = grupos.find((x) => x.chave === chave);
    if (!g) {
      g = { chave, cop: s.cop, itens: [],
        titulo: s.cop ? `COP ${s.cop.numero}` : s.origem === "CORTE_ITU" ? "Corte em Itu (sem COP)" : "Histórico da carga (sem COP)" };
      grupos.push(g);
    }
    g.itens.push(s);
  }

  /** Coluna "Código do SA": o código, ou o botão para informar/corrigir (Fabiano, Amanda) */
  function celulaCodigo(s: Sa) {
    const pode = informaCodigo && s.situacao !== "CONFIRMADO";
    return (
      <>
        {s.sa_codigo ? (
          pode ? (
            <button type="button" className="valor" onClick={() => setCodigoDe(s)} title="Corrigir o código do SA"
              aria-label={`Código do SA ${s.sa_codigo} da OP ${s.op}: corrigir`}>{s.sa_codigo}<Icone nome="editar" /></button>
          ) : <strong className="mono">{s.sa_codigo}</strong>
        ) : pode ? (
          <button type="button" className="falta" onClick={() => setCodigoDe(s)} aria-label={`Informar o código do SA da OP ${s.op}`}>
            <Icone nome="codigo" />Informar código
          </button>
        ) : <span className="desc">—</span>}
        {s.sa_codigo && s.sa_codigo_sugerido && s.sa_codigo !== s.sa_codigo_sugerido && <span className="sub">sugerido {s.sa_codigo_sugerido}</span>}
        {!s.sa_codigo && s.sa_novo && <span className="sub">SA novo · a Amanda cadastra no Mega</span>}
        {altera && s.situacao !== "CONFIRMADO" && (
          <div className="celula-acoes">
            <button type="button" className="link" onClick={() => setEditarDe({ sa: s, soRs: false })}
              aria-label={`Dados do SA da OP ${s.op}: descrição, NCM, ICMS, IPI e pedido`}><Icone nome="editar" />Dados do SA</button>
          </div>
        )}
      </>
    );
  }

  /** Coluna "R$/kg": "Falta" tracejado (obrigatório antes da NF do RJ) ou o valor com o lápis para corrigir */
  function celulaRs(s: Sa) {
    const tem = (s.rs_kg ?? 0) > 0;
    const porPeca = s.valor_precificador ? <span className="sub">R$&nbsp;{reais(s.valor_precificador)}/pç</span> : null;
    if (!editaRs) {
      return tem ? <>{rsKg(s.rs_kg ?? 0)}{porPeca}</>
        : s.origem === "CARGA" ? "—" : <span className="etiqueta atencao" title="Obrigatório antes da NF de transferência">falta</span>;
    }
    const abrir = () => setEditarDe({ sa: s, soRs: true });
    if (tem) {
      return (
        <>
          <button type="button" className="valor" onClick={abrir} title="Corrigir o R$/kg"
            aria-label={`R$/kg da OP ${s.op}: ${rsKg(s.rs_kg ?? 0)}, corrigir`}>{rsKg(s.rs_kg ?? 0)}<Icone nome="editar" /></button>
          {porPeca}
        </>
      );
    }
    if (s.origem === "CARGA") {
      return <button type="button" className="valor" onClick={abrir} title="Informar o R$/kg (opcional no histórico da carga)"
        aria-label={`Informar o R$/kg da OP ${s.op} (opcional)`}>—<Icone nome="editar" /></button>;
    }
    return (
      <button type="button" className="falta" onClick={abrir} title="Obrigatório antes da NF de transferência do RJ"
        aria-label={`Informar o R$/kg da OP ${s.op} (falta, obrigatório antes da NF do RJ)`}><Icone nome="alerta" />Falta</button>
    );
  }

  return (
    <>
      <header className="cabecalho cabecalho-acao">
        <div>
          <h1>Cadastro de SA</h1>
          <p>Pedidos de SA (semiacabado) agrupados por COP, e os do corte em Itu de material RJ. O Fabiano confere e pede o SA;
            a Amanda cadastra no Mega e informa o código; o sistema confirma lendo o Mega. O RJ só informa a NF de um COP quando
            todos os itens têm <strong>SA confirmado e R$/kg do precificador</strong>.</p>
        </div>
        <div className="acoes-cabecalho">
          <a className="secundario" href={exportarTudo} download><Icone nome="baixar" />Exportar para Excel</a>
          {altera && (
            <button className={sel.length ? "secundario" : "primario"} disabled={ocupado} onClick={() => void verificar([])}>
              <Icone nome="atualizar" />{ocupado && !sel.length ? "Consultando…" : "Verificar no Mega agora"}
            </button>
          )}
        </div>
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

      <section className="quadro" aria-label="Pedidos de SA">
        <div className="barra-filtros">
          <div className="chips" role="group" aria-label="Situação">
            {FILTROS.map((f) => (
              <button key={f.chave} type="button" className="chip" aria-pressed={filtro === f.chave} onClick={() => setFiltro(f.chave)}>{f.nome}</button>
            ))}
          </div>
          <label>
            COP
            <input inputMode="numeric" value={copFiltro} onChange={(e) => mudarCop(e.target.value)} placeholder="todos" style={{ width: "8rem" }} />
          </label>
          <label className="marcar">
            <input type="checkbox" checked={historico} onChange={(e) => setHistorico(e.target.checked)} />
            <span>Incluir histórico da carga (planilha de SA)</span>
          </label>
          <span className="desc" style={{ marginLeft: "auto", alignSelf: "center" }}>{lista?.total ?? 0} pedido(s)</span>
        </div>

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
                  {altera && <th className="marcar-linha"><span className="sr-only">Selecionar</span></th>}
                  <th>OP / cliente</th><th>Item</th><th>Material · contêiner</th><th className="num">Peso · peças</th>
                  <th>Código do SA</th><th>Situação</th><th>NF</th><th className="num">R$/kg</th>
                </tr>
              </thead>
              <tbody>
                {grupos.map((g) => {
                  const n = g.itens.length;
                  const conf = g.itens.filter((s) => s.situacao === "CONFIRMADO").length;
                  const comRs = g.itens.filter((s) => (s.rs_kg ?? 0) > 0).length;
                  const todosSel = g.itens.every((s) => sel.includes(s.id));
                  return (
                  <Fragment key={g.chave}>
                  <tr className="grupo-cop">
                    <td colSpan={NCOL}>
                      <div className="grupo-cab">
                        <span className="grupo-titulo">
                          {altera && (
                            <input type="checkbox" aria-label={`Selecionar ${g.titulo}`} checked={todosSel}
                              onChange={() => setSel(todosSel ? sel.filter((id) => !g.itens.some((s) => s.id === id)) : [...new Set([...sel, ...g.itens.map((s) => s.id)])])} />
                          )}
                          <Icone nome={g.cop ? "envio" : g.chave === "corte-itu" ? "corte" : "lista"} />
                          {g.titulo}
                        </span>
                        {g.cop && (conf === n && comRs === n
                          ? <span className="etiqueta ok">Pronto para a NF do RJ</span>
                          : g.cop.situacao === "FECHADO" && <span className="etiqueta bloqueio">NF do RJ bloqueada até SA e R$/kg</span>)}
                        <Progresso rotulo="SA confirmado" feito={conf} total={n} />
                        {g.chave !== "outros" && <Progresso rotulo="R$/kg" feito={comRs} total={n} />}
                        <span className="desc">{n} OP(s)</span>
                        {g.cop && (
                          <div className="empurra">
                            <Link className="secundario pequeno" to={`/cops/${g.cop.id}`}>Abrir COP<Icone nome="seta" /></Link>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                  {g.itens.map((s) => (
                  <Fragment key={s.id}>
                  <tr className={["linha-sa", s.atrasado ? "atrasado" : "", sel.includes(s.id) ? "selecionada" : "", s.avisos?.length ? "com-aviso" : ""].join(" ")}>
                    {altera && (
                      <td className="marcar-linha"><input type="checkbox" aria-label={`Selecionar OP ${s.op}`} checked={sel.includes(s.id)} onChange={() => alternar(s.id)} /></td>
                    )}
                    <td className="quebra" data-rotulo="OP / cliente">
                      <strong className="mono">{s.op}</strong>
                      <span className="sub">{s.cliente ?? "—"}</span>
                      <span className="sub">{data(s.data)} · {s.pedido ? `pedido ${s.pedido}` : "sem pedido"}</span>
                    </td>
                    <td className="quebra" data-rotulo="Item">{s.item_codigo ?? "—"}<span className="sub">{s.item_descricao ?? ""}</span></td>
                    <td data-rotulo="Material · contêiner">{s.material} {s.dimensao}<span className="sub mono">{s.conteiner ?? "—"}</span></td>
                    <td className="num" data-rotulo="Peso · peças">{kg(s.peso_kg)} kg<span className="sub">{s.quantidade} pç</span></td>
                    <td data-rotulo="Código do SA">{celulaCodigo(s)}</td>
                    <td className="quebra" data-rotulo="Situação">
                      <span className={`etiqueta ${SITUACAO[s.situacao]?.classe ?? ""}`}>{SITUACAO[s.situacao]?.nome ?? s.situacao}</span>
                      {SITUACAO[s.situacao]?.dica && <span className="sub">{SITUACAO[s.situacao].dica}</span>}
                      {(s.atrasado || s.confirmacao_teste || (confirmaTeste && s.situacao !== "CONFIRMADO")) && (
                        <div className="celula-acoes">
                          {s.atrasado && <span className="etiqueta ruim">mais de 48 h</span>}
                          {s.confirmacao_teste && <span className="etiqueta atencao" title="Confirmado pela ferramenta de teste, sem ler o Mega">confirmado em teste</span>}
                          {confirmaTeste && s.situacao !== "CONFIRMADO" && (
                            <button type="button" className="link botao-teste" disabled={ocupado} onClick={() => confirmarTeste(s)} title="Marca como confirmado sem ler o Mega. Só existe na homologação.">
                              Confirmar SA (teste) <span className="etiqueta atencao">só homologação</span>
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                    <td data-rotulo="NF">
                      {s.nf ? <>NF {s.nf.numero}<span className="sub">{nomeEmitente(s.nf.emitente)}</span></> : <span className="desc">sem NF</span>}
                    </td>
                    <td className="num" data-rotulo="R$/kg">{celulaRs(s)}</td>
                  </tr>
                  {!!s.avisos?.length && (
                    <tr className="linha-aviso">
                      <td colSpan={NCOL}>
                        {s.avisos.map((a) => <p key={a.codigo} className="validacao alerta">{a.mensagem}</p>)}
                      </td>
                    </tr>
                  )}
                  </Fragment>
                  ))}
                  </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {lista && lista.total > 100 && (
        <div className="paginacao">
          <button className="secundario" disabled={pag <= 1} onClick={() => setPag(pag - 1)}>Anterior</button>
          <span>Página {pag} de {Math.ceil(lista.total / 100)} · {lista.total.toLocaleString("pt-BR")} pedidos</span>
          <button className="secundario" disabled={pag >= Math.ceil(lista.total / 100)} onClick={() => setPag(pag + 1)}>Próxima</button>
        </div>
      )}

      {altera && sel.length > 0 && (
        <div className="barra-lote" role="region" aria-label="Ações para os pedidos selecionados">
          <span><b>{sel.length}</b> selecionado(s)</span>
          <button type="button" className="secundario pequeno" disabled={ocupado} onClick={() => void preparar()}>Marcar como preparado</button>
          <button type="button" className="secundario pequeno" disabled={!selB2.length || ocupado} onClick={() => setNfAberta(true)}
            title="Só para linhas de corte em Itu (B2)">Informar NF (corte em Itu)</button>
          <a className="secundario pequeno" href={exportarSelecionados} download><Icone nome="baixar" />Exportar</a>
          <button type="button" className="primario pequeno" disabled={ocupado} onClick={() => void verificar(sel)}>
            <Icone nome="atualizar" />{ocupado ? "Consultando…" : "Verificar no Mega"}
          </button>
          <button type="button" className="fantasma pequeno" onClick={() => setSel([])} aria-label="Desmarcar todos"><Icone nome="x" /></button>
        </div>
      )}

      {testeDe && (
        <JanelaTeste sa={testeDe} aoFechar={() => setTesteDe(null)}
          aoGravar={(r) => { setTesteDe(null); atualizarLinha(r); setAviso(`SA ${r.sa_codigo ?? ""} da OP ${testeDe.op} confirmado em teste (sem ler o Mega).`); void carregar(); }} />
      )}
      {codigoDe && <JanelaCodigo sa={codigoDe} aoFechar={() => setCodigoDe(null)} aoGravar={(m) => { setCodigoDe(null); setAviso(m); void carregar(); }} />}
      {editarDe && (
        <JanelaEditar sa={editarDe.sa} soRs={editarDe.soRs || !altera || editarDe.sa.situacao === "CONFIRMADO"} aoFechar={() => setEditarDe(null)}
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

// janelas usam o componente compartilhado components/Janela (antes: useJanela + <dialog> repetidos aqui)
function JanelaCodigo({ sa, aoFechar, aoGravar }: { sa: Sa; aoFechar: () => void; aoGravar: (msg: string) => void }) {
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
    <Janela titulo={`Código do SA · OP ${sa.op}`} aoFechar={aoFechar}>
      <div className="bloco-passo" style={{ gap: "var(--esp-4)" }}>
        <p className="desc">{sa.item_codigo} · {sa.item_descricao}</p>
        <p className="dica">Informe o código depois que o SA estiver cadastrado no Mega pela Amanda. Fica "Aguardando Mega" e o sistema já tenta confirmar.</p>
        {sa.sa_novo && !sa.sa_codigo_sugerido && (
          <p className="validacao alerta">Esta peça nunca teve SA. Depois que a Amanda cadastrar o SA novo no Mega, digite o código aqui.</p>
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
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Cancelar</button>
        </div>
      </div>
    </Janela>
  );
}

/** contrato §7.1 (R070): linha sem código pede o código antes de confirmar em teste */
function JanelaTeste({ sa, aoFechar, aoGravar }: { sa: Sa; aoFechar: () => void; aoGravar: (r: Sa) => void }) {
  const [codigo, setCodigo] = useState(String(sa.sa_codigo_sugerido ?? ""));
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function confirmar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    const n = Number(codigo);
    if (!Number.isInteger(n) || n <= 0) return setErro("Digite o código do SA (só números).");
    setOcupado(true);
    try {
      aoGravar(await api.post<Sa>(`/sas/${sa.id}/confirmar-teste`, { sa_codigo: n }));
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível confirmar em teste.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <Janela titulo={`Confirmar SA (teste) · OP ${sa.op}`} aoFechar={aoFechar}>
      <form className="bloco-passo" style={{ gap: "var(--esp-4)" }} onSubmit={(e) => void confirmar(e)}>
        <p><span className="etiqueta atencao">só homologação</span></p>
        <p className="desc">{sa.item_codigo} · {sa.item_descricao}</p>
        <p className="dica">Esta linha ainda não tem código do SA. Informe um código para marcar como confirmado sem ler o Mega.</p>
        <label>
          Código do SA
          <input inputMode="numeric" autoFocus value={codigo} onChange={(e) => setCodigo(e.target.value)} required />
        </label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario" disabled={ocupado}>Confirmar SA (teste)</button>
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Cancelar</button>
        </div>
      </form>
    </Janela>
  );
}

function JanelaEditar({ sa, soRs, aoFechar, aoGravar }: { sa: Sa; soRs: boolean; aoFechar: () => void; aoGravar: () => void }) {
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
    <Janela titulo={`${soRs ? "R$/kg do precificador" : "Pedido de SA"} · OP ${sa.op}`} aoFechar={aoFechar}>
      <form className="bloco-passo" style={{ gap: "var(--esp-4)" }} onSubmit={(e) => void salvar(e)}>
        {sa.exportado_renato_em && <p className="validacao alerta">Já exportado para o Renato em {data(sa.exportado_renato_em)}. A alteração avisa o Renato.</p>}
        <label>
          R$/kg do precificador{sa.origem !== "CARGA" && " (obrigatório)"}
          <input inputMode="decimal" value={f.rs_kg} onChange={(e) => setF({ ...f, rs_kg: e.target.value })} autoFocus required={sa.origem !== "CARGA"} />
          {sa.origem !== "CARGA" && <small className="dica">Sem o R$/kg o RJ não consegue informar a NF de transferência{sa.cop ? ` do COP ${sa.cop.numero}` : ""}.</small>}
          <small className="dica">{valor !== null ? `Valor precificador: R$ ${reais(valor)} por peça` : "Preenchido por quem cuida do custo; o sistema não calcula."}</small>
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
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Cancelar</button>
        </div>
      </form>
    </Janela>
  );
}

function JanelaNf({ ids, aoFechar, aoGravar }: { ids: number[]; aoFechar: () => void; aoGravar: (numero: string) => void }) {
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
    <Janela titulo={`NF de transferência · ${ids.length} linha(s) de corte em Itu`} aoFechar={aoFechar}>
      <form className="bloco-passo" style={{ gap: "var(--esp-4)" }} onSubmit={(e) => void salvar(e)}>
        <label>Nº da NF<input value={f.numero} onChange={(e) => setF({ ...f, numero: e.target.value })} autoFocus required /></label>
        {EMITENTES_LANCAMENTO.length === 1 ? (
          <p className="desc">Emitente: <strong>{EMITENTES_LANCAMENTO[0].nome}</strong></p>
        ) : (
          <fieldset className="formatos">
            <legend>Emitente</legend>
            {EMITENTES_LANCAMENTO.map((x) => (
              <label key={x.valor} className={f.emitente === x.valor ? "opcao marcada" : "opcao"}>
                <input type="radio" name="emitente" checked={f.emitente === x.valor} onChange={() => setF({ ...f, emitente: x.valor })} />
                {x.nome}
              </label>
            ))}
          </fieldset>
        )}
        <label>Data da NF (opcional)<input type="date" value={f.data} onChange={(e) => setF({ ...f, data: e.target.value })} /></label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario">Informar NF</button>
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Cancelar</button>
        </div>
      </form>
    </Janela>
  );
}
