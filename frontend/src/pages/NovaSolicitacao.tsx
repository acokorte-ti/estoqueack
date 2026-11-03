import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, data, ErroApi, ESTOQUE_NOME, kg, num, qs, validacaoDoErro, type Validacao } from "../api/cliente";
import PainelValidacao, { confirmacoesValidas, podeGravar, type Confirmacoes } from "../components/PainelValidacao";

/* ------------------------------------------------------------------ tipos da API */

interface ComponenteOp { codigo: number; descricao: string; tipo: "SA" | "MP" | "OUTRO"; um: string | null;
  qtd_necessaria: number | null; qtd_unitaria: number | null; qtd_requisitada: number | null }
interface OpMega {
  numero: number; item_codigo: number | null; item_descricao: string | null;
  cliente: string | null; cliente_codigo: number | null; pedido: string | null; tipo: string | null;
  situacao: string | null; situacao_descricao: string | null; aberta: boolean | null;
  quantidade: number | null; data_recebimento: string | null;
  medida_sugerida: { formato: Formato; espessura: number | null; largura: number | null; diametro: number | null; comprimento: number | null } | null;
  estrutura: ComponenteOp[] | null;
}
type Formato = "RETANGULAR" | "REDONDO";
interface Liga { codigo: string; nome: string; ativo: boolean }
interface LoteCompativel {
  id: number; codigo: string; conteiner: string | null; liga: string; formato: string; bitola: string; descricao: string;
  estoque: string; tipo: string; saldo_kg: number; reservado_kg: number; disponivel_kg: number;
  peso_previsto_kg: number | null; peso_peca_kg: number | null; sobremetal_pct: number | null;
  liga_equivalente?: boolean; substituido_por_id?: number | null;
  indicadores?: { destinacao?: boolean; nota?: boolean; origem_nao_identificada?: boolean };
}
type Modo = "CORTAR_RJ" | "TRAZER_INTEIRA";
interface Efeito { lote: string; lote_id: number; material: string; conteiner: string | null; modo: Modo; quantidade: number;
  bruto: { espessura: number | null; largura: number | null; diametro: number | null; comprimento: number | null };
  comprimento_corte_mm: number | null; peso_peca_kg: number | null; peso_previsto_kg: number | null;
  sobremetal_pct: number | null; instrucao: string; saldo_kg: number }
interface ResultadoSolic { frase: string; efeitos: Efeito[]; op?: { pedido?: string | null; cliente?: string | null } }
interface Gravado { solicitacoes: { id: number; numero: string; situacao: string; lote?: { codigo: string } }[] }

interface ItemCorte {
  lote: LoteCompativel;
  modo: Modo;
  quantidade: string;
  sobremetal_c: string;
  sobremetal_l: string;
  bruto: { espessura: string; largura: string; diametro: string; comprimento: string };
  comprimento_barra: string;
  instrucao: string;
  instrucao_processo: string;
}

