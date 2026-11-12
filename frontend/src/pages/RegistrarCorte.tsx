import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, data, kg, num, qs, validacaoDoErro, type Validacao } from "../api/cliente";
import { MODO_NOME, material, type SolicDetalhe } from "../api/solicitacao";
import PainelValidacao, { confirmacoesValidas, podeGravar, type Confirmacoes } from "../components/PainelValidacao";

interface LoteOpcao { id: number; codigo: string; liga: string; bitola: string; conteiner: string | null; disponivel_kg: number; saldo_kg: number }
interface Linha { lote_id: number; pecas: string; peso: string; barra: string }
interface Efeito { lote: string; lote_id?: number; antes_kg: number; depois_kg: number }
interface ResultadoCorte { frase?: string; efeitos?: Efeito[]; previsto_kg?: number | null }

const hojeIso = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const diasAtras = (n: number) => new Date(Date.now() - n * 86400000 - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

/** T10 Registrar corte (RJ). Uma linha por lote usado; "Usar outro lote / dividir" acrescenta linhas. */
export default function RegistrarCorte() {
  const { id } = useParams();
  const nav = useNavigate();
  const [s, setS] = useState<SolicDetalhe | null>(null);
  const [opcoes, setOpcoes] = useState<LoteOpcao[]>([]);
  const [linhas, setLinhas] = useState<Linha[]>([]);
  const [dataCorte, setDataCorte] = useState(hojeIso());
  const [obs, setObs] = useState("");
  const [v, setV] = useState<Validacao<ResultadoCorte> | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [feito, setFeito] = useState(false);

  useEffect(() => {
    api.get<SolicDetalhe>(`/solicitacoes/${id}`).then((x) => {
      setS(x);
      const faltam = Math.max(0, x.quantidade - x.pecas_cortadas);
      setLinhas([{ lote_id: x.lote.id, pecas: String(faltam || x.quantidade), peso: "", barra: "" }]);
      const m = x.medida_acabada;
      if (m) {
        api.get<{ itens: LoteOpcao[] }>(`/lotes/compativeis${qs({ liga: x.lote.liga, formato: m.formato, espessura: m.espessura, largura: m.largura,
          diametro: m.diametro, comprimento: m.comprimento, quantidade: 1, estoque: "RJ_NO_RIO" })}`)
          .then((r) => setOpcoes(r.itens)).catch(() => setOpcoes([]));
      }
    }).catch((e: Error) => setErro(e.message));
  }, [id]);

  const lotesDisponiveis = useMemo(() => {
    if (!s) return [];
    const atual: LoteOpcao = { id: s.lote.id, codigo: s.lote.codigo, liga: s.lote.liga, bitola: s.lote.bitola, conteiner: s.lote.conteiner, disponivel_kg: NaN, saldo_kg: NaN };
    return [atual, ...opcoes.filter((o) => o.id !== s.lote.id)];
  }, [s, opcoes]);

  const mudar = (i: number, p: Partial<Linha>) => { setLinhas(linhas.map((l, k) => (k === i ? { ...l, ...p } : l))); setV(null); };
  const corpo = (c: Confirmacoes) => ({
    linhas: linhas.map((l) => ({ lote_id: l.lote_id, pecas: num(l.pecas) ?? 0, peso_real_kg: num(l.peso) ?? 0, comprimento_barra_mm: num(l.barra) ?? null })),
    data_corte: dataCorte, observacao: obs.trim() || null, confirmacoes: c,
  });
  // P26(2a): aviso BARRA_MAIS_LEVE_QUE_PECA vem da API; enquanto ela não mandar, a tela calcula o mesmo aviso (não bloqueia)
  const somaPeso = linhas.reduce((t, l) => t + (num(l.peso) ?? 0), 0);
  const somaPecas = linhas.reduce((t, l) => t + (num(l.pecas) ?? 0), 0);
  const previstoProp = s?.peso_previsto_kg && s.quantidade ? (s.peso_previsto_kg * somaPecas) / s.quantidade : 0;
  const barraLeveLocal = !!v && s?.modo === "TRAZER_INTEIRA" && previstoProp > 0 && somaPeso > 0 && somaPeso < previstoProp &&
    !v.ocorrencias.some((o) => o.codigo.startsWith("BARRA_MAIS_LEVE_QUE_PECA"));
  const completo = linhas.length > 0 && linhas.every((l) => (num(l.pecas) ?? 0) > 0 && (num(l.peso) ?? 0) > 0);

  async function conferir() {
    setErro("");
    setOcupado(true);
    try {
      setV(await api.post<Validacao<ResultadoCorte>>(`/solicitacoes/${id}/corte/validar`, corpo({})));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível conferir o corte.");
    } finally {
      setOcupado(false);
    }
  }

  async function confirmar() {
    if (!v) return;
    setErro("");
    setOcupado(true);
    try {
      await api.post(`/solicitacoes/${id}/corte`, corpo(confirmacoesValidas(v.ocorrencias, conf)));
      setFeito(true);
    } catch (e) {
      const x = validacaoDoErro<ResultadoCorte>(e);
      if (x) setV({ ...x, resultado: x.resultado ?? v.resultado });
      else setErro(e instanceof Error ? e.message : "Não foi possível gravar o corte.");
    } finally {
      setOcupado(false);
    }
  }

  if (!s) return erro ? <p className="erro" role="alert">{erro}</p> : <p className="carregando">Carregando…</p>;

  if (feito) {
    return (
      <>
        <header className="cabecalho"><h1>Corte registrado · OP {s.op}</h1></header>
        <p className="validacao ok" role="status">O peso real foi baixado do lote e a reserva liberada. O corte já aparece em "Cortes prontos" para entrar no COP.</p>
        <div className="botoes"><button className="primario" onClick={() => nav("/fila-rj")}>Voltar para a fila</button></div>
      </>
    );
  }

  const nomeLote = (lid: number) => { const o = lotesDisponiveis.find((x) => x.id === lid); return o ? `${o.liga} ${o.bitola} · ${o.conteiner ?? "—"} (${o.codigo})` : String(lid); };

  return (
    <>
      <p><Link to="/fila-rj">← Fila RJ</Link></p>
      <header className="cabecalho">
        <h1>Registrar corte · OP {s.op}</h1>
        <p className="cartao-instrucao">{s.instrucao ?? `${s.quantidade} peça(s)`}</p>
      </header>

      <section className="ficha">
        <dl className="dados">
          <div><dt>Material pedido</dt><dd>{material(s.lote)} · {s.lote.conteiner ?? "—"}</dd></div>
          <div><dt>Modo</dt><dd>{MODO_NOME[s.modo]}</dd></div>
          <div><dt>Peças</dt><dd>{s.pecas_cortadas ? `${s.pecas_cortadas} já cortadas de ${s.quantidade}` : s.quantidade}</dd></div>
          <div><dt>Peso previsto</dt><dd>{s.peso_previsto_kg !== null ? `${kg(s.peso_previsto_kg)} kg` : "—"}</dd></div>
          <div><dt>Prazo</dt><dd>{data(s.prazo)}</dd></div>
          {s.instrucao_processo && <div><dt>Processo</dt><dd>{s.instrucao_processo}</dd></div>}
        </dl>
        {s.modo === "TRAZER_INTEIRA" && <p className="dica" style={{ marginTop: 8 }}>Peça inteira: informe o peso da barra inteira separada. A tolerância (8 % para material do RJ) é conferida no corte em Itu. Se a barra pesar menos que a peça prevista, aparece um aviso para conferir a pesagem ou a bitola (não bloqueia).</p>}
      </section>

      {linhas.map((l, i) => (
        <section key={i} className="painel-form" style={{ marginTop: "var(--esp-4)" }} aria-label={`Lote ${i + 1}`}>
          <div className="linha-titulo">
            <h2>{linhas.length > 1 ? `Lote ${i + 1}` : "Lote usado"}</h2>
            {i > 0 && <button className="link" onClick={() => { setLinhas(linhas.filter((_, k) => k !== i)); setV(null); }}>Remover</button>}
          </div>
          <label>
            Lote
            <select value={l.lote_id} onChange={(e) => mudar(i, { lote_id: Number(e.target.value) })}>
              {lotesDisponiveis.map((o) => (
                <option key={o.id} value={o.id}>{o.liga} {o.bitola} · {o.conteiner ?? "—"} ({o.codigo}){Number.isFinite(o.disponivel_kg) ? ` · ${kg(o.disponivel_kg)} kg` : " · lote pedido"}</option>
              ))}
            </select>
            {l.lote_id !== s.lote.id && <small className="dica">Lote diferente do pedido: o sistema pede justificativa e avisa Itu.</small>}
          </label>
          <div className="grade-form">
            <label>Peças cortadas<input inputMode="numeric" value={l.pecas} onChange={(e) => mudar(i, { pecas: e.target.value })} /></label>
            <label>Peso real de balança (kg)<input inputMode="decimal" className="campo-grande" value={l.peso} onChange={(e) => mudar(i, { peso: e.target.value })} autoFocus={i === 0} /></label>
            <label>Comprimento da barra (mm), opcional<input inputMode="decimal" value={l.barra} onChange={(e) => mudar(i, { barra: e.target.value })} /></label>
          </div>
        </section>
      ))}

      <div className="botoes" style={{ marginTop: "var(--esp-3)" }}>
        <button className="secundario" onClick={() => { setLinhas([...linhas, { lote_id: (opcoes.find((o) => o.id !== s.lote.id) ?? { id: s.lote.id }).id, pecas: "", peso: "", barra: "" }]); setV(null); }}>
          Usar outro lote / dividir
        </button>
      </div>

      <div className="painel-form" style={{ marginTop: "var(--esp-4)" }}>
        <div className="grade-form">
          <label>Data do corte<input type="date" value={dataCorte} min={diasAtras(7)} max={hojeIso()} onChange={(e) => { setDataCorte(e.target.value); setV(null); }} /></label>
          <label>Observação<input value={obs} onChange={(e) => setObs(e.target.value)} /></label>
        </div>
      </div>

      {v && (
        <div className="bloco-passo" style={{ marginTop: "var(--esp-4)" }}>
          {v.resultado?.frase && <p className="frase-resultado resultado-frase">{v.resultado.frase}</p>}
          {!!v.resultado?.efeitos?.length && (
            <ul className="efeitos">
              {v.resultado.efeitos.map((e) => (
                <li key={e.lote}>Lote <strong>{e.lote_id ? nomeLote(e.lote_id) : e.lote}</strong>: {kg(e.antes_kg)} kg → <strong>{kg(e.depois_kg)} kg</strong></li>
              ))}
            </ul>
          )}
          {barraLeveLocal && (
            <p className="validacao alerta">
              A barra ({kg(somaPeso)} kg) pesa menos do que a peça prevista ({kg(previstoProp)} kg); confira a pesagem ou a bitola.
            </p>
          )}
          <PainelValidacao ocorrencias={v.ocorrencias} confirmacoes={conf} aoMudar={setConf} semOcorrencias="Peso dentro da tolerância." />
        </div>
      )}
      {erro && <p className="erro" role="alert">{erro}</p>}

      <div className="rodape-acao">
        <span className="resultado-frase">{somaPecas} peça(s) · {kg(somaPeso)} kg</span>
        {!v ? (
          <button className="primario" disabled={!completo || ocupado} onClick={() => void conferir()}>{ocupado ? "Conferindo…" : "Conferir corte"}</button>
        ) : (
          <button className="primario" disabled={ocupado || !podeGravar(v.ocorrencias, conf)} onClick={() => void confirmar()}>{ocupado ? "Gravando…" : "Confirmar corte"}</button>
        )}
      </div>
    </>
  );
}
