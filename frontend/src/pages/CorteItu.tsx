import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api, ErroApi, ESTOQUE_NOME, kg, num, qs } from "../api/cliente";
import LancamentoCorteItu, { CartaoLote, type LoteCorteItu as Lote } from "../components/LancamentoCorteItu";
import { diasDe, textoPeca, usePesoReal, vencida, type PecaPesoReal } from "../api/pesoReal";

interface OpMega { numero: number; item_codigo: number | null; item_descricao: string | null; cliente: string | null; pedido: string | null;
  situacao: string | null; situacao_descricao: string | null }

const emItu = (l: Lote) => l.estoque !== "RJ_NO_RIO";

/**
 * T13 Corte em Itu pelos atalhos. Fora do menu desde 2026-11-17: o corte normal começa em "Pedir corte de material".
 * Abre pelo Painel (peça inteira aguardando peso real, "Informar peso real"), pelo lote RJ em Itu ("Usar em corte em Itu")
 * e pelo recebimento ("Cortar em Itu agora").
 */
export default function CorteItu() {
  const [params] = useSearchParams();
  const [opNum, setOpNum] = useState(params.get("op") ?? "");
  const [op, setOp] = useState<OpMega | null>(null);
  const [megaFora, setMegaFora] = useState(false);
  const [lote, setLote] = useState<Lote | null>(null);
  const [busca, setBusca] = useState("");
  const [achados, setAchados] = useState<Lote[] | null>(null);
  const previstoUrl = num(params.get("previsto") ?? "");
  const misto = params.get("consumo_misto") === "1";
  const [erro, setErro] = useState("");
  const [feito, setFeito] = useState(false);
  const [rodada, setRodada] = useState(0);
  const { resumo: pesoReal } = usePesoReal();
  // peça inteira do RJ aguardando peso real (spec v3.11 §2.2 passo 7): a T13 sugere e resolve a pendência
  const pecaPendente = pesoReal?.pecas.find((p) => (p.lote_id ? p.lote_id === lote?.id : !!op && p.op === op.numero)) ?? null;

  function usarPeca(p: PecaPesoReal) {
    if (!p.op) return;
    setOpNum(String(p.op));
    if (p.lote_id) api.get<Lote>(`/lotes/${p.lote_id}`).then(setLote).catch(() => undefined);
    void buscarOp(String(p.op), !!p.lote_id);
  }

  // vindo do Painel, do lote RJ em Itu ou do recebimento de peça inteira
  useEffect(() => {
    const lid = params.get("lote_id");
    if (lid) api.get<Lote>(`/lotes/${lid}`).then(setLote).catch(() => undefined);
    if (params.get("op")) void buscarOp(params.get("op")!);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function buscarOp(n: string, temLote = !!params.get("lote_id")) {
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
    if (!temLote) {
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

  function recomecar() {
    setFeito(false); setLote(null); setOp(null); setOpNum(""); setAchados(null); setRodada((r) => r + 1);
  }

  return (
    <>
      <header className="cabecalho">
        <h1>Registrar corte em Itu</h1>
        {!feito && <p>Consumo da OP, sobra e RETO para material que já está em Itu (RJ em Itu ou Estoque Mega). O corte do dia a dia começa em "Pedir corte de material".</p>}
      </header>
      {erro && <p className="erro" role="alert">{erro}</p>}

      {!feito && (
        <>
          {!op && !lote && !!pesoReal?.pecas.length && (
            <section className="painel-form" aria-label="Peças inteiras do RJ aguardando peso real">
              <h2>Peças inteiras do RJ aguardando peso real ({pesoReal.pecas.length})</h2>
              <p className="dica">Depois do corte, informe o consumo pesado na balança. Com mais de {pesoReal.limite} dias sem peso real, novas solicitações ao RJ ficam bloqueadas.</p>
              <ul className="escolhas">
                {pesoReal.pecas.slice(0, 10).map((p, k) => (
                  <li key={p.pendencia_id ?? p.lote_id ?? k}>
                    <button type="button" className="escolha-lote" style={{ width: "100%", textAlign: "left" }} onClick={() => usarPeca(p)} disabled={!p.op}>
                      <span />
                      <span><span className="titulo">{textoPeca(p)}</span><span className="linha2">{[p.lote, p.conteiner].filter(Boolean).join(" · ")}</span></span>
                      <span className="kg"><strong className={vencida(p, pesoReal.limite) ? "texto-bloqueio" : undefined}>{diasDe(p)} dia(s)</strong><span className="desc">desde o recebimento</span></span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}

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
            {lote ? <CartaoLote lote={lote} /> : <p className="desc">Busque o lote pelo código, contêiner ou descrição.</p>}
            <form className="linha-form" style={{ marginBottom: 0 }} onSubmit={(e) => void procurar(e)}>
              <label>{lote ? "Trocar lote" : "Procurar lote"}<input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="L-000451, CH25K, H13 70x610…" /></label>
              <button className="secundario">Procurar</button>
            </form>
            {achados && (achados.length ? (
              <ul className="escolhas">
                {achados.map((l) => (
                  <li key={l.id}>
                    <button type="button" className="escolha-lote" style={{ width: "100%", textAlign: "left" }} onClick={() => { setLote(l); setAchados(null); }}>
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
        </>
      )}

      <LancamentoCorteItu key={rodada} op={op} megaFora={megaFora} lote={lote} previsto={previstoUrl ?? null} misto={misto}
        pecasInicial={params.get("pecas") ?? ""} pecaPendente={pecaPendente} aoGravar={() => setFeito(true)} aoRecomecar={recomecar} />
    </>
  );
}

