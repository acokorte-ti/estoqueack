import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ErroApi, ESTOQUE_NOME, kg, num, qs, validacaoDoErro, type Validacao } from "../api/cliente";
import PainelValidacao, { confirmacoesValidas, podeGravar, type Confirmacoes } from "../components/PainelValidacao";

interface Lote { id: number; codigo: string; conteiner: string | null; liga: string; bitola: string; estoque: string; tipo: string;
  saldo_kg: number; disponivel_kg: number; codigo_mega?: number | null }
interface OpMega { numero: number; item_codigo: number | null; item_descricao: string | null; cliente: string | null; pedido: string | null;
  situacao: string | null; situacao_descricao: string | null }
interface Resultado { frase?: string; perda_kg?: number; perda_esperada_kg?: number; previsto_kg?: number | null; gera_sa?: boolean; instrucao_mega?: string | null }
interface Gravado { id: number; op: number; consumo_kg: number; sobra_kg: number; perda_kg: number; lote_reto: { id: number; codigo: string } | null;
  sa_id: number | null; instrucao_mega: string | null }

const hojeIso = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const emItu = (l: Lote) => l.estoque !== "RJ_NO_RIO";

/** T13 Corte em Itu: consumo da OP, sobra na bitola ou RETO, perda e a instrução "Fazer no Mega". */
export default function CorteItu() {
  const [params] = useSearchParams();
  const [opNum, setOpNum] = useState(params.get("op") ?? "");
  const [op, setOp] = useState<OpMega | null>(null);
  const [megaFora, setMegaFora] = useState(false);
  const [lote, setLote] = useState<Lote | null>(null);
  const [busca, setBusca] = useState("");
  const [achados, setAchados] = useState<Lote[] | null>(null);
  const previstoUrl = num(params.get("previsto") ?? "");
  const [f, setF] = useState({ pecas: "", consumo: "", sobra: "", naBitola: true, usado: "", data: hojeIso(), obs: "" });
  const [v, setV] = useState<Validacao<Resultado> | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [gravado, setGravado] = useState<Gravado | null>(null);
  const [copiado, setCopiado] = useState(false);

  // vindo do T07 ("Registrar corte em Itu agora") ou do recebimento de peça inteira
  useEffect(() => {
    const lid = params.get("lote_id");
    if (lid) api.get<Lote>(`/lotes/${lid}`).then(setLote).catch(() => undefined);
    if (params.get("op")) void buscarOp(params.get("op")!);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function buscarOp(n: string) {
    setErro("");
    setOp(null);
    setMegaFora(false);
    const numero = Number(n.trim());
    if (!Number.isInteger(numero) || numero <= 0) return setErro("Digite o número da OP.");
    try {
      setOp(await api.get<OpMega>(`/mega/op/${numero}`));
    } catch (e) {
      if (e instanceof ErroApi && e.status === 503) { setMegaFora(true); setOp({ numero, item_codigo: null, item_descricao: null, cliente: null, pedido: null, situacao: null, situacao_descricao: null }); }
      else setErro(e instanceof Error ? e.message : "Não foi possível consultar a OP.");
    }
    if (!params.get("lote_id")) {
      const s = await api.get<{ lote_id: number | null }>(`/cortes-itu/sugestao?op=${numero}`).catch(() => null);
      if (s?.lote_id) api.get<Lote>(`/lotes/${s.lote_id}`).then(setLote).catch(() => undefined);
    }
  }

  async function procurar(e: FormEvent) {
    e.preventDefault();
    try {
      const r = await api.get<{ itens: Lote[] }>(`/lotes${qs({ busca: busca.trim(), com_saldo: true, por_pagina: 30 })}`);
      setAchados(r.itens.filter(emItu));
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível procurar.");
    }
  }

  const mudar = (p: Partial<typeof f>) => { setF({ ...f, ...p }); setV(null); };
  const corpo = (c: Confirmacoes) => ({
    op: op?.numero, lote_id: lote?.id, consumo_kg: num(f.consumo), sobra_kg: num(f.sobra) ?? 0, sobra_na_bitola: f.naBitola,
    pecas: num(f.pecas) ?? null, peso_usado_kg: num(f.usado) ?? null, previsto_kg: previstoUrl ?? null,
    data_corte: f.data || null, observacao: f.obs.trim() || null, op_manual: megaFora ? { item_codigo: null, cliente: null } : null,
    confirmacoes: c,
  });
  const pronto = !!op && !!lote && (num(f.consumo) ?? 0) > 0;

  async function conferir() {
    setErro("");
    setOcupado(true);
    try {
      setV(await api.post<Validacao<Resultado>>("/cortes-itu/validar", corpo({})));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível conferir.");
    } finally {
      setOcupado(false);
    }
  }

  async function confirmar() {
    if (!v) return;
    setErro("");
    setOcupado(true);
    try {
      setGravado(await api.post<Gravado>("/cortes-itu", corpo(confirmacoesValidas(v.ocorrencias, conf))));
    } catch (e) {
      const x = validacaoDoErro<Resultado>(e);
      if (x) setV({ ...x, resultado: x.resultado ?? v.resultado });
      else setErro(e instanceof Error ? e.message : "Não foi possível gravar.");
    } finally {
      setOcupado(false);
    }
  }

  function recomecar() {
    setGravado(null); setV(null); setConf({}); setLote(null); setOp(null); setOpNum(""); setCopiado(false);
    setF({ pecas: "", consumo: "", sobra: "", naBitola: true, usado: "", data: hojeIso(), obs: "" });
  }

  if (gravado) {
    return (
      <>
        <header className="cabecalho"><h1>Corte em Itu registrado · OP {gravado.op}</h1></header>
        <p className="validacao ok" role="status">
          <span>
            Consumo {kg(gravado.consumo_kg)} kg, sobra {kg(gravado.sobra_kg)} kg, perda {kg(gravado.perda_kg)} kg.
            {gravado.lote_reto && <> Novo lote RETO <strong>{gravado.lote_reto.codigo}</strong>.</>}
            {gravado.sa_id && <> Pedido de SA criado: <Link to="/sa">abrir SA</Link>.</>}
          </span>
        </p>
        {gravado.instrucao_mega && (
          <section className="ficha fazer-mega">
            <h2>Fazer no Mega</h2>
            <p className="resultado-frase">{gravado.instrucao_mega}</p>
            <div className="botoes">
              <button className="primario" onClick={() => void navigator.clipboard.writeText(gravado.instrucao_mega!).then(() => setCopiado(true))}>
                {copiado ? "Copiado" : "Copiar instrução"}
              </button>
            </div>
            <p className="dica">A baixa na OP e a transferência para o código RETO continuam sendo feitas no Mega. A conciliação confere depois.</p>
          </section>
        )}
        <div className="botoes" style={{ marginTop: "var(--esp-4)" }}><button className="secundario" onClick={recomecar}>Novo corte em Itu</button></div>
      </>
    );
  }

  return (
    <>
      <header className="cabecalho">
        <h1>Corte em Itu</h1>
        <p>Consumo da OP, sobra e RETO para material que já está em Itu (RJ em Itu ou Estoque Mega).</p>
      </header>
      {erro && <p className="erro" role="alert">{erro}</p>}

      <form className="painel-form linha-form" onSubmit={(e) => { e.preventDefault(); void buscarOp(opNum); }}>
        <label>Nº da OP<input inputMode="numeric" autoFocus={!opNum} value={opNum} onChange={(e) => setOpNum(e.target.value)} required /></label>
        <button className="secundario">Buscar OP</button>
      </form>
      {op && (
        <p className={megaFora ? "validacao alerta" : op.situacao && op.situacao !== "AB" ? "validacao alerta" : "frase-resultado"}>
          {megaFora ? `OP ${op.numero}: Mega fora do ar; os dados da OP serão conferidos depois.` :
            <>OP {op.numero} · {op.item_codigo} {op.item_descricao} · {op.cliente ?? "—"}{op.situacao && op.situacao !== "AB" && ` · ${op.situacao_descricao}`}</>}
        </p>
      )}

      <section className="painel-form" style={{ marginTop: "var(--esp-4)" }}>
        <h2>Lote</h2>
        {lote ? (
          <div className="escolha-lote marcada" style={{ cursor: "default" }}>
            <span />
            <span>
              <span className="titulo">{lote.liga} {lote.bitola} · {lote.conteiner ?? "sem contêiner"} <span className={`estoque-tag ${lote.estoque}`}>{ESTOQUE_NOME[lote.estoque] ?? lote.estoque}</span>{lote.tipo !== "ORIGINAL" && <span className="etiqueta">{lote.tipo}</span>}</span>
              <span className="linha2">{lote.codigo}{lote.codigo_mega ? ` · código Mega ${lote.codigo_mega}` : ""}</span>
            </span>
            <span className="kg"><strong>{kg(lote.saldo_kg)} kg</strong><span className="desc">saldo</span></span>
          </div>
        ) : <p className="desc">Busque o lote pelo código, contêiner ou descrição.</p>}
        <form className="linha-form" style={{ marginBottom: 0 }} onSubmit={(e) => void procurar(e)}>
          <label>{lote ? "Trocar lote" : "Procurar lote"}<input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="L-000451, CH25K, H13 70x610…" /></label>
          <button className="secundario">Procurar</button>
        </form>
        {achados && (achados.length ? (
          <ul className="escolhas">
            {achados.map((l) => (
              <li key={l.id}>
                <button type="button" className="escolha-lote" style={{ width: "100%", textAlign: "left" }} onClick={() => { setLote(l); setAchados(null); setV(null); }}>
                  <span />
                  <span><span className="titulo">{l.liga} {l.bitola} · {l.conteiner ?? "—"} <span className={`estoque-tag ${l.estoque}`}>{ESTOQUE_NOME[l.estoque] ?? l.estoque}</span></span>
                    <span className="linha2">{l.codigo} · {l.tipo}</span></span>
                  <span className="kg"><strong>{kg(l.saldo_kg)} kg</strong></span>
                </button>
              </li>
            ))}
          </ul>
        ) : <p className="validacao alerta">Nenhum lote em Itu com esse texto.</p>)}
      </section>

      <section className="painel-form" style={{ marginTop: "var(--esp-4)" }}>
        <h2>Corte</h2>
        {previstoUrl && <p className="dica">Peso previsto da solicitação: {kg(previstoUrl)} kg (base da regra dos 5 %).</p>}
        <div className="grade-form">
          <label>Peças produzidas<input inputMode="numeric" value={f.pecas} onChange={(e) => mudar({ pecas: e.target.value })} /></label>
          <label>Consumo da OP (kg, balança)<input inputMode="decimal" className="campo-grande" value={f.consumo} onChange={(e) => mudar({ consumo: e.target.value })} /></label>
          <label>Sobra (kg, balança)<input inputMode="decimal" className="campo-grande" value={f.sobra} onChange={(e) => mudar({ sobra: e.target.value })} placeholder="0" /></label>
        </div>
        {(num(f.sobra) ?? 0) > 0 && (
          <fieldset className="formatos">
            <legend>A sobra ainda está na bitola {lote?.bitola ?? ""}?</legend>
            <label className={f.naBitola ? "opcao marcada" : "opcao"}><input type="radio" name="bitola" checked={f.naBitola} onChange={() => mudar({ naBitola: true })} />Sim, fica no lote</label>
            <label className={!f.naBitola ? "opcao marcada" : "opcao"}><input type="radio" name="bitola" checked={!f.naBitola} onChange={() => mudar({ naBitola: false })} />Não, vira RETO</label>
          </fieldset>
        )}
        <details className="avancado">
          <summary>Peso do material usado, data e observação</summary>
          <div className="grade-form">
            <label>Peso do material usado (kg)<input inputMode="decimal" value={f.usado} onChange={(e) => mudar({ usado: e.target.value })} placeholder={lote ? `saldo: ${kg(lote.saldo_kg)}` : ""} />
              <small className="dica">Para lote grande, informe o peso do pedaço que foi para a serra. Em branco: o saldo do lote. A perda é calculada sobre ele.</small></label>
            <label>Data do corte<input type="date" value={f.data} max={hojeIso()} onChange={(e) => mudar({ data: e.target.value })} /></label>
            <label>Observação<input value={f.obs} onChange={(e) => mudar({ obs: e.target.value })} /></label>
          </div>
        </details>
      </section>

      {v && (
        <div className="bloco-passo" style={{ marginTop: "var(--esp-4)" }}>
          {v.resultado?.frase && <p className="frase-resultado resultado-frase">{v.resultado.frase}</p>}
          {v.resultado && (
            <dl className="dados ficha">
              {v.resultado.perda_kg !== undefined && <div><dt>Perda de corte</dt><dd>{kg(v.resultado.perda_kg)} kg</dd></div>}
              {v.resultado.perda_esperada_kg !== undefined && <div><dt>Perda esperada (serra)</dt><dd>{kg(v.resultado.perda_esperada_kg)} kg</dd></div>}
              {v.resultado.previsto_kg ? <div><dt>Previsto</dt><dd>{kg(v.resultado.previsto_kg)} kg</dd></div> : null}
              {v.resultado.gera_sa !== undefined && <div><dt>Gera pedido de SA</dt><dd>{v.resultado.gera_sa ? "Sim (material fiscal RJ)" : "Não"}</dd></div>}
              {v.resultado.instrucao_mega && <div className="largo"><dt>Fazer no Mega</dt><dd>{v.resultado.instrucao_mega}</dd></div>}
            </dl>
          )}
          <PainelValidacao ocorrencias={v.ocorrencias} confirmacoes={conf} aoMudar={setConf} semOcorrencias="Dentro da tolerância." />
        </div>
      )}

      <div className="rodape-acao">
        {!v ? (
          <button className="primario" disabled={!pronto || ocupado} onClick={() => void conferir()}>{ocupado ? "Conferindo…" : "Conferir corte"}</button>
        ) : (
          <button className="primario" disabled={ocupado || !podeGravar(v.ocorrencias, conf)} onClick={() => void confirmar()}>{ocupado ? "Gravando…" : "Confirmar"}</button>
        )}
      </div>
    </>
  );
}
