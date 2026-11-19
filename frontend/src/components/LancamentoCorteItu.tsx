import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, ESTOQUE_NOME, kg, num, pct, validacaoDoErro, type Ocorrencia, type Validacao } from "../api/cliente";
import PainelValidacao, { confirmacoesValidas, podeGravar, type Confirmacoes } from "./PainelValidacao";
import { diasDe, textoPeca, type PecaPesoReal } from "../api/pesoReal";

export interface LoteCorteItu { id: number; codigo: string; conteiner: string | null; liga: string; bitola: string; estoque: string; tipo: string;
  saldo_kg: number; disponivel_kg: number; codigo_mega?: number | null; formato?: string }
interface Resultado { frase?: string; perda_kg?: number; perda_esperada_kg?: number; previsto_kg?: number | null; gera_sa?: boolean; instrucao_mega?: string | null;
  perda_pct?: number; perda_max_pct?: number; perda_max_kg?: number; peso_usado_kg?: number;
  /** spec v3.5 P22(a): 8 % para material fiscal RJ em Itu, 5 % para lote do Estoque Mega */
  tolerancia_excesso_pct?: number; consumo_misto?: boolean;
  /** spec v3.13 / contrato §6.1: regra do RETO da sobra fora da bitola (null sem sobra fora da bitola) */
  regra_reto?: RegraReto | null }
interface RegraReto {
  aplicavel?: boolean; formato?: "PLACA" | "REDONDO"; limites?: { esp_limite_mm?: number; larg_max_ate_limite_mm?: number; larg_max_acima_mm?: number };
  espessura_mm?: number | null; largura_mm?: number | null; diametro_mm?: number | null;
  destino?: "RETO" | "LOTE_NOVO" | null; vai_para_reto?: boolean | null; texto_regra?: string; texto_resultado?: string; conferida?: boolean }
interface Gravado { id: number; op: number; consumo_kg: number; sobra_kg: number; perda_kg: number; lote_reto: { id: number; codigo: string } | null;
  sa_id: number | null; instrucao_mega: string | null;
  /** R058: o corte resolveu a pendência "Informar o peso real" (opcional; sem ele, vale a peça sugerida) */
  pendencia_peso_real_resolvida?: boolean;
  /** contrato §6.1: sobra fora da regra do RETO vira lote novo com a medida nova */
  lote_sobra?: { id: number; codigo: string; bitola: string } | null; sobra_destino?: "RETO" | "LOTE_NOVO" | null }

const hojeIso = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
/** Tolerância da T13 pelo lote, enquanto a API não diz: RJ em Itu 8 %, Estoque Mega 5 %. */
const limitePadrao = (l: LoteCorteItu | null) => (l?.estoque === "RJ_EM_ITU" ? 8 : 5);
const limiteDe = (pctLim: number) => (pctLim >= 8 ? "para material do RJ" : "para lote do Estoque Mega");
const mm = (v: number) => v.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
/** Ocorrências que o quadro da regra do RETO já mostra (não repetir no painel). */
const NO_QUADRO_RETO = ["REGRA_RETO_NAO_CONFERIDA", "REGRA_RETO"];

/** Frase curta com os números que a API devolveu: "Espessura 30 mm (até 50) e largura 180 mm (menor que 200): vai para RETO." */
function fraseReto(r: RegraReto): string | null {
  if (r.formato === "REDONDO" || r.aplicavel === false) {
    if (r.destino === "RETO" || r.vai_para_reto === true) return "Redondo: você escolheu RETO.";
    if (r.destino === "LOTE_NOVO" || r.vai_para_reto === false) return `Redondo: não vai para RETO; vira lote novo${r.diametro_mm ? ` Ø${mm(r.diametro_mm)}` : ""} com a medida nova.`;
    return null;
  }
  const e = r.espessura_mm, l = r.largura_mm, lim = r.limites;
  if (e == null || l == null || !lim?.esp_limite_mm || !r.destino) return null;
  const ate = e <= lim.esp_limite_mm;
  const max = ate ? lim.larg_max_ate_limite_mm : lim.larg_max_acima_mm;
  const larg = max == null ? "" : l < max ? ` (menor que ${mm(max)})` : ` (${mm(max)} ou mais)`;
  const fim = r.destino === "RETO" ? "vai para RETO" : `não vai para RETO; vira lote novo ${mm(e)}X${mm(l)} com a medida nova`;
  return `Espessura ${mm(e)} mm (${ate ? "até" : "acima de"} ${mm(lim.esp_limite_mm)}) e largura ${mm(l)} mm${larg}: ${fim}.`;
}