const PASSOS = ["OP", "Lote", "Corte", "Revisão"];
const PROCESSOS = ["Retificar espessura", "Retificar largura", "Peça bipartida", "Usar sobras"];
const emItu = (l: LoteCompativel) => l.estoque !== "RJ_NO_RIO";
const n2s = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v).replace(".", ","));
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} %`);
const SITUACAO_BLOQUEIA = ["EN", "CA"]; // Encerrada / Cancelada (R026)

/* ------------------------------------------------------------------ tela */

export default function NovaSolicitacao() {
  const [passo, setPasso] = useState(1);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);

  // passo 1
  const [opNum, setOpNum] = useState("");
  const [op, setOp] = useState<OpMega | null>(null);
  const [megaFora, setMegaFora] = useState(false);
  const [opManual, setOpManual] = useState({ item_codigo: "", item_descricao: "", cliente: "" });
  const [ligas, setLigas] = useState<Liga[]>([]);
  const [liga, setLiga] = useState("");
  const [medida, setMedida] = useState({ formato: "RETANGULAR" as Formato, espessura: "", largura: "", diametro: "", comprimento: "" });
  const [medidaSugerida, setMedidaSugerida] = useState(false);

  // passo 2 e 3
  const [lotes, setLotes] = useState<LoteCompativel[] | null>(null);
  const [itens, setItens] = useState<ItemCorte[]>([]);
  const [prazo, setPrazo] = useState("");
  const [observacao, setObservacao] = useState("");

  // passo 4
  const [validacao, setValidacao] = useState<Validacao<ResultadoSolic> | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [gravado, setGravado] = useState<{ enviada: boolean; r: Gravado } | null>(null);

  useEffect(() => {
    api.get<Liga[]>("/ligas").then((l) => setLigas(l.filter((x) => x.ativo))).catch(() => setLigas([]));
  }, []);

  const quantidadeOp = op?.quantidade ? String(op.quantidade) : "";
  const itu = itens.length === 1 && emItu(itens[0].lote);

  /* ---------- passo 1: OP ---------- */
  async function buscarOp(e: FormEvent) {
    e.preventDefault();
    setErro("");
    setOp(null);
    setMegaFora(false);
    const n = Number(opNum.trim());
    if (!Number.isInteger(n) || n <= 0) return setErro("Digite o número da OP (só números).");
    setOcupado(true);
    try {
      const r = await api.get<OpMega>(`/mega/op/${n}`);
      setOp(r);
      if (r.medida_sugerida) {
        const m = r.medida_sugerida;
        setMedida({ formato: m.formato, espessura: n2s(m.espessura), largura: n2s(m.largura), diametro: n2s(m.diametro), comprimento: n2s(m.comprimento) });
        setMedidaSugerida(true);
      } else setMedidaSugerida(false);
      if (r.data_recebimento) setPrazo(r.data_recebimento);
      // sugere a liga quando a MP da estrutura cita uma liga cadastrada (só sugestão, editável)
      const mp = r.estrutura?.find((c) => c.tipo === "MP")?.descricao?.toUpperCase() ?? "";
      const achada = ligas.find((l) => new RegExp(`(^|[^A-Z0-9.])${l.codigo.replace(".", "\\.")}([^A-Z0-9]|$)`).test(mp));
      if (achada && !liga) setLiga(achada.codigo);
    } catch (err) {
      if (err instanceof ErroApi && err.status === 503) {
        setMegaFora(true);
        setOp({ numero: n, item_codigo: null, item_descricao: null, cliente: null, cliente_codigo: null, pedido: null, tipo: null,
          situacao: null, situacao_descricao: null, aberta: null, quantidade: null, data_recebimento: null, medida_sugerida: null, estrutura: null });
      } else setErro(err instanceof Error ? err.message : "Não foi possível consultar a OP.");
    } finally {
      setOcupado(false);
    }
  }

  const opBloqueada = !!op?.situacao && SITUACAO_BLOQUEIA.includes(op.situacao);
  const medidaOk =
    medida.comprimento.trim() !== "" &&
    (medida.formato === "RETANGULAR" ? medida.espessura.trim() !== "" && medida.largura.trim() !== "" : medida.diametro.trim() !== "");
  const passo1Ok = !!op && !opBloqueada && !!liga && medidaOk &&
    (!megaFora || (opManual.item_codigo.trim() !== "" && opManual.item_descricao.trim() !== ""));

  /* ---------- passo 2: lotes compatíveis ---------- */
  async function irParaLotes() {
    setErro("");
    setOcupado(true);
    try {
      const r = await api.get<LoteCompativel[] | { itens: LoteCompativel[] }>(
        `/lotes/compativeis${qs({
          liga, formato: medida.formato,
          espessura: num(medida.espessura), largura: num(medida.largura), diametro: num(medida.diametro),
          comprimento: num(medida.comprimento), quantidade: num(quantidadeOp) ?? 1,
        })}`,
      );
      setLotes(Array.isArray(r) ? r : r.itens);
      setPasso(2);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível buscar os lotes.");
    } finally {
      setOcupado(false);
    }
  }

  function novoItem(l: LoteCompativel): ItemCorte {
    return { lote: l, modo: "CORTAR_RJ", quantidade: quantidadeOp, sobremetal_c: "5", sobremetal_l: "",
      bruto: { espessura: "", largura: "", diametro: "", comprimento: "" }, comprimento_barra: "", instrucao: "", instrucao_processo: "" };
  }

  function alternarLote(l: LoteCompativel) {
    const ja = itens.find((i) => i.lote.id === l.id);
    if (ja) return setItens(itens.filter((i) => i.lote.id !== l.id));
    // lote em Itu vai sozinho (corte em Itu, sem solicitação); lotes do RJ podem ser vários
    if (emItu(l)) return setItens([novoItem(l)]);
    setItens([...itens.filter((i) => !emItu(i.lote)), novoItem(l)]);
  }

  const mudarItem = (id: number, p: Partial<ItemCorte>) => setItens(itens.map((i) => (i.lote.id === id ? { ...i, ...p } : i)));

  /* ---------- passos 3/4: validar e gravar ---------- */
  function corpo(enviar: boolean, confirmacoes: Confirmacoes) {
    return {
      op: op?.numero, liga,
      medida: { formato: medida.formato, espessura: num(medida.espessura) ?? null, largura: num(medida.largura) ?? null,
        diametro: num(medida.diametro) ?? null, comprimento: num(medida.comprimento) ?? null },
      itens: itens.map((i) => {
        const b = i.bruto;
        const temBruto = Object.values(b).some((v) => v.trim() !== "");
        return {
          lote_id: i.lote.id, modo: i.modo, quantidade: num(i.quantidade) ?? null,
          sobremetal_comprimento_mm: num(i.sobremetal_c) ?? null, sobremetal_largura_mm: num(i.sobremetal_l) ?? null,
          bruto: temBruto ? { espessura: num(b.espessura) ?? null, largura: num(b.largura) ?? null, diametro: num(b.diametro) ?? null, comprimento: num(b.comprimento) ?? null } : null,
          comprimento_barra_mm: i.modo === "TRAZER_INTEIRA" ? num(i.comprimento_barra) ?? null : null,
          instrucao: i.instrucao.trim() || null, instrucao_processo: i.instrucao_processo.trim() || null,
        };
      }),
      prazo: prazo || null, observacao: observacao.trim() || null,
      op_manual: megaFora ? { item_codigo: num(opManual.item_codigo) ?? null, item_descricao: opManual.item_descricao.trim(), cliente: opManual.cliente.trim() || null } : null,
      enviar, confirmacoes,
    };
  }

  async function revisar() {
    setErro("");
    setOcupado(true);
    try {
      const v = await api.post<Validacao<ResultadoSolic>>("/solicitacoes/validar", corpo(true, {}));
      setValidacao(v);
      setPasso(4);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível validar a solicitação.");
    } finally {
      setOcupado(false);
    }
  }

  async function gravar(enviar: boolean) {
    setErro("");
    setOcupado(true);
    try {
      const c = validacao ? confirmacoesValidas(validacao.ocorrencias, conf) : {};
      const r = await api.post<Gravado>("/solicitacoes", corpo(enviar, c));
      setGravado({ enviada: enviar, r });
    } catch (err) {
      const v = validacaoDoErro<ResultadoSolic>(err);
      if (v) setValidacao({ ...v, resultado: v.resultado ?? validacao?.resultado ?? null });
      else setErro(err instanceof Error ? err.message : "Não foi possível gravar.");
    } finally {
      setOcupado(false);
    }
  }

  function recomecar() {
    setPasso(1); setOp(null); setOpNum(""); setMegaFora(false); setLotes(null); setItens([]); setValidacao(null);
    setConf({}); setGravado(null); setErro(""); setObservacao(""); setPrazo("");
  }

  const liberaEnviar = !!validacao && podeGravar(validacao.ocorrencias, conf);
  const temErro = !!validacao?.ocorrencias.some((o) => o.nivel === "ERRO");

  /* ---------- tela de sucesso ---------- */
  if (gravado) {
    return (
      <>
        <header className="cabecalho"><h1>Nova solicitação de corte</h1></header>
        <div className="ficha">
          <p className="validacao ok" role="status">
            {gravado.enviada ? "Enviada ao RJ. O peso previsto ficou reservado no lote e o Marcelo foi avisado." : "Rascunho salvo. Nada foi reservado ainda."}
          </p>
          <ul>
            {gravado.r.solicitacoes.map((s) => (
              <li key={s.id}><Link to={`/solicitacoes/${s.id}`}><strong>{s.numero}</strong></Link>{s.lote ? `, lote ${s.lote.codigo}` : ""}</li>
            ))}
          </ul>
          <div className="botoes">
            <button className="primario" onClick={recomecar}>Nova solicitação</button>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <header className="cabecalho">
        <h1>Nova solicitação de corte</h1>
        <p>Digite a OP, escolha o lote e confira o corte antes de enviar ao RJ.</p>
      </header>

      <ol className="passos" aria-label="Passos">
        {PASSOS.map((p, i) => (
          <li key={p} aria-current={passo === i + 1 ? "step" : undefined} className={passo > i + 1 ? "feito" : ""}>
            <span className="n" aria-hidden="true">{passo > i + 1 ? "✓" : i + 1}</span>{p}
          </li>
        ))}
      </ol>

      {erro && <p className="erro" role="alert">{erro}</p>}

      {/* ============ PASSO 1 ============ */}
      {passo === 1 && (
        <div className="bloco-passo">
          <form className="painel-form linha-form" onSubmit={buscarOp}>
            <label>
              Nº da OP
              <input inputMode="numeric" autoFocus value={opNum} onChange={(e) => setOpNum(e.target.value)} placeholder="100592" required />
            </label>
            <button className="secundario" disabled={ocupado}>{ocupado ? "Buscando…" : "Buscar OP"}</button>
          </form>

          {op && <FichaOp op={op} megaFora={megaFora} bloqueada={opBloqueada} />}

          {op && megaFora && (
            <div className="painel-form">
              <h2>Dados da OP (digitados)</h2>
              <p className="dica">O Mega não respondeu. Os dados ficam marcados como "não confirmados no Mega" e são conferidos depois.</p>
              <div className="grade-form">
                <label>Código do item<input inputMode="numeric" value={opManual.item_codigo} onChange={(e) => setOpManual({ ...opManual, item_codigo: e.target.value })} required /></label>
                <label>Descrição do item<input value={opManual.item_descricao} onChange={(e) => setOpManual({ ...opManual, item_descricao: e.target.value })} required /></label>
                <label>Cliente<input value={opManual.cliente} onChange={(e) => setOpManual({ ...opManual, cliente: e.target.value })} /></label>
              </div>
            </div>
          )}

          {op && !opBloqueada && (
            <div className="painel-form">
              <h2>Peça acabada</h2>
              <div className="grade-form">
                <label>
                  Liga
                  <select value={liga} onChange={(e) => setLiga(e.target.value)} required>
                    <option value="">Escolha a liga</option>
                    {ligas.map((l) => <option key={l.codigo} value={l.codigo}>{l.codigo}</option>)}
                  </select>
                </label>
              </div>
              <fieldset className="formatos">
                <legend>Formato {medidaSugerida && <span className="sugerido">sugerido pela descrição do item</span>}</legend>
                {(["RETANGULAR", "REDONDO"] as Formato[]).map((f) => (
                  <label key={f} className={medida.formato === f ? "opcao marcada" : "opcao"}>
                    <input type="radio" name="formato" checked={medida.formato === f} onChange={() => setMedida({ ...medida, formato: f })} />
                    {f === "RETANGULAR" ? "Retangular (E × L × C)" : "Redondo (Ø × C)"}
                  </label>
                ))}
              </fieldset>
              <div className="grade-medidas">
                {medida.formato === "RETANGULAR" ? (
                  <>
                    <label>Espessura (mm)<input inputMode="decimal" value={medida.espessura} onChange={(e) => setMedida({ ...medida, espessura: e.target.value })} /></label>
                    <label>Largura (mm)<input inputMode="decimal" value={medida.largura} onChange={(e) => setMedida({ ...medida, largura: e.target.value })} /></label>
                  </>
                ) : (
                  <label>Diâmetro (mm)<input inputMode="decimal" value={medida.diametro} onChange={(e) => setMedida({ ...medida, diametro: e.target.value })} /></label>
                )}
                <label>Comprimento (mm)<input inputMode="decimal" value={medida.comprimento} onChange={(e) => setMedida({ ...medida, comprimento: e.target.value })} /></label>
              </div>
            </div>
          )}

          <div className="botoes">
            <button className="primario" disabled={!passo1Ok || ocupado} onClick={() => void irParaLotes()}>
              {ocupado ? "Buscando lotes…" : "Continuar: escolher lote"}
            </button>
          </div>
        </div>
      )}

      {/* ============ PASSO 2 ============ */}
      {passo === 2 && lotes && (
        <div className="bloco-passo">
          <p className="dica">
            Lotes de {liga} (e ligas equivalentes) que comportam {medida.formato === "RETANGULAR" ? `${medida.espessura} × ${medida.largura}` : `Ø ${medida.diametro}`} × {medida.comprimento} mm,
            do menor sobremetal para o maior. Para usar mais de um lote do RJ na mesma OP, marque os dois. Lote em Itu vai sozinho.
          </p>
          {!lotes.length ? (
            <div className="estado-vazio">
              <strong>Nenhum lote compatível com saldo disponível</strong>
              Confira a liga e a medida, ou consulte o estoque.
            </div>
          ) : (
            <ul className="escolhas">
              {lotes.map((l) => {
                const marcado = itens.some((i) => i.lote.id === l.id);
                return (
                  <li key={l.id}>
                    <label className={marcado ? "escolha-lote marcada" : "escolha-lote"}>
                      <input type="checkbox" checked={marcado} onChange={() => alternarLote(l)} />
                      <span>
                        <span className="titulo">
                          {l.liga} {l.bitola} · {l.conteiner ?? "sem contêiner"}
                          <span className={`estoque-tag ${l.estoque}`}>{ESTOQUE_NOME[l.estoque] ?? l.estoque}</span>
                          {l.liga_equivalente && <span className="etiqueta atencao">liga equivalente</span>}
                          {l.indicadores?.destinacao && <span className="etiqueta atencao">reserva/restrição</span>}
                          {l.substituido_por_id && <span className="etiqueta info">item substituído</span>}
                          {l.tipo !== "ORIGINAL" && <span className="etiqueta">{l.tipo}</span>}
                        </span>
                        <span className="linha2">
                          {l.codigo} · sobremetal {pct(l.sobremetal_pct)} · previsto {l.peso_previsto_kg !== null ? `${kg(l.peso_previsto_kg)} kg` : "—"}
                        </span>
                      </span>
                      <span className="kg"><strong className="numero">{kg(l.disponivel_kg)} kg</strong><span className="desc">disponível</span></span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
          <div className="botoes">
            <button className="primario" disabled={!itens.length} onClick={() => setPasso(3)}>Continuar: dados do corte</button>
            <button className="secundario" onClick={() => setPasso(1)}>Voltar</button>
          </div>
        </div>
      )}

      {/* ============ PASSO 3 ============ */}
      {passo === 3 && (
        <div className="bloco-passo">
          {itu ? (
            <div className="ficha">
              <h2>Corte em Itu</h2>
              <p>
                O lote <strong>{itens[0].lote.codigo}</strong> ({itens[0].lote.liga} {itens[0].lote.bitola}) já está em Itu. Não se cria solicitação
                nem reserva: o corte é lançado direto no "Corte em Itu", com a OP, o lote e o peso previsto preenchidos.
              </p>
              <div className="botoes">
                <Link
                  className="primario"
                  to={`/corte-itu${qs({ op: op?.numero, lote_id: itens[0].lote.id, previsto: itens[0].lote.peso_previsto_kg ?? undefined })}`}
                >
                  Registrar corte em Itu agora
                </Link>
                <button className="secundario" onClick={() => setPasso(2)}>Voltar</button>
              </div>
            </div>
          ) : (
            <>
              {itens.map((i) => (
                <ItemCorteForm key={i.lote.id} item={i} formato={medida.formato} aoMudar={(p) => mudarItem(i.lote.id, p)} />
              ))}
              <div className="painel-form">
                <div className="grade-form">
                  <label>
                    <span className="rotulo">Prazo {op?.data_recebimento && prazo === op.data_recebimento && <span className="sugerido">entrega da OP</span>}</span>
                    <input type="date" value={prazo} onChange={(e) => setPrazo(e.target.value)} />
                  </label>
                  <label>
                    Observação
                    <input value={observacao} onChange={(e) => setObservacao(e.target.value)} />
                  </label>
                </div>
              </div>
              <div className="botoes">
                <button className="primario" disabled={ocupado || itens.some((i) => !num(i.quantidade))} onClick={() => void revisar()}>
                  {ocupado ? "Calculando…" : "Continuar: revisar"}
                </button>
                <button className="secundario" onClick={() => setPasso(2)}>Voltar</button>
              </div>
            </>
          )}
        </div>
      )}

      {/* ============ PASSO 4 ============ */}
      {passo === 4 && validacao && (
        <div className="bloco-passo">
          {validacao.resultado?.frase && <p className="frase-resultado resultado-frase">{validacao.resultado.frase}</p>}
          {!!validacao.resultado?.efeitos?.length && <TabelaEfeitos efeitos={validacao.resultado.efeitos} />}
          <PainelValidacao ocorrencias={validacao.ocorrencias} confirmacoes={conf} aoMudar={setConf} semOcorrencias="Tudo certo. Pode enviar ao RJ." />
          <div className="rodape-acao">
            {temErro && <span className="resultado-frase">Corrija os itens em vermelho para enviar.</span>}
            <button className="secundario" onClick={() => setPasso(3)} disabled={ocupado}>Voltar</button>
            <button className="secundario" onClick={() => void gravar(false)} disabled={ocupado}>Salvar rascunho</button>
            <button className="primario" onClick={() => void gravar(true)} disabled={ocupado || !liberaEnviar}>
              {ocupado ? "Enviando…" : "Enviar ao RJ"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ partes */

function FichaOp({ op, megaFora, bloqueada }: { op: OpMega; megaFora: boolean; bloqueada: boolean }) {
  if (megaFora) {
    return <p className="validacao alerta">OP {op.numero}: o Mega não respondeu agora. Você pode digitar os dados da OP abaixo e seguir.</p>;
  }
  const naoAberta = !bloqueada && op.situacao !== null && op.situacao !== "AB";
  const sit = op.situacao_descricao ?? op.situacao ?? "—";
  return (
    <section className="ficha" aria-label={`OP ${op.numero}`}>
      <h2>OP {op.numero}</h2>
      {bloqueada && <p className="validacao erro">OP {sit.toLowerCase()} no Mega. Não é possível pedir corte para ela.</p>}
      {naoAberta && <p className="validacao alerta">OP ainda não aberta no Mega ({sit}). Dá para seguir; confira antes de enviar.</p>}
      <dl className="dados">
        <div className="largo"><dt>Item</dt><dd>{op.item_codigo ?? "—"} · {op.item_descricao ?? "—"}</dd></div>
        <div><dt>Cliente</dt><dd>{op.cliente ?? "—"}</dd></div>
        <div><dt>Pedido</dt><dd>{op.pedido ?? "—"}</dd></div>
        <div><dt>Tipo</dt><dd>{op.tipo ?? "—"}</dd></div>
        <div>
          <dt>Situação</dt>
          <dd><span className={`etiqueta ${bloqueada ? "ruim" : naoAberta ? "atencao" : "ok"}`}>{sit}</span></dd>
        </div>
        <div><dt>Quantidade</dt><dd>{op.quantidade ?? "—"}</dd></div>
        <div><dt>Entrega</dt><dd>{data(op.data_recebimento)}</dd></div>
      </dl>
      <details className="avancado">
        <summary>Estrutura da OP no Mega (só informativo)</summary>
        {op.estrutura === null ? (
          <p className="dica">Não foi possível ler a estrutura no Mega agora.</p>
        ) : !op.estrutura.length ? (
          <p className="dica">A OP não tem componentes na estrutura.</p>
        ) : (
          <div className="tabela-rolagem">
            <table className="tabela">
              <thead><tr><th>Tipo</th><th>Código</th><th>Descrição</th><th className="num">Necessária</th><th className="num">Requisitada</th><th>UM</th></tr></thead>
              <tbody>
                {op.estrutura.map((c) => (
                  <tr key={`${c.tipo}-${c.codigo}`}>
                    <td><span className={`etiqueta ${c.tipo === "SA" ? "info" : ""}`}>{c.tipo}</span></td>
                    <td>{c.codigo}</td>
                    <td>{c.descricao}</td>
                    <td className="num">{c.qtd_necessaria?.toLocaleString("pt-BR") ?? "—"}</td>
                    <td className="num">{c.qtd_requisitada?.toLocaleString("pt-BR") ?? "—"}</td>
                    <td>{c.um ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="dica">A MP prevista na estrutura geralmente não é a que será usada. O SA aparece aqui quando a OP é de material RJ.</p>
          </div>
        )}
      </details>
    </section>
  );
}

function ItemCorteForm({ item, formato, aoMudar }: { item: ItemCorte; formato: Formato; aoMudar: (p: Partial<ItemCorte>) => void }) {
  const l = item.lote;
  const b = item.bruto;
  return (
    <section className="painel-form" aria-label={`Corte do lote ${l.codigo}`}>
      <h2>{l.liga} {l.bitola} · {l.conteiner ?? "sem contêiner"} <span className="desc">({l.codigo})</span></h2>
      <fieldset className="formatos">
        <legend>Modo</legend>
        {(["CORTAR_RJ", "TRAZER_INTEIRA"] as Modo[]).map((m) => (
          <label key={m} className={item.modo === m ? "opcao marcada" : "opcao"}>
            <input type="radio" name={`modo-${l.id}`} checked={item.modo === m} onChange={() => aoMudar({ modo: m })} />
            {m === "CORTAR_RJ" ? "Cortar no RJ" : "Trazer peça inteira"}
          </label>
        ))}
      </fieldset>
      <div className="grade-form">
        <label>
          Quantidade de peças
          <input inputMode="numeric" value={item.quantidade} onChange={(e) => aoMudar({ quantidade: e.target.value })} required />
        </label>
        <label>
          <span className="rotulo">Sobremetal no comprimento (mm) <span className="sugerido">sugerido</span></span>
          <input inputMode="decimal" value={item.sobremetal_c} onChange={(e) => aoMudar({ sobremetal_c: e.target.value })} />
        </label>
        {formato === "RETANGULAR" && (
          <label>
            Sobremetal na largura (mm)
            <input inputMode="decimal" value={item.sobremetal_l} onChange={(e) => aoMudar({ sobremetal_l: e.target.value })} placeholder="automático" />
            <small className="dica">Em branco: 0 se a peça usa a largura inteira da barra, senão 5.</small>
          </label>
        )}
        {item.modo === "TRAZER_INTEIRA" && (
          <label>
            Comprimento da barra (mm), opcional
            <input inputMode="decimal" value={item.comprimento_barra} onChange={(e) => aoMudar({ comprimento_barra: e.target.value })} />
          </label>
        )}
      </div>
      <div>
        <p className="dica" style={{ marginBottom: 6 }}>Instrução de processo</p>
        <div className="chips">
          {PROCESSOS.map((p) => (
            <button key={p} type="button" className="chip" aria-pressed={item.instrucao_processo === p}
              onClick={() => aoMudar({ instrucao_processo: item.instrucao_processo === p ? "" : p })}>{p}</button>
          ))}
        </div>
      </div>
      <details className="avancado">
        <summary>Ajustar dimensões brutas ou instrução para o RJ</summary>
        <p className="dica">Em branco, o sistema calcula: bitola + sobremetal. A revisão mostra o resultado.</p>
        <div className="grade-medidas">
          {formato === "RETANGULAR" ? (
            <>
              <label>Espessura bruta<input inputMode="decimal" value={b.espessura} onChange={(e) => aoMudar({ bruto: { ...b, espessura: e.target.value } })} /></label>
              <label>Largura bruta<input inputMode="decimal" value={b.largura} onChange={(e) => aoMudar({ bruto: { ...b, largura: e.target.value } })} /></label>
            </>
          ) : (
            <label>Diâmetro bruto<input inputMode="decimal" value={b.diametro} onChange={(e) => aoMudar({ bruto: { ...b, diametro: e.target.value } })} /></label>
          )}
          <label>Comprimento de corte<input inputMode="decimal" value={b.comprimento} onChange={(e) => aoMudar({ bruto: { ...b, comprimento: e.target.value } })} /></label>
        </div>
        <label>
          Instrução para o RJ
          <input value={item.instrucao} onChange={(e) => aoMudar({ instrucao: e.target.value })} placeholder="automática, ex.: 12 PEÇAS COM 255MM COMPRIMENTO" />
        </label>
        <label>
          Outra instrução de processo
          <input value={PROCESSOS.includes(item.instrucao_processo) ? "" : item.instrucao_processo} onChange={(e) => aoMudar({ instrucao_processo: e.target.value })} />
        </label>
      </details>
    </section>
  );
}

function TabelaEfeitos({ efeitos }: { efeitos: Efeito[] }) {
  const medidas = (e: Efeito) => {
    const br = e.bruto;
    return br.diametro ? `Ø ${br.diametro} × ${br.comprimento}` : `${br.espessura} × ${br.largura} × ${br.comprimento}`;
  };
  const total = useMemo(() => efeitos.reduce((s, e) => s + (e.peso_previsto_kg ?? 0), 0), [efeitos]);
  return (
    <div className="tabela-rolagem">
      <table className="tabela">
        <thead>
          <tr><th>Lote</th><th>Modo</th><th className="num">Peças</th><th>Bruto (mm)</th><th className="num">Peso previsto</th><th className="num">Sobremetal</th><th>Instrução para o RJ</th></tr>
        </thead>
        <tbody>
          {efeitos.map((e) => (
            <tr key={e.lote_id}>
              <td><strong>{e.material}</strong><br /><span className="desc">{e.lote} · {e.conteiner ?? "—"}</span></td>
              <td>{e.modo === "CORTAR_RJ" ? "Cortar no RJ" : "Peça inteira"}</td>
              <td className="num">{e.quantidade}</td>
              <td>{medidas(e)}</td>
              <td className="num"><strong>{e.peso_previsto_kg !== null ? `${kg(e.peso_previsto_kg)} kg` : "—"}</strong></td>
              <td className="num">{pct(e.sobremetal_pct)}</td>
              <td>{e.instrucao}</td>
            </tr>
          ))}
        </tbody>
        {efeitos.length > 1 && (
          <tfoot><tr><td colSpan={4}><strong>Total reservado</strong></td><td className="num"><strong>{kg(total)} kg</strong></td><td colSpan={2} /></tr></tfoot>
        )}
      </table>
    </div>
  );
}
