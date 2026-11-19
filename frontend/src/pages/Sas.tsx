import { useCallback, useEffect, useState, type FormEvent } from "react";
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
  /** contrato §7 (spec v3.19): o Mega já tem o SA, mas a linha não fechou porque falta o R$/kg do precificador */
  sa_no_mega?: boolean;
  /** contrato §7 (spec v3.19): o SA só fecha com o precificador (o histórico da carga fica como veio) */
  precificador_obrigatorio?: boolean;
}
interface CopResumo { id: number; numero: number; situacao: string; qtd_itens: number; peso_total_kg: number }
interface Lista { itens: Sa[]; total: number; cops_aguardando_sa: CopResumo[] }

const SITUACAO: Record<SituacaoSa, { nome: string; classe: string; dica: string }> = {
  PENDENTE: { nome: "Pendente", classe: "", dica: "o Fabiano confere e pede o SA" },
  PREPARADO: { nome: "Preparado", classe: "info", dica: "a Amanda cadastra no Mega e grava o código" },
  AGUARDANDO_MEGA: { nome: "Aguardando Mega", classe: "atencao", dica: "o sistema confere o código no Mega" },
  CONFIRMADO: { nome: "Confirmado", classe: "ok", dica: "SA fechado" },
};
const FILTROS: { chave: string; nome: string; situacao: SituacaoSa[] }[] = [
  { chave: "abertos", nome: "Em aberto", situacao: [] },
  { chave: "PENDENTE", nome: "Pendentes", situacao: ["PENDENTE"] },
  { chave: "PREPARADO", nome: "Preparados", situacao: ["PREPARADO"] },
  { chave: "AGUARDANDO_MEGA", nome: "Aguardando Mega", situacao: ["AGUARDANDO_MEGA"] },
  { chave: "CONFIRMADO", nome: "Confirmados", situacao: ["CONFIRMADO"] },
];

const temRs = (s: Sa) => (s.rs_kg ?? 0) > 0;
const obrigaRs = (s: Sa) => s.precificador_obrigatorio ?? s.origem !== "CARGA";
/** o código só conta como informado em "Aguardando Mega" ou depois; antes disso é a sugestão do sistema */
const informado = (s: Sa) => s.situacao === "AGUARDANDO_MEGA" || s.situacao === "CONFIRMADO";

function situacaoDe(s: Sa) {
  if (s.situacao === "AGUARDANDO_MEGA" && s.sa_no_mega) {
    return { nome: "Falta o precificador", classe: "atencao", dica: "o SA já está no Mega; grave o R$/kg para fechar" };
  }
  return SITUACAO[s.situacao] ?? { nome: s.situacao, classe: "", dica: "" };
}

function mensagemCodigo(r: Sa, codigo: number, op: number) {
  if (r.situacao === "CONFIRMADO") return `SA ${codigo} confirmado no Mega e fechado na OP ${op}.`;
  if (r.sa_no_mega) return `SA ${codigo} encontrado no Mega para a OP ${op}. Falta o R$/kg do precificador para fechar.`;
  return `Código ${codigo} gravado na OP ${op}. Aguardando a confirmação no Mega.`;
}

/** "SA fechado 1 de 3" com a barrinha (layout A): mostra por que a NF do COP está bloqueada sem abrir o COP. */
function Progresso({ rotulo, feito, total }: { rotulo: string; feito: number; total: number }) {
  const pct = total ? (feito / total) * 100 : 0;
  return (
    <div className="progresso">
      <span>{rotulo} {feito} de {total}</span>
      <span className="trilho" aria-hidden="true"><i className={feito < total ? "parcial" : undefined} style={{ width: `${pct}%` }} /></span>
    </div>
  );
}

/* ------------------------------------------------------------------ campos à mostra no cartão (spec v3.19 T14) */

