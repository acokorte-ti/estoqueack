import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, data, ESTOQUE_NOME, kg, num, qs, validacaoDoErro, type Validacao } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { TIPO_LOTE, type Destinacao, type LoteDetalhe as TLote, type Movimento, type NoArvore, type Nota } from "../api/lote";
import Janela, { fecharJanela } from "../components/Janela";
import PainelValidacao, { confirmacoesValidas, JUSTIFICATIVA_MIN, podeGravar, type Confirmacoes } from "../components/PainelValidacao";

interface Pagina<T> { itens: T[]; total: number; pagina: number; por_pagina: number }
type Acao = null | "reserva" | "ajuste" | "origem" | { estornar: Movimento };

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
    () => api.get<Pagina<Movimento>>(`/lotes/${id}/movimentos${qs({ pagina: pagMov, por_pagina: 50 })}`).then(setMovs).catch(() => undefined),
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
      <p><Link to="/estoque">← Consulta de estoque</Link></p>
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
        {pode.solicitar && l.disponivel_kg > 0 && <Link className="primario" to="/solicitacoes/nova">Nova solicitação</Link>}
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
          {l.custo_kg !== null && <div><dt>R$/kg</dt><dd>{l.custo_kg.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</dd></div>}
          {l.origem && <div className="largo"><dt>Origem</dt><dd>{l.origem.lote} · {l.origem.conteiner ?? "—"} · {l.origem.bitola}</dd></div>}
        </dl>
        <div className="botoes" style={{ marginTop: "var(--esp-4)" }}>
          {pode.ajuste && <button className="secundario" onClick={() => setAcao("ajuste")}>Ajustar saldo</button>}
          {pode.reserva && <button className="secundario" onClick={() => setAcao("reserva")}>Adicionar reserva ou restrição</button>}
          {pode.origem && l.indicadores.origem_nao_identificada && <button className="secundario" onClick={() => setAcao("origem")}>Atribuir origem</button>}
        </div>
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
                    <td>{m.tipo_descricao}{m.estorno_de && <><br /><span className="etiqueta">estorno do mov. {m.estorno_de}</span></>}</td>
                    <td className={`num ${m.kg < 0 ? "negativo" : "positivo"}`}>{m.kg > 0 ? "+" : ""}{kg(m.kg)}</td>
                    <td className="num">{kg(m.saldo_apos_kg)}</td>
                    <td>{[m.op && `OP ${m.op}`, m.cop && `COP ${m.cop}`, m.sa && `SA ${m.sa}`].filter(Boolean).join(" · ") || "—"}</td>
                    <td className="desc">{m.documento ?? "—"}</td>
                    <td>{m.usuario ?? "—"}{m.justificativa && <><br /><span className="desc">{m.justificativa}</span></>}</td>
                    <td className="acoes">{pode.estorno && !m.estorno_de && m.tipo !== "SALDO_INICIAL" && <button className="link" onClick={() => setAcao({ estornar: m })}>Estornar</button>}</td>
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
    </>
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
      <label>Justificativa<textarea rows={3} value={just} onChange={(e) => { setJust(e.target.value); setV(null); }} />
        <small className="dica">{just.trim().length < JUSTIFICATIVA_MIN ? `Faltam ${JUSTIFICATIVA_MIN - just.trim().length} caractere(s).` : "Ok."}</small></label>
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
      <label>Justificativa<textarea autoFocus rows={3} value={just} onChange={(e) => setJust(e.target.value)} />
        <small className="dica">{just.trim().length < JUSTIFICATIVA_MIN ? `Faltam ${JUSTIFICATIVA_MIN - just.trim().length} caractere(s).` : "Ok."}</small></label>
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
    const r = await api.get<{ itens: typeof pais }>(`/lotes${qs({ busca: paiBusca.trim() || conteiner.trim(), liga: lote.liga, com_saldo: false, por_pagina: 20 })}`).catch(() => null);
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