/** A mensagem de EXCESSO_TOLERANCIA diz o limite usado; se a API ainda não disser, a tela completa. */
function comLimite(ocs: Ocorrencia[], pctLim: number): Ocorrencia[] {
  return ocs.map((o) => {
    if (!o.codigo.startsWith("EXCESSO_TOLERANCIA") || /limite/i.test(o.mensagem)) return o;
    const lim = typeof o.dados?.limite_pct === "number" ? (o.dados.limite_pct as number) : pctLim;
    return { ...o, mensagem: `${o.mensagem} Limite: ${pct(lim)} ${limiteDe(lim)}.` };
  });
}

/**
 * Lançamento do corte em Itu (T13): consumo da OP, sobra na bitola ou RETO (com "Conferi a regra do RETO"), perda e "Fazer no Mega".
 * Usado dentro de "Pedir corte de material" quando o lote já está em Itu (2026-11-17) e na tela /corte-itu dos atalhos
 * (peça inteira aguardando peso real, lote RJ em Itu, recebimento).
 */
export default function LancamentoCorteItu({ op, megaFora, lote, previsto = null, misto = false, pecasInicial = "", pecaPendente = null,
  voltar, aoGravar, aoRecomecar, textoRecomecar = "Novo corte em Itu", aviso, botoesNoTopo = false }: {
  op: { numero: number } | null; megaFora: boolean; lote: LoteCorteItu | null; previsto?: number | null; misto?: boolean;
  pecasInicial?: string; pecaPendente?: PecaPesoReal | null; voltar?: () => void; aoGravar?: () => void;
  /** dentro de uma tela em passos: repete Voltar/Conferir/Confirmar no topo (Eduardo, 2026-11-17) */
  botoesNoTopo?: boolean;
  aoRecomecar: () => void; textoRecomecar?: string; aviso?: ReactNode;
}) {
  const [f, setF] = useState({ pecas: pecasInicial, consumo: "", sobra: "", naBitola: true, usado: "", data: hojeIso(), obs: "",
    esp: "", larg: "", diam: "", paraReto: null as boolean | null });
  const [conferiRegra, setConferiRegra] = useState(false);
  const [v, setV] = useState<Validacao<Resultado> | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [gravado, setGravado] = useState<Gravado | null>(null);
  const [copiado, setCopiado] = useState(false);

  // trocou a OP ou o lote: a conferência anterior não vale mais
  useEffect(() => { setV(null); setConferiRegra(false); }, [op?.numero, lote?.id]);
  // peças sugeridas que chegam depois (link com ?pecas=, consumo misto): só preenche se ainda estiver vazio
  useEffect(() => { if (pecasInicial) setF((x) => (x.pecas ? x : { ...x, pecas: pecasInicial })); }, [pecasInicial]);

  const mudar = (p: Partial<typeof f>) => { setF({ ...f, ...p }); setV(null); setConferiRegra(false); };
  // sobra fora da bitola passa pela regra do RETO (spec v3.13 T13, contrato §6.1)
  const redondo = lote?.formato === "REDONDO";
  // redondo nunca sai da bitola (Eduardo, 2026-11-19): a sobra fica no lote
  const sobraFora = (num(f.sobra) ?? 0) > 0 && !f.naBitola && !redondo;
  /** "45X600" → "45": a sobra fora da bitola mantém a espessura da matéria-prima inicial */
  const espessuraDoLote = /^(\d+(?:[.,]\d+)?)X/i.exec(lote?.bitola ?? "")?.[1] ?? "";
  const medidaOk = !sobraFora || (redondo
    ? f.paraReto === true || (f.paraReto === false && (num(f.diam) ?? 0) > 0)
    : (num(f.esp) ?? 0) > 0 && (num(f.larg) ?? 0) > 0);
  const regra = v?.resultado?.regra_reto ?? null;
  // o quadro da regra mostra o resultado e a caixa "Conferi a regra do RETO": o painel não repete
  const ocsPainel = v ? v.ocorrencias.filter((o) => !(sobraFora && NO_QUADRO_RETO.some((c) => o.codigo.startsWith(c))
    && (o.codigo.startsWith("REGRA_RETO_NAO_CONFERIDA") || !!regra))) : [];
  const regraPendente = sobraFora && !conferiRegra;
  const corpo = (c: Confirmacoes, conferi = conferiRegra) => ({
    op: op?.numero, lote_id: lote?.id, consumo_kg: num(f.consumo), sobra_kg: num(f.sobra) ?? 0, sobra_na_bitola: f.naBitola || redondo,
    pecas: num(f.pecas) ?? null, peso_usado_kg: num(f.usado) ?? null, previsto_kg: previsto ?? null,
    data_corte: f.data || null, observacao: f.obs.trim() || null, op_manual: megaFora ? { item_codigo: null, cliente: null } : null,
    consumo_misto: misto,
    sobra_espessura_mm: sobraFora && !redondo ? num(f.esp) ?? null : null,
    sobra_largura_mm: sobraFora && !redondo ? num(f.larg) ?? null : null,
    sobra_vai_para_reto: sobraFora && redondo ? f.paraReto : null,
    sobra_diametro_mm: sobraFora && redondo && f.paraReto === false ? num(f.diam) ?? null : null,
    conferi_regra_reto: sobraFora ? conferi : null,
    confirmacoes: c,
  });
  const pronto = !!op && !!lote && (num(f.consumo) ?? 0) > 0 && medidaOk;

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
      aoGravar?.();
    } catch (e) {
      const x = validacaoDoErro<Resultado>(e);
      if (x) setV({ ...x, resultado: x.resultado ?? v.resultado });
      else setErro(e instanceof Error ? e.message : "Não foi possível gravar.");
    } finally {
      setOcupado(false);
    }
  }

  if (gravado) {
    return (
      <section className="bloco-passo" aria-label="Corte em Itu registrado">
        <h2>Corte em Itu registrado · OP {gravado.op}</h2>
        <p className="validacao ok" role="status">
          <span>
            Consumo {kg(gravado.consumo_kg)} kg, sobra {kg(gravado.sobra_kg)} kg, perda {kg(gravado.perda_kg)} kg.
            {gravado.lote_reto && <> Novo lote RETO <strong>{gravado.lote_reto.codigo}</strong>.</>}
            {gravado.lote_sobra && <> Novo lote <strong>{gravado.lote_sobra.codigo}</strong> {gravado.lote_sobra.bitola} (sobra com a medida nova, fora do RETO).</>}
            {gravado.sa_id && <> Pedido de SA criado: <Link to="/sa">abrir SA</Link>.</>}
            {(gravado.pendencia_peso_real_resolvida ?? !!pecaPendente) && <> Peso real informado: a pendência da peça inteira saiu do Painel.</>}
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
            <p className="dica">{gravado.sobra_destino === "LOTE_NOVO"
              ? "A baixa na OP continua sendo feita no Mega. A sobra com a medida nova fica no mesmo código do Mega (sem transferência para RETO)."
              : "A baixa na OP e a transferência para o código RETO continuam sendo feitas no Mega."} A tela "Conferir estoque com o Mega" confere depois.</p>
          </section>
        )}
        <div className="botoes" style={{ marginTop: "var(--esp-4)" }}><button className="secundario" onClick={aoRecomecar}>{textoRecomecar}</button></div>
      </section>
    );
  }

  const acoes = (
    <>
      {voltar && <button className="secundario" onClick={voltar} disabled={ocupado}>Voltar</button>}
      {!v ? (
        <button className="primario" disabled={!pronto || ocupado} onClick={() => void conferir()}>{ocupado ? "Conferindo…" : "Conferir corte"}</button>
      ) : (
        <button className="primario" disabled={ocupado || regraPendente || !podeGravar(ocsPainel, conf)} onClick={() => void confirmar()}>{ocupado ? "Gravando…" : "Confirmar corte em Itu"}</button>
      )}
    </>
  );

  return (
    <>
      {botoesNoTopo && <div className="botoes botoes-topo" aria-label="Navegação dos passos">{acoes}</div>}
      <section className="painel-form" style={{ marginTop: "var(--esp-4)" }}>
        <h2>Corte</h2>
        {aviso}
        {pecaPendente && (
          <p className="validacao alerta">
            Peça inteira do RJ aguardando peso real ({textoPeca(pecaPendente)}{diasDe(pecaPendente) !== null ? `, há ${diasDe(pecaPendente)} dia(s)` : ""}).
            O consumo pesado vale para a OP e para o saldo do lote RJ em Itu; o SA e a NF ficam com o peso previsto.
          </p>
        )}
        {misto && <p className="validacao alerta">Parte de Itu de uma OP com consumo misto (Itu + RJ). A parte do RJ segue pela solicitação enviada.</p>}
        {previsto ? <p className="dica">Peso previsto: {kg(previsto)} kg. Tolerância: {pct(limitePadrao(lote))} {limiteDe(limitePadrao(lote))}.</p> : null}
        <div className="grade-form">
          <label>Peças produzidas<input inputMode="numeric" value={f.pecas} onChange={(e) => mudar({ pecas: e.target.value })} /></label>
          <label>Consumo da OP (kg, balança)<input inputMode="decimal" className="campo-grande" value={f.consumo} onChange={(e) => mudar({ consumo: e.target.value })} /></label>
          <label>Sobra (kg, balança)<input inputMode="decimal" className="campo-grande" value={f.sobra} onChange={(e) => mudar({ sobra: e.target.value })} placeholder="0" /></label>
        </div>
        {(num(f.sobra) ?? 0) > 0 && redondo && (
          <p className="dica">Redondo: a sobra continua no lote (o corte não muda o diâmetro).</p>
        )}
        {(num(f.sobra) ?? 0) > 0 && !redondo && (
          <fieldset className="formatos">
            <legend>A sobra ainda está na bitola {lote?.bitola ?? ""}?</legend>
            <label className={f.naBitola ? "opcao marcada" : "opcao"}><input type="radio" name="bitola" checked={f.naBitola} onChange={() => mudar({ naBitola: true })} />Sim, fica no lote</label>
            {/* a espessura da sobra é a da matéria-prima inicial (Eduardo, 2026-11-19): já vem preenchida */}
            <label className={!f.naBitola ? "opcao marcada" : "opcao"}><input type="radio" name="bitola" checked={!f.naBitola} onChange={() => mudar({ naBitola: false, esp: f.esp || espessuraDoLote })} />Não, mudou de medida</label>
          </fieldset>
        )}
        {sobraFora && (
          <div className="bloco-passo" aria-label="Regra do RETO">
            {redondo ? (
              <>
                <fieldset className="formatos">
                  <legend>Redondo: a sobra vai para RETO?</legend>
                  <label className={f.paraReto === true ? "opcao marcada" : "opcao"}><input type="radio" name="para-reto" checked={f.paraReto === true} onChange={() => mudar({ paraReto: true })} />Sim, vai para RETO</label>
                  <label className={f.paraReto === false ? "opcao marcada" : "opcao"}><input type="radio" name="para-reto" checked={f.paraReto === false} onChange={() => mudar({ paraReto: false })} />Não, vira lote novo</label>
                </fieldset>
                {f.paraReto === false && (
                  <div className="grade-form">
                    <label>Diâmetro da sobra (mm)<input inputMode="decimal" value={f.diam} onChange={(e) => mudar({ diam: e.target.value })} /></label>
                  </div>
                )}
                <p className="dica">No redondo a regra de espessura × largura não vale: você escolhe. O lote novo fica com o diâmetro da sobra, filho deste lote.</p>
              </>
            ) : (
              <>
                <div className="grade-form">
                  <label>Espessura da sobra (mm)<input inputMode="decimal" className="campo-grande" value={f.esp} onChange={(e) => mudar({ esp: e.target.value })} /></label>
                  <label>Largura da sobra (mm)<input inputMode="decimal" className="campo-grande" value={f.larg} onChange={(e) => mudar({ larg: e.target.value })} /></label>
                </div>
                <p className="dica">
                  {regra?.texto_regra ?? "Regra do RETO: espessura até 50 mm → largura abaixo de 200 mm; espessura acima de 50 mm → largura abaixo de 250 mm."}
                  {" "}Fora da regra, a sobra vira lote novo com a medida nova, filho deste lote. Limites na tela Parâmetros.
                </p>
              </>
            )}
            {v && regra && (
              <p className={regra.destino === "RETO" ? "validacao ok" : "validacao alerta"} role="status">
                <span>
                  <strong>{fraseReto(regra) ?? regra.texto_resultado}</strong>
                  {fraseReto(regra) && regra.texto_resultado && <><br />{regra.texto_resultado}</>}
                  {regra.destino === "LOTE_NOVO" && lote?.estoque === "ESTOQUE_MEGA" && <><br />Sem transferência para RETO no Mega: o kg continua no código {lote.codigo_mega ?? "do lote de origem"}.</>}
                </span>
              </p>
            )}
            {v && (
              <label className="marcar">
                <input type="checkbox" checked={conferiRegra} onChange={(e) => setConferiRegra(e.target.checked)} />
                <span>Conferi a regra do RETO</span>
              </label>
            )}
          </div>
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
              {v.resultado.perda_kg !== undefined && <div><dt>Perda de corte</dt><dd>{kg(v.resultado.perda_kg)} kg{v.resultado.perda_pct !== undefined && ` (${pct(v.resultado.perda_pct)} do material usado)`}</dd></div>}
              {v.resultado.perda_max_pct !== undefined && <div><dt>Perda máxima</dt><dd>{pct(v.resultado.perda_max_pct)}{v.resultado.perda_max_kg !== undefined && ` = ${kg(v.resultado.perda_max_kg)} kg`}</dd></div>}
              {v.resultado.perda_pct === undefined && v.resultado.perda_esperada_kg !== undefined && <div><dt>Perda esperada (serra)</dt><dd>{kg(v.resultado.perda_esperada_kg)} kg</dd></div>}
              {v.resultado.previsto_kg ? <div><dt>Previsto</dt><dd>{kg(v.resultado.previsto_kg)} kg</dd></div> : null}
              {v.resultado.previsto_kg ? <div><dt>Tolerância usada</dt><dd>{pct(v.resultado.tolerancia_excesso_pct ?? limitePadrao(lote))} {limiteDe(v.resultado.tolerancia_excesso_pct ?? limitePadrao(lote))}</dd></div> : null}
              {v.resultado.gera_sa !== undefined && <div><dt>Gera pedido de SA</dt><dd>{v.resultado.gera_sa ? "Sim (material fiscal RJ)" : "Não"}</dd></div>}
              {v.resultado.instrucao_mega && <div className="largo"><dt>Fazer no Mega</dt><dd>{v.resultado.instrucao_mega}</dd></div>}
            </dl>
          )}
          <PainelValidacao ocorrencias={comLimite(ocsPainel, v.resultado?.tolerancia_excesso_pct ?? limitePadrao(lote))} confirmacoes={conf} aoMudar={setConf} semOcorrencias="Dentro da tolerância." />
          {regraPendente && <p className="dica">Para confirmar, marque "Conferi a regra do RETO" no quadro da sobra.</p>}
        </div>
      )}

      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="rodape-acao">{acoes}</div>
    </>
  );
}

/** Lote escolhido (mesmo cartão em "Registrar corte em Itu" e no corte em Itu de "Pedir corte de material"). */
export function CartaoLote({ lote }: { lote: LoteCorteItu }) {
  return (
    <div className="escolha-lote marcada" style={{ cursor: "default" }}>
      <span />
      <span>
        <span className="titulo">{lote.liga} {lote.bitola} · {lote.conteiner ?? "sem contêiner"} <span className={`estoque-tag ${lote.estoque}`}>{ESTOQUE_NOME[lote.estoque] ?? lote.estoque}</span>{lote.tipo !== "ORIGINAL" && <span className="etiqueta">{lote.tipo}</span>}</span>
        <span className="linha2">{lote.codigo}{lote.estoque === "ESTOQUE_MEGA" && lote.codigo_mega ? ` · código Mega ${lote.codigo_mega}` : ""}</span>
      </span>
      <span className="kg"><strong>{kg(lote.saldo_kg)} kg</strong><span className="desc">saldo</span></span>
    </div>
  );
}