/** "Código do SA": campo e botão à vista (Amanda/Fabiano). Sem pendência grava direto; com pendência abre a janela. */
function CampoCodigo({ sa, pode, aoGravar, aoConferir }: {
  sa: Sa; pode: boolean; aoGravar: (msg: string) => void; aoConferir: (codigo: number, v: Validacao) => void;
}) {
  const id = `sa-codigo-${sa.id}`;
  const [codigo, setCodigo] = useState(String(sa.sa_codigo ?? sa.sa_codigo_sugerido ?? ""));
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const feito = informado(sa);
  const sugestao = !feito && codigo.trim() !== "" && (Number(codigo) === sa.sa_codigo || Number(codigo) === sa.sa_codigo_sugerido);
  const outros = sa.outros_codigos.length ? ` Outros já usados nesta peça: ${sa.outros_codigos.join(", ")}.` : "";

  if (sa.situacao === "CONFIRMADO" || !pode) {
    return (
      <div className={`campo-sa${feito ? "" : " vazio"}`}>
        <span className="rotulo-campo">Código do SA {!feito && sa.sa_codigo && <span className="sugerido">sugerido</span>}</span>
        <span className="valor-fixo">{sa.sa_codigo ?? "—"}</span>
        <span className="dica">{sa.situacao === "CONFIRMADO" ? "conferido no Mega" : feito ? "o sistema confere no Mega"
          : "a Amanda grava depois de cadastrar no Mega"}</span>
      </div>
    );
  }

  async function gravar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    const n = Number(codigo);
    if (!Number.isInteger(n) || n <= 0) return setErro("Digite o código do SA (só números).");
    setOcupado(true);
    try {
      const v = await api.post<Validacao>(`/sas/${sa.id}/codigo/validar`, { sa_codigo: n, confirmacoes: {} });
      if (v.ocorrencias.length) {
        aoConferir(n, v);   // estou ciente / justificativa na janela
        return;
      }
      const r = await api.post<Sa>(`/sas/${sa.id}/codigo`, { sa_codigo: n, confirmacoes: {} });
      aoGravar(mensagemCodigo(r, n, sa.op));
    } catch (err) {
      const v = validacaoDoErro<Record<string, unknown>>(err);
      if (v) aoConferir(n, v);
      else setErro(err instanceof Error ? err.message : "Não foi possível gravar o código.");
    } finally {
      setOcupado(false);
    }
  }

  const mudou = !feito || Number(codigo) !== sa.sa_codigo;
  const dica = feito
    ? `Gravado; o sistema confere no Mega.${sa.sa_codigo_sugerido && sa.sa_codigo !== sa.sa_codigo_sugerido ? ` Sugerido: ${sa.sa_codigo_sugerido}.` : ""}`
    : sugestao ? "Código sugerido pelo sistema (último SA desta peça). Grave depois de conferir no Mega."
      : sa.sa_novo ? "SA novo: a Amanda cadastra no Mega e digita o código aqui."
        : "Digite o código depois do cadastro no Mega.";
  return (
    <form className={`campo-sa${feito ? "" : " vazio"}`} onSubmit={(e) => void gravar(e)}>
      <label className="rotulo-campo" htmlFor={id}>Código do SA {sugestao && <span className="sugerido">sugerido</span>}</label>
      <div className="campo-linha">
        <input id={id} inputMode="numeric" value={codigo} placeholder="código"
          onChange={(e) => { setCodigo(e.target.value); setErro(""); }} />
        <button className="secundario pequeno" disabled={ocupado || !codigo.trim() || !mudou}
          aria-label={`Gravar o código do SA da OP ${sa.op}`}>{ocupado ? "Gravando…" : "Gravar"}</button>
      </div>
      {erro ? <span className="erro-campo" role="alert">{erro}</span> : <span className="dica">{dica}{outros}</span>}
    </form>
  );
}

