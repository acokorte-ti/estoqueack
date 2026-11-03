import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, data, ESTOQUE_NOME, kg, qs, validacaoDoErro, type Ocorrencia, type Validacao } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { MODO_NOME, material, numerosCop, type SolicDetalhe } from "../api/solicitacao";
import { EtiquetaAtraso, EtiquetaSituacao } from "../components/Etiquetas";
import Janela, { fecharJanela } from "../components/Janela";
import PainelValidacao, { confirmacoesValidas, JUSTIFICATIVA_MIN, podeGravar, type Confirmacoes } from "../components/PainelValidacao";

type Acao = "cancelar" | "enviar" | "trocar-lote" | "encerrar" | "trocar-op" | null;

/** T08: detalhe de uma solicitação, com as ações permitidas na situação atual. */
export default function SolicitacaoDetalhe() {
  const { id } = useParams();
  const nav = useNavigate();
  const { usuario } = useSessao();
  const altera = usuario?.perfil === "ESTOQUE" || usuario?.perfil === "ADMIN";
  const [s, setS] = useState<SolicDetalhe | null>(null);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState<string[]>([]);
  const [acao, setAcao] = useState<Acao>(null);

  const carregar = useCallback(
    () => api.get<SolicDetalhe>(`/solicitacoes/${id}`).then(setS).catch((e: Error) => setErro(e.message)),
    [id],
  );
  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function duplicar() {
    setErro("");
    try {
      const r = await api.post<{ id: number } | { solicitacoes: { id: number }[] }>(`/solicitacoes/${id}/duplicar`);
      const novo = "id" in r ? r.id : r.solicitacoes[0]?.id;
      if (novo) nav(`/solicitacoes/${novo}`);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível duplicar.");
    }
  }

  const feito = (msg: string[] = []) => {
    setAcao(null);
    setAviso(msg);
    void carregar();
  };

  if (!s) return erro ? <p className="erro" role="alert">{erro}</p> : <p className="carregando">Carregando…</p>;

  const semCorte = s.pecas_cortadas === 0;
  const pode = {
    enviar: altera && s.situacao === "RASCUNHO",
    cancelar: altera && semCorte && ["RASCUNHO", "ENVIADA", "MATERIAL_INSUFICIENTE"].includes(s.situacao),
    trocarLote: altera && s.situacao === "MATERIAL_INSUFICIENTE",
    encerrar: altera && s.situacao === "CORTADA_PARCIAL",
    trocarOp: altera && !["CANCELADA", "RASCUNHO"].includes(s.situacao),
    duplicar: altera,
  };
  const m = s.medida_acabada;
  const b = s.bruto;
  const n = (v: number | null) => (v === null ? "?" : v.toLocaleString("pt-BR"));
  const dim = (x: { espessura: number | null; largura: number | null; diametro: number | null; comprimento: number | null } | null) =>
    !x ? "—" : x.diametro ? `Ø ${n(x.diametro)} × ${n(x.comprimento)}` : `${n(x.espessura)} × ${n(x.largura)} × ${n(x.comprimento)}`;

  return (
    <>
      <p><Link to="/solicitacoes">← Solicitações</Link></p>
      <header className="cabecalho cabecalho-acao">
        <div>
          <h1>{s.numero} · OP {s.op}</h1>
          <p><EtiquetaSituacao s={s.situacao} /> {s.atraso && <EtiquetaAtraso a={s.atraso} dias={s.dias_em_aberto} />} {s.encerrada_saldo_pendente && <span className="etiqueta">encerrada com saldo pendente</span>}</p>
        </div>
        {pode.enviar && <button className="primario" onClick={() => setAcao("enviar")}>Enviar ao RJ</button>}
        {pode.trocarLote && <button className="primario" onClick={() => setAcao("trocar-lote")}>Trocar lote</button>}
        {pode.encerrar && <button className="primario" onClick={() => setAcao("encerrar")}>Encerrar com saldo pendente</button>}
      </header>

      {erro && <p className="erro" role="alert">{erro}</p>}
      {aviso.map((a) => <p key={a} className="validacao alerta">{a}</p>)}
      {s.situacao === "MATERIAL_INSUFICIENTE" && s.motivo && <p className="validacao erro">RJ informou material insuficiente: {s.motivo}</p>}
      {s.situacao === "CANCELADA" && s.motivo && <p className="validacao alerta">Cancelada: {s.motivo}</p>}

      <section className="ficha">
        <dl className="dados">
          <div className="largo"><dt>Item</dt><dd>{s.item_codigo ?? "—"} · {s.item_descricao ?? "—"}{!s.op_confirmada_mega && <span className="etiqueta atencao"> não confirmado no Mega</span>}</dd></div>
          <div><dt>Cliente</dt><dd>{s.cliente ?? "—"}</dd></div>
          <div><dt>Pedido</dt><dd>{s.pedido ?? "—"}</dd></div>
          <div><dt>Prazo</dt><dd>{data(s.prazo)}</dd></div>
          <div><dt>Enviada em</dt><dd>{data(s.enviada_em)}</dd></div>
          <div className="largo"><dt>Lote</dt><dd>{material(s.lote)} · {s.lote.conteiner ?? "—"} · {s.lote.codigo} <span className={`estoque-tag ${s.lote.estoque}`}>{ESTOQUE_NOME[s.lote.estoque] ?? s.lote.estoque}</span></dd></div>
          <div><dt>Modo</dt><dd>{MODO_NOME[s.modo]}</dd></div>
          <div><dt>Peças</dt><dd>{s.pecas_cortadas} cortada(s) de {s.quantidade}</dd></div>
          <div><dt>Peça acabada (mm)</dt><dd>{dim(m)}</dd></div>
          <div><dt>Bruto de corte (mm)</dt><dd>{dim(b)}</dd></div>
          <div><dt>Peso previsto</dt><dd>{s.peso_previsto_kg !== null ? `${kg(s.peso_previsto_kg)} kg` : "—"}</dd></div>
          <div><dt>Peso real</dt><dd>{s.peso_real_kg !== null ? `${kg(s.peso_real_kg)} kg` : "—"}</dd></div>
          <div><dt>Reservado no lote</dt><dd>{s.reserva_kg ? `${kg(s.reserva_kg)} kg` : "—"}</dd></div>
          <div><dt>Sobremetal</dt><dd>{s.sobremetal_pct !== null ? `${s.sobremetal_pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} %` : "—"}</dd></div>
          <div className="largo"><dt>Instrução para o RJ</dt><dd>{s.instrucao ?? "—"}{s.instrucao_processo && ` · ${s.instrucao_processo}`}</dd></div>
          {s.observacao && <div className="largo"><dt>Observação</dt><dd>{s.observacao}</dd></div>}
          <div><dt>COP</dt><dd>{numerosCop(s.cops) || "—"}</dd></div>
          <div><dt>SA</dt><dd>{s.sas.length ? s.sas.map((x) => x.sa_codigo ?? "a informar").join(", ") : "—"}</dd></div>
        </dl>
        {s.confirmacoes && Object.keys(s.confirmacoes).length > 0 && (
          <details className="avancado">
            <summary>Justificativas registradas ({Object.keys(s.confirmacoes).length})</summary>
            <ul>{Object.entries(s.confirmacoes).map(([k, v]) => <li key={k}><strong>{k}</strong>: {v}</li>)}</ul>
          </details>
        )}
      </section>

      <h2 style={{ margin: "var(--esp-5) 0 var(--esp-3)" }}>Cortes</h2>
      {!s.cortes.length ? (
        <p className="desc">Nenhum corte registrado ainda.</p>
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead><tr><th>Data</th><th>Lote</th><th className="num">Peças</th><th className="num">Peso real</th><th className="num">Barra</th><th>COP</th><th /></tr></thead>
            <tbody>
              {s.cortes.map((c) => (
                <tr key={c.id} className={c.estornado ? "inativo" : ""}>
                  <td>{data(c.data_corte)}</td><td>{c.lote}</td><td className="num">{c.pecas}</td>
                  <td className="num">{kg(c.peso_real_kg)} kg</td><td className="num">{c.comprimento_barra_mm ?? "—"}</td>
                  <td>{c.cop ?? "—"}</td><td>{c.estornado && <span className="etiqueta">estornado</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {altera && (
        <div className="botoes" style={{ marginTop: "var(--esp-5)" }}>
          {pode.trocarOp && <button className="secundario" onClick={() => setAcao("trocar-op")}>Trocar OP</button>}
          {pode.duplicar && <button className="secundario" onClick={() => void duplicar()}>Duplicar</button>}
          {pode.cancelar && <button className="perigo" onClick={() => setAcao("cancelar")}>{s.situacao === "RASCUNHO" ? "Excluir rascunho" : "Cancelar solicitação"}</button>}
        </div>
      )}

      {acao === "cancelar" && <JanelaTexto titulo={s.situacao === "RASCUNHO" ? "Excluir rascunho" : "Cancelar solicitação"} rotulo="Motivo" minimo={3}
        botao={s.situacao === "RASCUNHO" ? "Excluir rascunho" : "Cancelar solicitação"} perigo aviso="A reserva no lote é liberada."
        enviar={(t) => api.post(`/solicitacoes/${s.id}/cancelar`, { motivo: t })} aoFechar={() => setAcao(null)} aoGravar={() => feito()} />}
      {acao === "encerrar" && <JanelaTexto titulo="Encerrar com saldo pendente" rotulo="Justificativa" minimo={JUSTIFICATIVA_MIN} botao="Encerrar com saldo pendente"
        aviso={`Foram cortadas ${s.pecas_cortadas} de ${s.quantidade} peças. O que foi cortado segue para o COP e a reserva do restante é liberada.`}
        enviar={(t) => api.post(`/solicitacoes/${s.id}/encerrar`, { justificativa: t })} aoFechar={() => setAcao(null)} aoGravar={() => feito()} />}
      {acao === "trocar-op" && <JanelaTrocarOp s={s} aoFechar={() => setAcao(null)} aoGravar={(avisos) => feito(avisos)} />}
      {acao === "enviar" && <JanelaEnviar s={s} aoFechar={() => setAcao(null)} aoGravar={() => feito()} />}
      {acao === "trocar-lote" && <JanelaTrocarLote s={s} aoFechar={() => setAcao(null)} aoGravar={() => feito()} />}
    </>
  );
}

/* ------------------------------------------------------------------ janelas */

function JanelaTexto({ titulo, rotulo, minimo, botao, aviso, perigo = false, enviar, aoFechar, aoGravar }: {
  titulo: string; rotulo: string; minimo: number; botao: string; aviso?: string; perigo?: boolean;
  enviar: (texto: string) => Promise<unknown>; aoFechar: () => void; aoGravar: () => void;
}) {
  const [t, setT] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  async function ok(e: FormEvent) {
    e.preventDefault();
    setErro("");
    setOcupado(true);
    try {
      await enviar(t.trim());
      aoGravar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível concluir.");
    } finally {
      setOcupado(false);
    }
  }
  const falta = minimo - t.trim().length;
  return (
    <Janela titulo={titulo} aoFechar={aoFechar}>
      <form onSubmit={(e) => void ok(e)} className="bloco-passo" style={{ gap: "var(--esp-4)" }}>
        {aviso && <p className="desc">{aviso}</p>}
        <label>{rotulo}<textarea autoFocus value={t} onChange={(e) => setT(e.target.value)} rows={3} />
          <small className="dica">{falta > 0 ? `Faltam ${falta} caractere(s).` : "Ok."}</small></label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className={perigo ? "perigo" : "primario"} disabled={falta > 0 || ocupado}>{botao}</button>
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
        </div>
      </form>
    </Janela>
  );
}

function JanelaTrocarOp({ s, aoFechar, aoGravar }: { s: SolicDetalhe; aoFechar: () => void; aoGravar: (avisos: string[]) => void }) {
  const [op, setOp] = useState("");
  const [j, setJ] = useState("");
  const [erro, setErro] = useState("");
  async function ok(e: FormEvent) {
    e.preventDefault();
    setErro("");
    try {
      const r = await api.post<{ avisos?: string[] }>(`/solicitacoes/${s.id}/trocar-op`, { op: Number(op), justificativa: j.trim() });
      aoGravar(r?.avisos ?? []);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível trocar a OP.");
    }
  }
  return (
    <Janela titulo={`Trocar OP ${s.op}`} aoFechar={aoFechar}>
      <form onSubmit={(e) => void ok(e)} className="bloco-passo" style={{ gap: "var(--esp-4)" }}>
        <p className="desc">Use quando a OP foi cancelada no Mega ou o material vai para outra OP. Se o SA já estava confirmado, o sistema avisa o que ajustar no Mega.</p>
        <label>Nova OP<input inputMode="numeric" autoFocus value={op} onChange={(e) => setOp(e.target.value)} required /></label>
        <label>Justificativa<textarea value={j} onChange={(e) => setJ(e.target.value)} rows={3} /></label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario" disabled={!Number(op) || j.trim().length < JUSTIFICATIVA_MIN}>Trocar OP</button>
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
        </div>
      </form>
    </Janela>
  );
}

/** Enviar rascunho: não há prévia; o 409 devolve as validações e a tela pede as justificativas. */
function JanelaEnviar({ s, aoFechar, aoGravar }: { s: SolicDetalhe; aoFechar: () => void; aoGravar: () => void }) {
  const [oc, setOc] = useState<Ocorrencia[] | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  async function enviar() {
    setErro("");
    setOcupado(true);
    try {
      await api.post(`/solicitacoes/${s.id}/enviar`, { confirmacoes: oc ? confirmacoesValidas(oc, conf) : {} });
      aoGravar();
    } catch (err) {
      const v = validacaoDoErro(err);
      if (v) setOc(v.ocorrencias);
      else setErro(err instanceof Error ? err.message : "Não foi possível enviar.");
    } finally {
      setOcupado(false);
    }
  }
  return (
    <Janela titulo={`Enviar ${s.numero} ao RJ`} aoFechar={aoFechar}>
      <p className="desc">O peso previsto ({s.peso_previsto_kg !== null ? `${kg(s.peso_previsto_kg)} kg` : "—"}) fica reservado no lote {s.lote.codigo} e o RJ é avisado.</p>
      {oc && <PainelValidacao ocorrencias={oc} confirmacoes={conf} aoMudar={setConf} />}
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="primario" disabled={ocupado || (!!oc && !podeGravar(oc, conf))} onClick={() => void enviar()}>{ocupado ? "Enviando…" : "Enviar ao RJ"}</button>
        <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}

interface LoteOpcao { id: number; codigo: string; liga: string; bitola: string; conteiner: string | null; estoque: string; disponivel_kg: number; sobremetal_pct: number | null; liga_equivalente?: boolean }

/** Material insuficiente → escolher outro lote do RJ (R003). Volta para Enviada com nova reserva. */
function JanelaTrocarLote({ s, aoFechar, aoGravar }: { s: SolicDetalhe; aoFechar: () => void; aoGravar: () => void }) {
  const [lotes, setLotes] = useState<LoteOpcao[] | null>(null);
  const [lote, setLote] = useState<number | null>(null);
  const [v, setV] = useState<Validacao | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [erro, setErro] = useState("");
  const m = s.medida_acabada;

  useEffect(() => {
    if (!m) return setLotes([]);
    api.get<{ itens: LoteOpcao[] }>(`/lotes/compativeis${qs({ liga: s.lote.liga, formato: m.formato, espessura: m.espessura, largura: m.largura,
      diametro: m.diametro, comprimento: m.comprimento, quantidade: s.quantidade - s.pecas_cortadas, estoque: "RJ_NO_RIO" })}`)
      .then((r) => setLotes(r.itens.filter((l) => l.id !== s.lote.id)))
      .catch((e: Error) => { setErro(e.message); setLotes([]); });
  }, [s, m]);

  async function escolher(id: number) {
    setLote(id);
    setV(null);
    setConf({});
    setErro("");
    try {
      setV(await api.post<Validacao>(`/solicitacoes/${s.id}/trocar-lote/validar`, { lote_id: id, confirmacoes: {} }));
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível validar o lote.");
    }
  }

  async function gravar() {
    if (!lote || !v) return;
    try {
      await api.post(`/solicitacoes/${s.id}/trocar-lote`, { lote_id: lote, confirmacoes: confirmacoesValidas(v.ocorrencias, conf) });
      aoGravar();
    } catch (err) {
      const x = validacaoDoErro(err);
      if (x) setV(x);
      else setErro(err instanceof Error ? err.message : "Não foi possível trocar o lote.");
    }
  }

  return (
    <Janela titulo="Trocar lote" aoFechar={aoFechar} larga>
      <p className="desc">Lotes do RJ no Rio que comportam a peça, sem o lote atual ({s.lote.codigo}).</p>
      {lotes === null ? <p className="carregando">Buscando lotes…</p> : !lotes.length ? (
        <p className="validacao alerta">Nenhum outro lote compatível com saldo. Cancele a solicitação ou peça compra.</p>
      ) : (
        <ul className="escolhas">
          {lotes.map((l) => (
            <li key={l.id}>
              <label className={lote === l.id ? "escolha-lote marcada" : "escolha-lote"}>
                <input type="radio" name="novo-lote" checked={lote === l.id} onChange={() => void escolher(l.id)} />
                <span><span className="titulo">{l.liga} {l.bitola} · {l.conteiner ?? "—"}{l.liga_equivalente && <span className="etiqueta atencao">liga equivalente</span>}</span>
                  <span className="linha2">{l.codigo} · sobremetal {l.sobremetal_pct !== null ? `${l.sobremetal_pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} %` : "—"}</span></span>
                <span className="kg"><strong>{kg(l.disponivel_kg)} kg</strong><span className="desc">disponível</span></span>
              </label>
            </li>
          ))}
        </ul>
      )}
      {v && <PainelValidacao ocorrencias={v.ocorrencias} confirmacoes={conf} aoMudar={setConf} semOcorrencias="Lote aceito." />}
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="primario" disabled={!v || !podeGravar(v.ocorrencias, conf)} onClick={() => void gravar()}>Trocar lote e reenviar ao RJ</button>
        <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}
