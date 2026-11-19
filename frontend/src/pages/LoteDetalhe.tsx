import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, data, ESTOQUE_NOME, kg, num, qs, rsKg, validacaoDoErro, type Validacao } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { ORIGEM_ENTRADA, TIPO_LOTE, type Destinacao, type EntradaLote, type LoteDetalhe as TLote, type Movimento, type NoArvore, type Nota } from "../api/lote";
import Anexos from "../components/Anexos";
import Janela, { fecharJanela } from "../components/Janela";
import PainelValidacao, { confirmacoesValidas, JUSTIFICATIVA_MIN, podeGravar, type Confirmacoes } from "../components/PainelValidacao";

interface Pagina<T> { itens: T[]; total: number; pagina: number; por_pagina: number }
type Acao = null | "reserva" | "ajuste" | "origem" | "completar" | { estornar: Movimento };

/** T05 Detalhe do lote: cabeçalho, origem, movimentos, reservas/restrições, notas. Ações T17, T18 e atribuir origem. */
export default function LoteDetalhe() {
  const { id } = useParams();
  const { usuario } = useSessao();
  const p = usuario?.perfil;
  const pode = {
    reserva: p === "ESTOQUE" || p === "ANALISE" || p === "ADMIN",
    ajuste: p === "ESTOQUE" || p === "ADMIN",
    estorno: p === "ESTOQUE" || p === "OPERACAO_RJ" || p === "ADMIN",
    origem: p === "ESTOQUE" || p === "ADMIN",
    solicitar: p === "ESTOQUE" || p === "ADMIN",
  };
  const [l, setL] = useState<TLote | null>(null);
  const [arv, setArv] = useState<{ raiz: NoArvore; atual_id: number } | null>(null);
  const [movs, setMovs] = useState<Pagina<Movimento> | null>(null);
  const [pagMov, setPagMov] = useState(1);
  const [dest, setDest] = useState<Destinacao[]>([]);
  const [notas, setNotas] = useState<Nota[]>([]);
  const [novaNota, setNovaNota] = useState("");
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [acao, setAcao] = useState<Acao>(null);
  const [ent, setEnt] = useState<EntradaLote | null>(null);
  const [erroEnt, setErroEnt] = useState("");

  // "Entrada e documentos" (contrato §16.4): carga própria, para um erro aqui não esconder o resto do lote
  const carregarEntrada = useCallback(() => {
    setErroEnt("");
    return api.get<EntradaLote>(`/lotes/${id}/entrada`).then(setEnt)
      .catch((e: Error) => setErroEnt(`Não foi possível carregar a entrada e os documentos (${e.message}).`));
  }, [id]);
  useEffect(() => { void carregarEntrada(); }, [carregarEntrada]);

  const carregar = useCallback(async () => {
    setErro("");
    try {
      const [a, b, c, d] = await Promise.all([
        api.get<TLote>(`/lotes/${id}`), api.get<{ raiz: NoArvore; atual_id: number }>(`/lotes/${id}/arvore`),
        api.get<Destinacao[]>(`/lotes/${id}/destinacoes`), api.get<Nota[]>(`/lotes/${id}/notas`),
      ]);
      setL(a); setArv(b); setDest(c); setNotas(d);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível carregar o lote.");
    }
  }, [id]);
  const carregarMovs = useCallback(
    () => api.get<Pagina<Movimento>>(`/lotes/${id}/movimentos${qs({ pagina: pagMov, por_pagina: 50 })}`).then(setMovs)
      .catch((e: Error) => setErro(`Não foi possível carregar os movimentos (${e.message}).`)),
    [id, pagMov],
  );
  useEffect(() => { void carregar(); }, [carregar]);
  useEffect(() => { void carregarMovs(); }, [carregarMovs]);

  const feito = (msg: string) => { setAcao(null); setAviso(msg); void carregar(); void carregarMovs(); };

  async function salvarNota(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post(`/lotes/${id}/notas`, { texto: novaNota.trim() });
      setNovaNota("");
      setNotas(await api.get<Nota[]>(`/lotes/${id}/notas`));
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível salvar a nota.");
    }
  }

  async function encerrar(d: Destinacao) {
    try {
      await api.post(`/destinacoes/${d.id}/encerrar`);
      feito(`${d.tipo === "RESERVA" ? "Reserva" : "Restrição"} encerrada.`);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível encerrar.");
    }
  }

  if (!l) return erro ? <p className="erro" role="alert">{erro}</p> : <p className="carregando">Carregando…</p>;

  const paginasMov = movs ? Math.max(1, Math.ceil(movs.total / movs.por_pagina)) : 1;

  return (
    <>
      <p><Link to="/estoque">← Consultar estoque</Link></p>
      <header className="cabecalho cabecalho-acao">
        <div>
          <h1>{l.codigo} · {l.liga} {l.bitola}</h1>
          <p>
            <span className={`estoque-tag ${l.estoque}`}>{ESTOQUE_NOME[l.estoque]}</span>{" "}
            {l.tipo !== "ORIGINAL" && <span className="etiqueta">{TIPO_LOTE[l.tipo]}</span>}{" "}
            {l.status !== "ATIVO" && <span className="etiqueta">{l.status === "ESGOTADO" ? "Esgotado" : l.status}</span>}{" "}
            {l.indicadores.origem_nao_identificada && <span className="etiqueta atencao">origem não identificada</span>}
          </p>
        </div>
        <div className="botoes">
          {pode.solicitar && l.estoque === "RJ_EM_ITU" && l.saldo_kg > 0 && <Link className="secundario" to={`/corte-itu?lote_id=${l.id}`}>Usar em corte em Itu</Link>}
          {pode.solicitar && l.disponivel_kg > 0 && <Link className="primario" to="/solicitacoes/nova">Pedir corte de material</Link>}
        </div>
      </header>

      {erro && <p className="erro" role="alert">{erro}</p>}
      {aviso && <p className="validacao ok" role="status">{aviso}</p>}

      <section className="ficha">
        <div className="saldos">
          <div><span className="desc">Saldo</span><strong className="numero">{kg(l.saldo_kg)} kg</strong></div>
          <div><span className="desc">Reservado</span><strong className="numero">{kg(l.reservado_kg)} kg</strong></div>
          <div><span className="desc">Disponível</span><strong className="numero">{kg(l.disponivel_kg)} kg</strong></div>
        </div>
        <dl className="dados">
          <div><dt>Contêiner</dt><dd>{l.conteiner ?? "—"}</dd></div>
          <div><dt>Descrição</dt><dd>{l.descricao ?? "—"}</dd></div>
          <div><dt>Código Mega</dt><dd>{l.codigo_mega ?? "—"}</dd></div>
          <div><dt>Peso inicial</dt><dd>{l.peso_inicial_kg !== null ? `${kg(l.peso_inicial_kg)} kg` : "—"}</dd></div>
          <div><dt>Peças iniciais</dt><dd>{l.pecas_iniciais ?? "—"}</dd></div>
          <div><dt>NF de entrada</dt><dd>{l.documento_entrada ?? "—"}</dd></div>
          <div><dt>Data de entrada</dt><dd>{data(l.data_entrada)}</dd></div>
          {(ent?.custo_kg ?? l.custo_kg) !== null && <div><dt>R$/kg</dt><dd>{rsKg((ent?.custo_kg ?? l.custo_kg) as number)}</dd></div>}
          {l.origem && <div className="largo"><dt>Origem</dt><dd>{l.origem.lote} · {l.origem.conteiner ?? "—"} · {l.origem.bitola}</dd></div>}
        </dl>
        <div className="botoes" style={{ marginTop: "var(--esp-4)" }}>
          {pode.ajuste && <button className="secundario" onClick={() => setAcao("ajuste")}>Ajustar saldo</button>}
          {pode.reserva && <button className="secundario" onClick={() => setAcao("reserva")}>Adicionar reserva ou restrição</button>}
          {pode.origem && l.indicadores.origem_nao_identificada && <button className="secundario" onClick={() => setAcao("origem")}>Atribuir origem</button>}
        </div>
      </section>

      <section className="secao secao-entrada" aria-label="Entrada e documentos">
        <div className="linha-titulo">
          <h2>Entrada e documentos</h2>
          {ent?.pode_completar && <button className="secundario" onClick={() => { setAviso(""); setAcao("completar"); }}>Completar dados da entrada</button>}
        </div>
        {erroEnt && <p className="erro" role="alert">{erroEnt}</p>}
        {!ent ? (!erroEnt && <p className="carregando">Carregando…</p>) : <EntradaDoLote ent={ent} aoMudar={() => void carregarEntrada()} />}
      </section>

      {arv && (arv.raiz.filhos.length > 0 || arv.raiz.id !== l.id) && (
        <section className="secao">
          <h2>Árvore de origem</h2>
          <ul className="arvore"><NoLote no={arv.raiz} atual={arv.atual_id} /></ul>
        </section>
      )}

      {(dest.length > 0 || pode.reserva) && (
        <section className="secao">
          <h2>Reservas e restrições vigentes</h2>
          {!dest.length ? <p className="desc">Nenhuma.</p> : (
            <ul className="lista-simples">
              {dest.map((d) => (
                <li key={d.id}>
                  <span className={`etiqueta ${d.tipo === "RESERVA" ? "atencao" : "ruim"}`}>{d.tipo === "RESERVA" ? "Reserva" : "Restrição"}</span>{" "}
                  <strong>{d.descricao}</strong>{d.kg ? ` · ${kg(d.kg)} kg` : ""}{d.validade ? ` · até ${data(d.validade)}` : ""}
                  <span className="desc"> · {d.criado_por ?? "—"}, {data(d.criado_em)}</span>
                  {pode.reserva && <> <button className="link" onClick={() => void encerrar(d)}>Encerrar</button></>}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="secao">
        <h2>Movimentos {movs && <span className="desc">({movs.total})</span>}</h2>
        {!movs ? <p className="carregando">Carregando…</p> : !movs.itens.length ? <p className="desc">Nenhum movimento.</p> : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead><tr><th>Data</th><th>Movimento</th><th className="num">Kg</th><th className="num">Saldo depois</th><th>OP / COP / SA</th><th>Documento</th><th>Usuário / justificativa</th><th /></tr></thead>
              <tbody>
                {movs.itens.map((m) => (
                  <tr key={m.id}>
                    <td>{data(m.data)}</td>
                    <td>{m.tipo_descricao}{m.da_carga && <> <span className="etiqueta" title="Veio da carga das planilhas. Para corrigir, use Ajustar saldo.">da carga</span></>}{m.estorno_de && <><br /><span className="etiqueta">estorno do mov. {m.estorno_de}</span></>}</td>
                    <td className={`num ${m.kg < 0 ? "negativo" : "positivo"}`}>{m.kg > 0 ? "+" : ""}{kg(m.kg)}</td>
                    <td className="num">{kg(m.saldo_apos_kg)}</td>
                    <td>{[m.op && `OP ${m.op}`, m.cop && `COP ${m.cop}`, m.sa && `SA ${m.sa}`].filter(Boolean).join(" · ") || "—"}</td>
                    <td className="desc">{m.documento ?? "—"}</td>
                    <td>{m.usuario ?? "—"}{m.justificativa && <><br /><span className="desc">{m.justificativa}</span></>}</td>
                    <td className="acoes">{pode.estorno && (m.estornavel ?? (!m.estorno_de && m.tipo !== "SALDO_INICIAL")) && <button className="link" onClick={() => setAcao({ estornar: m })}>Estornar</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {movs && paginasMov > 1 && (
          <div className="paginacao">
            <button className="secundario" disabled={pagMov <= 1} onClick={() => setPagMov(pagMov - 1)}>Anteriores</button>
            <span>Página {pagMov} de {paginasMov}</span>
            <button className="secundario" disabled={pagMov >= paginasMov} onClick={() => setPagMov(pagMov + 1)}>Seguintes</button>
          </div>
        )}
      </section>

      <section className="secao">
        <h2>Notas</h2>
        {notas.length > 0 && (
          <ul className="lista-simples">
            {notas.map((n) => <li key={n.id}><span>{n.texto}</span> <span className="desc">· {n.usuario ?? "—"}, {data(n.criado_em)}</span></li>)}
          </ul>
        )}
        <form className="linha-form" onSubmit={(e) => void salvarNota(e)}>
          <label style={{ flex: "1 1 24rem" }}>Nova nota<input value={novaNota} onChange={(e) => setNovaNota(e.target.value)} placeholder="Ex.: separar para a GERDAU; barra com trinca na ponta" /></label>
          <button className="secundario" disabled={!novaNota.trim()}>Adicionar nota</button>
        </form>
      </section>

      {acao === "reserva" && <JanelaReserva lote={l} aoFechar={() => setAcao(null)} aoGravar={feito} />}
      {acao === "ajuste" && <JanelaAjuste lote={l} aoFechar={() => setAcao(null)} aoGravar={feito} />}
      {acao === "origem" && <JanelaOrigem lote={l} aoFechar={() => setAcao(null)} aoGravar={feito} />}
      {acao && typeof acao === "object" && <JanelaEstorno mov={acao.estornar} aoFechar={() => setAcao(null)} aoGravar={feito} />}
      {acao === "completar" && ent && (
        <JanelaCompletar lote={l} ent={ent} aoFechar={() => setAcao(null)}
          aoGravar={(r) => { setAcao(null); setEnt(r); setAviso(["Dados da entrada atualizados.", ...(r.avisos ?? [])].join(" ")); void carregar(); }} />
      )}
    </>
  );
}

const ou = (v: string | number | null | undefined) => (v === null || v === undefined || v === "" ? "—" : String(v));
const kgOu = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${kg(v)} kg`);
/** NCM com pontos (7228.30.00) quando vier só com os 8 dígitos. */
const ncmTexto = (v: string | null | undefined) => (v && /^\d{8}$/.test(v) ? `${v.slice(0, 4)}.${v.slice(4, 6)}.${v.slice(6)}` : ou(v));

/** T05 seção 6: dados da entrada (T06/T15/completados) ou da carga, item da NF, R$/kg e documentos anexos. */
function EntradaDoLote({ ent, aoMudar }: { ent: EntradaLote; aoMudar: () => void }) {
  const e = ent.entrada;
  const it = ent.item;
  return (
    <div className="ficha">
      {ent.da_origem && (
        <p className="desc" style={{ marginBottom: "var(--esp-3)" }}>
          <span className="etiqueta info">da origem {ent.da_origem}</span> Dados e documentos do lote de origem.
          {!ent.pode_completar && ` Para completar, abra o lote de origem ${ent.da_origem}.`}
        </p>
      )}
      {ent.origem && <p className="desc" style={{ marginBottom: "var(--esp-3)" }}>{ORIGEM_ENTRADA[ent.origem] ?? ent.origem}</p>}
      {e ? (
        <dl className="dados">
          <div><dt>NF</dt><dd>{ou(e.numero)}{e.serie ? ` · série ${e.serie}` : ""}</dd></div>
          <div><dt>Emissão</dt><dd>{data(e.data_emissao)}</dd></div>
          <div><dt>Data de entrada</dt><dd>{data(e.data_entrada)}</dd></div>
          <div><dt>Emitente / fornecedor</dt><dd>{ou(e.fornecedor)}</dd></div>
          <div><dt>CNPJ</dt><dd>{ou(e.cnpj)}</dd></div>
          <div><dt>Contêiner</dt><dd>{ou(e.conteiner)}</dd></div>
          <div><dt>Packing list</dt><dd>{ou(e.packing_list)}</dd></div>
          <div><dt>DI/DUIMP</dt><dd>{ou(e.di_duimp)}</dd></div>
          {e.chave_nfe && <div className="largo"><dt>Chave de acesso da NF-e</dt><dd className="num">{e.chave_nfe}</dd></div>}
          {e.observacao && <div className="largo"><dt>Observação da entrada</dt><dd>{e.observacao}</dd></div>}
        </dl>
      ) : ent.carga ? (
        <dl className="dados">
          <div><dt>Documento</dt><dd>{ou(ent.carga.documento)}</dd></div>
          <div><dt>Data de entrada</dt><dd>{data(ent.carga.data_entrada)}</dd></div>
          <div><dt>Peças</dt><dd>{ou(ent.carga.pecas)}</dd></div>
          <div><dt>Peso de entrada</dt><dd>{kgOu(ent.carga.peso_kg)}</dd></div>
          <div className="largo"><dt>Planilha</dt><dd>{[ent.carga.arquivo, ent.carga.aba, ent.carga.linha && `linha ${ent.carga.linha}`].filter(Boolean).join(" · ") || "—"}</dd></div>
        </dl>
      ) : <p className="desc">Sem dados de entrada registrados.</p>}

      {it && (
        <>
          <h3>Item da NF</h3>
          <dl className="dados">
            <div className="largo"><dt>Descrição como na NF</dt><dd>{ou(it.descricao_nf)}</dd></div>
            <div><dt>NCM</dt><dd>{ncmTexto(it.ncm)}</dd></div>
            <div><dt>Peças</dt><dd>{ou(it.pecas)}</dd></div>
            <div><dt>Peso líquido</dt><dd>{kgOu(it.peso_kg)}</dd></div>
            <div><dt>Peso bruto</dt><dd>{kgOu(it.peso_bruto_kg)}</dd></div>
            <div><dt>Comprimento</dt><dd>{ou(it.comprimento)}</dd></div>
            {it.observacao && <div className="largo"><dt>Observação do item</dt><dd>{it.observacao}</dd></div>}
          </dl>
        </>
      )}
      <dl className="dados" style={{ marginTop: "var(--esp-3)" }}>
        <div><dt>R$/kg (precificador)</dt><dd>{ent.custo_kg !== null ? rsKg(ent.custo_kg) : <span className="desc">não informado</span>}</dd></div>
      </dl>

      <h3>Documentos anexos</h3>
      <Anexos anexos={ent.anexos} enviarPara={`/lotes/${ent.lote_id}/anexos`} aoMudar={aoMudar} />
    </div>
  );
}

/** "Completar dados da entrada" (P42(d)): só o que não mexe no saldo; manda só os campos que mudaram. */
function JanelaCompletar({ lote, ent, aoFechar, aoGravar }: { lote: TLote; ent: EntradaLote; aoFechar: () => void; aoGravar: (r: EntradaLote) => void }) {
  const e = ent.entrada;
  const it = ent.item;
  const n = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v).replace(".", ","));
  const inicial = {
    numero: e?.numero ?? "", serie: e?.serie ?? "", data_emissao: e?.data_emissao ?? "", data_entrada: e?.data_entrada ?? "",
    fornecedor: e?.fornecedor ?? "", cnpj: e?.cnpj ?? "", chave_nfe: e?.chave_nfe ?? "", packing_list: e?.packing_list ?? "",
    di_duimp: e?.di_duimp ?? "", observacao: e?.observacao ?? "", descricao_nf: it?.descricao_nf ?? "", ncm: it?.ncm ?? "",
    peso_bruto_kg: n(it?.peso_bruto_kg), custo_kg: n(it?.custo_kg ?? ent.custo_kg), observacao_item: it?.observacao ?? "",
  };
  type Campo = keyof typeof inicial;
  const [f, setF] = useState(inicial);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const numericos: Campo[] = ["peso_bruto_kg", "custo_kg"];
  const mudados = (Object.keys(inicial) as Campo[]).filter((k) => f[k].trim() !== inicial[k].trim());
  const campo = (k: Campo, rotulo: string, extra: Record<string, string> = {}) => (
    <label>{rotulo}<input value={f[k]} onChange={(ev) => setF({ ...f, [k]: ev.target.value })} {...extra} /></label>
  );

  async function ok(ev: FormEvent) {
    ev.preventDefault();
    const corpo: Record<string, string | number | null> = {};
    for (const k of mudados) {
      const v = f[k].trim();
      corpo[k] = !v ? null : numericos.includes(k) ? (num(v) ?? null) : v;
    }
    setErro(""); setOcupado(true);
    try { aoGravar(await api.patch<EntradaLote>(`/lotes/${lote.id}/entrada`, corpo)); }
    catch (err) { setErro(err instanceof Error ? err.message : "Não foi possível salvar."); }
    finally { setOcupado(false); }
  }

  return (
    <Janela titulo={`Completar dados da entrada · ${lote.codigo}`} aoFechar={aoFechar} larga>
      <form onSubmit={(ev) => void ok(ev)} className="bloco-passo" style={{ gap: "var(--esp-4)" }}>
        <p className="desc">Só o que não mexe no saldo. Contêiner, liga, bitola, peso líquido, peças e comprimento se corrigem por estorno. A mudança fica na auditoria.</p>
        <div className="grade-form">
          {campo("numero", "Nº da NF")}
          {campo("serie", "Série")}
          {campo("data_emissao", "Data de emissão", { type: "date" })}
          {campo("data_entrada", "Data de entrada", { type: "date" })}
          {campo("fornecedor", "Emitente / fornecedor")}
          {campo("cnpj", "CNPJ", { inputMode: "numeric" })}
          {campo("packing_list", "Nº do packing list")}
          {campo("di_duimp", "Nº da DI/DUIMP")}
          {campo("ncm", "NCM", { inputMode: "numeric", placeholder: "7228.30.00" })}
          {campo("peso_bruto_kg", "Peso bruto (kg)", { inputMode: "decimal" })}
          {campo("custo_kg", "R$/kg (precificador)", { inputMode: "decimal" })}
        </div>
        {campo("chave_nfe", "Chave de acesso da NF-e", { inputMode: "numeric", placeholder: "44 dígitos" })}
        {campo("descricao_nf", "Descrição como na NF")}
        <label>Observação da entrada<textarea rows={2} value={f.observacao} onChange={(ev) => setF({ ...f, observacao: ev.target.value })} /></label>
        {campo("observacao_item", "Observação do item")}
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario" disabled={!mudados.length || ocupado}>{ocupado ? "Salvando…" : "Salvar dados"}</button>
          <button type="button" className="secundario" onClick={(ev) => fecharJanela(ev.currentTarget)}>Voltar</button>
        </div>
      </form>
    </Janela>
  );
}

function NoLote({ no, atual }: { no: NoArvore; atual: number }) {
  return (
    <li>
      <span className={no.id === atual ? "no atual" : "no"}>
        {no.id === atual ? <strong>{no.codigo}</strong> : <Link to={`/estoque/${no.id}`}>{no.codigo}</Link>}
        {" "}{TIPO_LOTE[no.tipo] ?? no.tipo} · {no.bitola} · {no.conteiner ?? "—"} · <strong>{kg(no.saldo_kg)} kg</strong>
      </span>
      {no.filhos.length > 0 && <ul>{no.filhos.map((f) => <NoLote key={f.id} no={f} atual={atual} />)}</ul>}
    </li>
  );
}

/* ------------------------------------------------------------------ janelas */

function JanelaReserva({ lote, aoFechar, aoGravar }: { lote: TLote; aoFechar: () => void; aoGravar: (m: string) => void }) {
  const [f, setF] = useState({ tipo: "RESERVA" as "RESERVA" | "RESTRICAO", descricao: "", kg: "", validade: "" });
  const [erro, setErro] = useState("");
  async function ok(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post(`/lotes/${lote.id}/destinacoes`, { tipo: f.tipo, descricao: f.descricao.trim(), kg: f.tipo === "RESERVA" ? num(f.kg) ?? null : null, validade: f.validade || null });
      aoGravar(`${f.tipo === "RESERVA" ? "Reserva" : "Restrição"} registrada. Quem usar este lote verá o "estou ciente".`);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível salvar.");
    }
  }
  return (
    <Janela titulo={`Reserva ou restrição · ${lote.codigo}`} aoFechar={aoFechar}>
      <form onSubmit={(e) => void ok(e)} className="bloco-passo" style={{ gap: "var(--esp-4)" }}>
        <fieldset className="formatos">
          <legend>Tipo</legend>
          <label className={f.tipo === "RESERVA" ? "opcao marcada" : "opcao"}><input type="radio" name="tipo-dest" checked={f.tipo === "RESERVA"} onChange={() => setF({ ...f, tipo: "RESERVA" })} />Reserva (separa kg)</label>
          <label className={f.tipo === "RESTRICAO" ? "opcao marcada" : "opcao"}><input type="radio" name="tipo-dest" checked={f.tipo === "RESTRICAO"} onChange={() => setF({ ...f, tipo: "RESTRICAO" })} />Restrição de uso</label>
        </fieldset>
        <label>Descrição<input autoFocus value={f.descricao} onChange={(e) => setF({ ...f, descricao: e.target.value })} placeholder={f.tipo === "RESERVA" ? "Reservado CPR" : "Não usar para guilhotinas"} required minLength={3} /></label>
        <div className="grade-form">
          {f.tipo === "RESERVA" && <label>Kg reservados<input inputMode="decimal" value={f.kg} onChange={(e) => setF({ ...f, kg: e.target.value })} placeholder={`até ${kg(lote.disponivel_kg)}`} /></label>}
          <label>Validade (opcional)<input type="date" value={f.validade} onChange={(e) => setF({ ...f, validade: e.target.value })} /></label>
        </div>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario" disabled={f.descricao.trim().length < 3}>Salvar</button>
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
        </div>
      </form>
    </Janela>
  );
}

function JanelaAjuste({ lote, aoFechar, aoGravar }: { lote: TLote; aoFechar: () => void; aoGravar: (m: string) => void }) {
  const [contado, setContado] = useState("");
  const [just, setJust] = useState("");
  const [v, setV] = useState<Validacao<{ frase?: string }> | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [erro, setErro] = useState("");
  const dif = num(contado) !== undefined ? (num(contado) as number) - lote.saldo_kg : null;
  const corpo = (c: Confirmacoes) => ({ saldo_contado_kg: num(contado), justificativa: just.trim(), confirmacoes: c });
  async function conferir() {
    setErro("");
    try { setV(await api.post<Validacao<{ frase?: string }>>(`/lotes/${lote.id}/ajuste/validar`, corpo({}))); }
    catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível conferir."); }
  }
  async function gravar() {
    if (!v) return;
    try {
      await api.post(`/lotes/${lote.id}/ajuste`, corpo(confirmacoesValidas(v.ocorrencias, conf)));
      aoGravar(`Saldo ajustado para ${kg(num(contado) as number)} kg.`);
    } catch (e) {
      const x = validacaoDoErro<{ frase?: string }>(e);
      if (x) setV(x); else setErro(e instanceof Error ? e.message : "Não foi possível ajustar.");
    }
  }
  return (
    <Janela titulo={`Ajustar saldo · ${lote.codigo}`} aoFechar={aoFechar}>
      <p className="desc">Saldo no sistema: <strong>{kg(lote.saldo_kg)} kg</strong>. O ajuste vira um movimento de inventário com a sua justificativa e aparece no relatório de exceções.</p>
      <label>Saldo contado (kg)<input inputMode="decimal" className="campo-grande" autoFocus value={contado} onChange={(e) => { setContado(e.target.value); setV(null); }} /></label>
      {dif !== null && <p className={dif === 0 ? "desc" : "resultado-frase"}>Diferença: {dif > 0 ? "+" : ""}{kg(dif)} kg</p>}
      <label>Justificativa<textarea rows={3} value={just} onChange={(e) => { setJust(e.target.value); setV(null); }} /></label>
      {v?.resultado?.frase && <p className="frase-resultado">{v.resultado.frase}</p>}
      {v && <PainelValidacao ocorrencias={v.ocorrencias} confirmacoes={conf} aoMudar={setConf} semOcorrencias="Pode ajustar." />}
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        {!v ? <button className="primario" disabled={num(contado) === undefined || just.trim().length < JUSTIFICATIVA_MIN || dif === 0} onClick={() => void conferir()}>Conferir ajuste</button>
          : <button className="primario" disabled={!podeGravar(v.ocorrencias, conf)} onClick={() => void gravar()}>Ajustar saldo</button>}
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}

function JanelaEstorno({ mov, aoFechar, aoGravar }: { mov: Movimento; aoFechar: () => void; aoGravar: (m: string) => void }) {
  const [just, setJust] = useState("");
  const [erro, setErro] = useState("");
  async function ok() {
    try {
      await api.post(`/movimentos/${mov.id}/estorno`, { justificativa: just.trim() });
      aoGravar(`Movimento estornado: ${mov.tipo_descricao} (${kg(mov.kg)} kg).`);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível estornar.");
    }
  }
  return (
    <Janela titulo="Estornar movimento" aoFechar={aoFechar}>
      <p><strong>{mov.tipo_descricao}</strong> de {data(mov.data)}: {mov.kg > 0 ? "+" : ""}{kg(mov.kg)} kg{mov.op ? ` · OP ${mov.op}` : ""}.</p>
      <p className="desc">Nada é apagado: o sistema cria o movimento inverso, ligado a este. Corte do RJ só pode ser estornado antes de entrar em COP fechado.</p>
      <label>Justificativa<textarea autoFocus rows={3} value={just} onChange={(e) => setJust(e.target.value)} /></label>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="perigo" disabled={just.trim().length < JUSTIFICATIVA_MIN} onClick={() => void ok()}>Estornar</button>
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}

function JanelaOrigem({ lote, aoFechar, aoGravar }: { lote: TLote; aoFechar: () => void; aoGravar: (m: string) => void }) {
  const [conteiner, setConteiner] = useState("");
  const [opcoes, setOpcoes] = useState<{ id: number; codigo: string }[]>([]);
  const [paiBusca, setPaiBusca] = useState("");
  const [pais, setPais] = useState<{ id: number; codigo: string; liga: string; bitola: string; conteiner: string | null }[]>([]);
  const [pai, setPai] = useState<number | null>(null);
  const [just, setJust] = useState("");
  const [erro, setErro] = useState("");
  useEffect(() => {
    const t = window.setTimeout(() => {
      if (conteiner.trim().length < 2) return setOpcoes([]);
      api.get<{ id: number; codigo: string }[]>(`/conteineres?busca=${encodeURIComponent(conteiner.trim())}`).then(setOpcoes).catch(() => setOpcoes([]));
    }, 250);
    return () => window.clearTimeout(t);
  }, [conteiner]);
  async function buscarPai() {
    const r = await api.get<{ itens: typeof pais }>(`/lotes${qs({ busca: paiBusca.trim() || conteiner.trim(), liga: lote.liga, com_saldo: false, por_pagina: 20 })}`).catch((e: Error) => { setErro(`Não foi possível buscar os lotes (${e.message}).`); return null; });
    setPais((r?.itens ?? []).filter((x) => x.id !== lote.id));
  }
  async function ok(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post(`/lotes/${lote.id}/atribuir-origem`, { conteiner: conteiner.trim().toUpperCase(), lote_pai_id: pai, justificativa: just.trim() });
      aoGravar(`Origem atribuída: contêiner ${conteiner.trim().toUpperCase()}.`);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível atribuir a origem.");
    }
  }
  return (
    <Janela titulo={`Atribuir origem · ${lote.codigo}`} aoFechar={aoFechar} larga>
      <form onSubmit={(e) => void ok(e)} className="bloco-passo" style={{ gap: "var(--esp-4)" }}>
        <p className="desc">Para material que entrou na carga sem contêiner conhecido. Use depois do inventário físico.</p>
        <label>Contêiner<input autoFocus list="conteineres-origem" value={conteiner} onChange={(e) => setConteiner(e.target.value.toUpperCase())} required placeholder="CH25K" />
          <datalist id="conteineres-origem">{opcoes.map((o) => <option key={o.id} value={o.codigo} />)}</datalist></label>
        <details className="avancado">
          <summary>Lote de origem (opcional)</summary>
          <div className="linha-form" style={{ marginBottom: 0 }}>
            <label>Buscar lote pai<input value={paiBusca} onChange={(e) => setPaiBusca(e.target.value)} placeholder="código, contêiner ou bitola" /></label>
            <button type="button" className="secundario" onClick={() => void buscarPai()}>Buscar</button>
          </div>
          {pais.length > 0 && (
            <ul className="escolhas">
              {pais.map((x) => (
                <li key={x.id}><label className={pai === x.id ? "escolha-lote marcada" : "escolha-lote"}>
                  <input type="radio" name="pai" checked={pai === x.id} onChange={() => setPai(x.id)} />
                  <span><span className="titulo">{x.codigo} · {x.liga} {x.bitola}</span><span className="linha2">{x.conteiner ?? "—"}</span></span><span />
                </label></li>
              ))}
            </ul>
          )}
        </details>
        <label>Justificativa<textarea rows={3} value={just} onChange={(e) => setJust(e.target.value)} placeholder="Ex.: inventário 10/11, etiqueta da barra mostra CH25K" /></label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario" disabled={conteiner.trim().length < 2 || just.trim().length < JUSTIFICATIVA_MIN}>Atribuir origem</button>
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
        </div>
      </form>
    </Janela>
  );
}