/** "R$/kg do precificador": obrigatório para o SA fechar (Eduardo, 2026-11-19); campo à vista com o valor por peça. */
function CampoPrecificador({ sa, pode, aoGravar }: { sa: Sa; pode: boolean; aoGravar: (msg: string) => void }) {
  const id = `sa-rs-${sa.id}`;
  const [valor, setValor] = useState(sa.rs_kg !== null ? String(sa.rs_kg).replace(".", ",") : "");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const obriga = obrigaRs(sa);
  const falta = obriga && !temRs(sa);
  const n = num(valor);
  const valido = n !== undefined && !Number.isNaN(n) && n > 0;
  const porPeca = valido && sa.quantidade ? ((n ?? 0) * sa.peso_kg) / sa.quantidade : null;
  const rotulo = <>R$/kg do precificador {obriga && <span className="obrigatorio">obrigatório</span>}</>;

  if (!pode) {
    return (
      <div className={`campo-sa${falta ? " vazio" : ""}`}>
        <span className="rotulo-campo">{rotulo}</span>
        <span className="valor-fixo">{temRs(sa) ? rsKg(sa.rs_kg ?? 0) : falta ? "falta" : "—"}</span>
        <span className="dica">{sa.valor_precificador ? `R$ ${reais(sa.valor_precificador)} por peça` : falta ? "sem ele o SA não fecha" : ""}</span>
      </div>
    );
  }

  async function gravar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    if (!valido) return setErro("Digite o R$/kg do precificador, maior que zero (ex.: 42,50).");
    setOcupado(true);
    try {
      const r = await api.patch<Sa>(`/sas/${sa.id}`, { rs_kg: n });
      aoGravar(r.situacao === "CONFIRMADO" && sa.situacao !== "CONFIRMADO"
        ? `Precificador gravado. SA ${r.sa_codigo ?? ""} da OP ${sa.op} fechado.`
        : `R$/kg do precificador gravado na OP ${sa.op}.`);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível gravar o R$/kg.");
    } finally {
      setOcupado(false);
    }
  }

  const mudou = valido && n !== sa.rs_kg;
  return (
    <form className={`campo-sa${falta ? " vazio" : ""}`} onSubmit={(e) => void gravar(e)}>
      <label className="rotulo-campo" htmlFor={id}>{rotulo}</label>
      <div className="campo-linha">
        <input id={id} inputMode="decimal" value={valor} placeholder="0,00"
          onChange={(e) => { setValor(e.target.value); setErro(""); }} />
        <button className="secundario pequeno" disabled={ocupado || !mudou}
          aria-label={`Gravar o R$/kg do precificador da OP ${sa.op}`}>{ocupado ? "Gravando…" : "Gravar"}</button>
      </div>
      {erro ? <span className="erro-campo" role="alert">{erro}</span> : (
        <span className="dica">
          {porPeca !== null ? `= R$ ${reais(porPeca)} por peça` : falta ? "Sem o precificador o SA não fecha e a NF do RJ não libera."
            : "Opcional no histórico da carga."}
          {sa.exportado_renato_em && ` Já exportado para o Renato em ${data(sa.exportado_renato_em)}: a alteração avisa o Renato.`}
        </span>
      )}
    </form>
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
  // Eduardo, 2026-11-19 (pendências item 17): a NF do corte em Itu (B2) é emitida no RJ e informada pelo Marcelo
  const informaNfB2 = usuario?.perfil === "OPERACAO_RJ" || usuario?.perfil === "ADMIN";
  const seleciona = altera || informaNfB2;

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

  /** campo do cartão gravou: mostra o resultado e relê a fila */
  const gravado = (msg: string) => {
    setErro("");
    setAviso(msg);
    void carregar();
  };

  const preparar = () =>
    acao(async () => {
      const r = await api.post<Sa[]>("/sas/preparar", { ids: sel });
      setSel([]);
      return `${r.length} pedido(s) marcado(s) como preparado(s): aguardando cadastro do SA no Mega pela Amanda.`;
    });

  /** sem ids: verifica todos os aguardando Mega; com ids: só os marcados */
  const verificar = (ids: number[]) =>
    acao(async () => {
      const r = await api.post<{ verificados: number; confirmados: number; falta_precificador?: number; erro?: string | null }>(
        "/sas/verificar", ids.length ? { ids } : {});
      if (r.erro) throw new Error(`Mega: ${r.erro}`);
      const falta = r.falta_precificador ? `, ${r.falta_precificador} esperando o precificador` : "";
      return `${r.verificados} SA(s) verificado(s) no Mega, ${r.confirmados} fechado(s)${falta}.`;
    });

  const msgTeste = (r: Sa, op: number) => r.situacao === "CONFIRMADO"
    ? `SA ${r.sa_codigo ?? ""} da OP ${op} confirmado em teste (sem ler o Mega).`
    : `SA ${r.sa_codigo ?? ""} da OP ${op} dado como achado no Mega (teste). Falta o R$/kg do precificador para fechar.`;

  const confirmarTeste = (s: Sa) => {
    if (!s.sa_codigo) return setTesteDe(s);
    void acao(async () => msgTeste(await api.post<Sa>(`/sas/${s.id}/confirmar-teste`, {}), s.op));
  };

  // janelas
  const [testeDe, setTesteDe] = useState<Sa | null>(null);
  const [codigoDe, setCodigoDe] = useState<{ sa: Sa; codigo?: number; validacao?: Validacao } | null>(null);
  const [dadosDe, setDadosDe] = useState<Sa | null>(null);
  const [nfAberta, setNfAberta] = useState(false);
  const selB2 = selecionados.filter((s) => s.origem === "CORTE_ITU");

  // spec v3.16 T14: um grupo por COP, na ordem em que aparecem; corte em Itu (B2) num grupo próprio
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

  /** Um cartão por OP: dados da peça à esquerda; à direita os dois campos que fecham o SA, sempre à mostra. */
  function cartao(s: Sa) {
    const sit = situacaoDe(s);
    const aberto = s.situacao !== "CONFIRMADO";
    const teste = confirmaTeste && aberto && !s.sa_no_mega;
    return (
      <article key={s.id} aria-label={`OP ${s.op}`}
        className={["cartao-sa", seleciona ? "" : "sem-marcar", s.atrasado ? "atrasado" : "", sel.includes(s.id) ? "selecionada" : ""].join(" ")}>
        {seleciona && (
          <div className="sa-marcar">{(altera || s.origem === "CORTE_ITU") &&
            <input type="checkbox" aria-label={`Selecionar OP ${s.op}`} checked={sel.includes(s.id)} onChange={() => alternar(s.id)} />}</div>
        )}
        <div className="sa-ident">
          <div className="sa-topo">
            <strong className="sa-op">OP {s.op}</strong>
            <span className="sa-cliente">{s.cliente ?? "—"}</span>
          </div>
          <p className="sa-item">Item {s.item_codigo ?? "—"}{s.item_descricao ? ` · ${s.item_descricao}` : ""}</p>
          <dl className="sa-fatos">
            <div><dt>Material</dt><dd>{s.material} {s.dimensao}</dd></div>
            <div><dt>Contêiner</dt><dd className="mono">{s.conteiner ?? "—"}</dd></div>
            <div><dt>Peso</dt><dd>{kg(s.peso_kg)} kg · {s.quantidade} pç</dd></div>
            <div><dt>Pedido</dt><dd>{s.pedido ?? "—"}</dd></div>
            <div><dt>Data</dt><dd>{data(s.data)}</dd></div>
            <div><dt>NF</dt><dd>{s.nf ? `${s.nf.numero} · ${nomeEmitente(s.nf.emitente)}` : "sem NF"}</dd></div>
          </dl>
          <div className="sa-situacao">
            <span className={`etiqueta ${sit.classe}`}>{sit.nome}</span>
            {sit.dica && <span>{sit.dica}</span>}
            {s.atrasado && <span className="etiqueta ruim">mais de 48 h</span>}
            {s.confirmacao_teste && <span className="etiqueta atencao" title="Pela ferramenta de teste, sem ler o Mega">confirmado em teste</span>}
          </div>
          {((altera && aberto) || teste) && (
            <div className="sa-acoes">
              {altera && aberto && (
                <button type="button" className="link" onClick={() => setDadosDe(s)}
                  aria-label={`Dados do SA da OP ${s.op}: descrição, NCM, ICMS, IPI e pedido`}><Icone nome="editar" />Dados do SA</button>
              )}
              {teste && (
                <button type="button" className="link botao-teste" disabled={ocupado} onClick={() => confirmarTeste(s)}
                  title="Faz de conta que o Mega achou o SA. Só existe na homologação.">
                  Confirmar SA (teste) <span className="etiqueta atencao">só homologação</span>
                </button>
              )}
            </div>
          )}
          {s.avisos?.map((a) => <p key={a.codigo} className="validacao alerta">{a.mensagem}</p>)}
        </div>
        <div className="sa-campos">
          <CampoCodigo key={`c-${s.sa_codigo ?? ""}-${s.situacao}`} sa={s} pode={informaCodigo} aoGravar={gravado}
            aoConferir={(codigo, validacao) => setCodigoDe({ sa: s, codigo, validacao })} />
          <CampoPrecificador key={`r-${s.rs_kg ?? ""}`} sa={s} pode={editaRs} aoGravar={gravado} />
        </div>
      </article>
    );
  }

  return (
    <>
      <header className="cabecalho cabecalho-acao">
        <div>
          <h1>Cadastro de SA</h1>
          <p>Pedidos de SA (semiacabado) agrupados por COP, e os do corte em Itu de material RJ. O Fabiano confere e pede o SA;
            a Amanda cadastra no Mega e grava o código; o precificador grava o R$/kg. <strong>O SA só fecha com o código
            conferido no Mega e o R$/kg do precificador</strong>, e o RJ só informa a NF de um COP com todos os SAs fechados.</p>
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
          <div className="grupos-sa">
            {grupos.map((g) => {
              const n = g.itens.length;
              const conf = g.itens.filter((s) => s.situacao === "CONFIRMADO").length;
              const comRs = g.itens.filter(temRs).length;
              const todosSel = g.itens.every((s) => sel.includes(s.id));
              return (
                <section key={g.chave} className="grupo-sa" aria-label={g.titulo}>
                  <div className="grupo-cab">
                    <span className="grupo-titulo">
                      {(altera || (informaNfB2 && g.chave === "corte-itu")) && (
                        <input type="checkbox" aria-label={`Selecionar ${g.titulo}`} checked={todosSel}
                          onChange={() => setSel(todosSel ? sel.filter((id) => !g.itens.some((s) => s.id === id)) : [...new Set([...sel, ...g.itens.map((s) => s.id)])])} />
                      )}
                      <Icone nome={g.cop ? "envio" : g.chave === "corte-itu" ? "corte" : "lista"} />
                      {g.titulo}
                    </span>
                    {g.cop && (conf === n && comRs === n
                      ? <span className="etiqueta ok">Pronto para a NF do RJ</span>
                      : g.cop.situacao === "FECHADO" && <span className="etiqueta bloqueio">NF do RJ bloqueada até todos os SAs fecharem</span>)}
                    <Progresso rotulo="SA fechado" feito={conf} total={n} />
                    {g.chave !== "outros" && <Progresso rotulo="Precificador" feito={comRs} total={n} />}
                    <span className="desc">{n} OP(s)</span>
                    {g.cop && (
                      <div className="empurra">
                        <Link className="secundario pequeno" to={`/cops/${g.cop.id}`}>Abrir COP<Icone nome="seta" /></Link>
                      </div>
                    )}
                  </div>
                  {g.itens.map(cartao)}
                </section>
              );
            })}
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

      {seleciona && sel.length > 0 && (
        <div className="barra-lote" role="region" aria-label="Ações para os pedidos selecionados">
          <span><b>{sel.length}</b> selecionado(s)</span>
          {altera && <button type="button" className="secundario pequeno" disabled={ocupado} onClick={() => void preparar()}>Marcar como preparado</button>}
          {informaNfB2 && <button type="button" className={altera ? "secundario pequeno" : "primario pequeno"} disabled={!selB2.length || ocupado} onClick={() => setNfAberta(true)}
            title="Só para linhas de corte em Itu (B2)">Informar NF (corte em Itu)</button>}
          {altera && <a className="secundario pequeno" href={exportarSelecionados} download><Icone nome="baixar" />Exportar</a>}
          {altera && <button type="button" className="primario pequeno" disabled={ocupado} onClick={() => void verificar(sel)}>
            <Icone nome="atualizar" />{ocupado ? "Consultando…" : "Verificar no Mega"}
          </button>}
          <button type="button" className="fantasma pequeno" onClick={() => setSel([])} aria-label="Desmarcar todos"><Icone nome="x" /></button>
        </div>
      )}

      {testeDe && (
        <JanelaTeste sa={testeDe} aoFechar={() => setTesteDe(null)}
          aoGravar={(r) => { const op = testeDe.op; setTesteDe(null); gravado(msgTeste(r, op)); }} />
      )}
      {codigoDe && (
        <JanelaCodigo sa={codigoDe.sa} codigoInicial={codigoDe.codigo} validacaoInicial={codigoDe.validacao}
          aoFechar={() => setCodigoDe(null)} aoGravar={(m) => { setCodigoDe(null); gravado(m); }} />
      )}
      {dadosDe && (
        <JanelaDados sa={dadosDe} aoFechar={() => setDadosDe(null)}
          aoGravar={() => { setDadosDe(null); gravado("Dados do SA atualizados."); }} />
      )}
      {nfAberta && (
        <JanelaNf ids={selB2.map((s) => s.id)} aoFechar={() => setNfAberta(false)}
          aoGravar={(n) => { setNfAberta(false); setSel([]); gravado(`NF ${n} informada em ${selB2.length} linha(s).`); }} />
      )}
    </>
  );
}

/* ------------------------------------------------------------------ janelas */

/** Código com pendência (troca do sugerido, inativo, não achado no Mega): estou ciente + justificativa antes de gravar */
function JanelaCodigo({ sa, codigoInicial, validacaoInicial, aoFechar, aoGravar }: {
  sa: Sa; codigoInicial?: number; validacaoInicial?: Validacao; aoFechar: () => void; aoGravar: (msg: string) => void;
}) {
  const [codigo, setCodigo] = useState(String(codigoInicial ?? sa.sa_codigo ?? sa.sa_codigo_sugerido ?? ""));
  const [validacao, setValidacao] = useState<Validacao | null>(validacaoInicial ?? null);
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
      const n = Number(codigo);
      const r = await api.post<Sa>(`/sas/${sa.id}/codigo`, { sa_codigo: n, confirmacoes: confirmacoesValidas(validacao.ocorrencias, conf) });
      aoGravar(mensagemCodigo(r, n, sa.op));
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
        <p className="dica">Esta linha ainda não tem código do SA. Informe um código para dar o SA como achado no Mega, sem ler o Mega.
          O SA fecha se o R$/kg do precificador já estiver gravado.</p>
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

/** "Dados do SA" (Estoque Itu/Admin): descrição, NCM, ICMS, IPI e pedido. O R$/kg fica no cartão. */
function JanelaDados({ sa, aoFechar, aoGravar }: { sa: Sa; aoFechar: () => void; aoGravar: () => void }) {
  const [f, setF] = useState({ sa_descricao: sa.sa_descricao ?? "", ncm: sa.ncm ?? "", icms: sa.icms ?? "", ipi: sa.ipi ?? "", pedido: sa.pedido ?? "" });
  const [erro, setErro] = useState("");

  async function salvar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    try {
      await api.patch(`/sas/${sa.id}`, { sa_descricao: f.sa_descricao || null, ncm: f.ncm || null, icms: f.icms || null,
        ipi: f.ipi || null, pedido: f.pedido || null });
      aoGravar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível salvar.");
    }
  }

  return (
    <Janela titulo={`Dados do SA · OP ${sa.op}`} aoFechar={aoFechar}>
      <form className="bloco-passo" style={{ gap: "var(--esp-4)" }} onSubmit={(e) => void salvar(e)}>
        {sa.exportado_renato_em && <p className="validacao alerta">Já exportado para o Renato em {data(sa.exportado_renato_em)}. A alteração avisa o Renato.</p>}
        <label>Descrição do SA<input value={f.sa_descricao} autoFocus onChange={(e) => setF({ ...f, sa_descricao: e.target.value })} /></label>
        <div className="grade-form">
          <label>NCM<input value={f.ncm} onChange={(e) => setF({ ...f, ncm: e.target.value })} /></label>
          <label>ICMS<input value={f.icms} onChange={(e) => setF({ ...f, icms: e.target.value })} /></label>
          <label>IPI<input value={f.ipi} onChange={(e) => setF({ ...f, ipi: e.target.value })} /></label>
          <label>Pedido<input value={f.pedido} onChange={(e) => setF({ ...f, pedido: e.target.value })} /></label>
        </div>
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
