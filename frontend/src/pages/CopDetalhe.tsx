import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, data, kg, num, reais, rsKg, validacaoDoErro, type Ocorrencia, type Validacao } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { EMITENTES_LANCAMENTO, faltasNf, nfTexto, nomeEmitente, SA_ITEM, SITUACAO_COP, temPrecificador, type Cop, type CopItem, type CortePronto } from "../api/cop";
import { MODO_NOME } from "../api/solicitacao";
import Janela, { fecharJanela } from "../components/Janela";
import PainelValidacao, { confirmacoesValidas, JUSTIFICATIVA_MIN, podeGravar, type Confirmacoes } from "../components/PainelValidacao";

const ETAPAS = ["Montar", "Fechar", "SA e precificador em Itu", "NF", "Enviar", "Recebido"];
function etapa(c: Cop): number {
  if (c.situacao === "ABERTO") return 0;
  if (c.situacao === "FECHADO") return 2;
  if (c.situacao === "AGUARDANDO_NF") return 3;
  if (c.situacao === "ENVIADO" || c.situacao === "RECEBIDO_PARCIAL") return 4;
  return 5;
}

/** T11: COP aberto, fechado ou enviado. Dois botões principais: "Fechar COP" (gera os SAs) e "Enviar" (SA + NF). */
export default function CopDetalhe() {
  const { id } = useParams();
  const { usuario } = useSessao();
  const monta = usuario?.perfil === "OPERACAO_RJ" || usuario?.perfil === "ADMIN";
  const [c, setC] = useState<Cop | null>(null);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [sel, setSel] = useState<number[]>([]);
  const [janela, setJanela] = useState<null | "adicionar" | "fechar" | "nf" | "reabrir" | "enviar" | "excluir">(null);
  const [editando, setEditando] = useState<CopItem | null>(null);
  const nav = useNavigate();

  const carregar = useCallback(() => api.get<Cop>(`/cops/${id}`).then(setC).catch((e: Error) => setErro(e.message)), [id]);
  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function remover(itemId: number) {
    setErro("");
    try {
      setC(await api.delete<Cop>(`/cops/${id}/itens/${itemId}`));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível remover o item.");
    }
  }

  const feito = (msg: string) => { setJanela(null); setSel([]); setAviso(msg); void carregar(); };

  if (!c) return erro ? <p className="erro" role="alert">{erro}</p> : <p className="carregando">Carregando…</p>;

  const itens = c.itens ?? [];
  const aberto = c.situacao === "ABERTO";
  const fechado = c.situacao === "FECHADO" || c.situacao === "AGUARDANDO_NF";
  const saOk = itens.filter((i) => i.sa?.situacao === "CONFIRMADO").length;
  const comNf = itens.filter((i) => i.nf).length;
  const comRs = itens.filter(temPrecificador).length;
  // spec v3.16 T11: a NF só libera com SA confirmado e R$/kg em todos os itens (ou em todos os selecionados)
  const faltam = faltasNf(sel.length ? itens.filter((i) => sel.includes(i.id)) : itens);
  const nfLiberada = !faltam.sa && !faltam.rs;
  const motivoNf = nfLiberada ? "" : `Falta ${[faltam.sa ? `SA confirmado em ${faltam.sa} item(ns)` : "", faltam.rs ? `R$/kg do precificador em ${faltam.rs} item(ns)` : ""].filter(Boolean).join(" e ")} (Cadastro de SA, em Itu).`;
  const e = etapa(c);
  // spec v3.23 T11: "Excluir COP" para quem abriu o COP e para o Admin, antes do envio e sem SA confirmado
  const autor = !!usuario && c.criado_por_id !== null && c.criado_por_id !== undefined && c.criado_por_id === usuario.id;
  const podeExcluir = (autor || usuario?.perfil === "ADMIN") && (c.situacao === "ABERTO" || c.situacao === "FECHADO") && saOk === 0 && comNf === 0;

  return (
    <>
      <p><Link to="/cops">← COPs</Link></p>
      <header className="cabecalho cabecalho-acao">
        <div>
          <h1>COP nº {c.numero}</h1>
          <p>
            <span className={`etiqueta ${SITUACAO_COP[c.situacao]?.classe ?? ""}`}>{SITUACAO_COP[c.situacao]?.nome ?? c.situacao}</span>{" "}
            {c.qtd_itens} item(ns) · {kg(c.peso_total_kg)} kg
            {c.enviado_em && ` · enviado em ${data(c.enviado_em)}`}
            {c.criado_por && ` · aberto por ${c.criado_por}`}
          </p>
        </div>
        {monta && aberto && <button className="primario" disabled={!itens.length} onClick={() => setJanela("fechar")}>Fechar COP</button>}
        {monta && fechado && <button className="primario" onClick={() => setJanela("enviar")}>Enviar</button>}
      </header>

      <ol className="passos" aria-label="Etapas do COP">
        {ETAPAS.map((n, i) => (
          <li key={n} aria-current={i === e ? "step" : undefined} className={i < e ? "feito" : ""}>
            <span className="n" aria-hidden="true">{i < e ? "✓" : i + 1}</span>{n}
          </li>
        ))}
      </ol>

      {erro && <p className="erro" role="alert">{erro}</p>}
      {aviso && <p className="validacao ok" role="status">{aviso}</p>}
      {fechado && (
        <p className={saOk === itens.length && comRs === itens.length && comNf === itens.length ? "validacao ok" : "validacao alerta"}>
          <span>
            SAs confirmados em Itu: <strong>{saOk} de {itens.length}</strong> · R$/kg do precificador: <strong>{comRs} de {itens.length}</strong> · NF informada: <strong>{comNf} de {itens.length}</strong>.
            {(saOk < itens.length || comRs < itens.length) && " Itu está fazendo os SAs e o precificador a partir deste COP; a NF libera quando os dois estiverem prontos."}
            {saOk === itens.length && comRs === itens.length && comNf < itens.length && " Informe a NF de transferência."}
          </span>
        </p>
      )}

      {monta && (aberto || fechado) && (
        <div className="barra-acoes">
          <span className="contagem">{sel.length ? `${sel.length} item(ns) selecionado(s)` : ""}</span>
          {aberto && <button className="secundario" onClick={() => setJanela("adicionar")}>Adicionar cortes prontos</button>}
          {fechado && (
            <button className="secundario" disabled={!nfLiberada} title={motivoNf || undefined} onClick={() => setJanela("nf")}>
              {sel.length ? "NF diferente para itens selecionados" : "Informar NF"}
            </button>
          )}
          {fechado && !nfLiberada && <span className="desc">NF bloqueada: {motivoNf}</span>}
          {fechado && <button className="perigo" onClick={() => setJanela("reabrir")}>Reabrir COP</button>}
          {podeExcluir && <button className="perigo" onClick={() => setJanela("excluir")}>Excluir COP</button>}
        </div>
      )}
      {!monta && podeExcluir && (
        <div className="barra-acoes"><button className="perigo" onClick={() => setJanela("excluir")}>Excluir COP</button></div>
      )}

      {!itens.length ? (
        <div className="estado-vazio"><strong>COP sem itens</strong>{monta && aberto ? "Use \"Adicionar cortes prontos\" para incluir os cortes já registrados." : ""}</div>
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr>
                {monta && fechado && <th><span className="sr-only">Selecionar</span></th>}
                <th>OP / cliente</th><th>Material / modo</th><th className="num">Peças / peso</th>
                <th>SA</th><th>NF</th>{!aberto && !fechado && <th>Recebimento</th>}{monta && aberto && <th />}
              </tr>
            </thead>
            <tbody>
              {itens.map((i) => {
                const semSa = i.sa?.situacao !== "CONFIRMADO";
                return (
                  <tr key={i.id} className={fechado && semSa ? "inativo" : sel.includes(i.id) ? "selecionada" : ""}>
                    {monta && fechado && (
                      <td><input type="checkbox" aria-label={`Selecionar OP ${i.op}`} checked={sel.includes(i.id)}
                        onChange={() => setSel(sel.includes(i.id) ? sel.filter((x) => x !== i.id) : [...sel, i.id])} /></td>
                    )}
                    <td><strong>{i.op}</strong><br /><span className="desc">{i.cliente ?? "—"}</span></td>
                    <td>{i.material}<br /><span className="desc">{i.conteiner ?? "—"} · {MODO_NOME[i.modo]}</span></td>
                    <td className="num">{i.pecas} pç<br /><span className="desc">{kg(i.peso_kg)} kg</span></td>
                    <td>
                      {i.sa ? <span className={`etiqueta ${SA_ITEM[i.sa.situacao]?.classe ?? ""}`}>{SA_ITEM[i.sa.situacao]?.nome ?? i.sa.situacao}</span> : aberto ? "—" : <span className="etiqueta">sem SA</span>}
                      {i.sa?.sa_codigo && <><br /><span className="desc">{i.sa.sa_codigo}</span></>}
                      {i.sa && (temPrecificador(i)
                        ? <><br /><span className="desc">R$ {rsKg(i.sa.rs_kg ?? 0)}/kg{i.sa.valor_precificador != null && ` · precificador R$ ${reais(i.sa.valor_precificador)} por peça`}</span></>
                        : !aberto && <><br /><span className="etiqueta atencao">falta R$/kg</span></>)}
                    </td>
                    <td>{i.nf ? `${i.nf.numero} · ${nomeEmitente(i.nf.emitente)}` : "—"}</td>
                    {!aberto && !fechado && (
                      <td>
                        {i.situacao === "RECEBIDO" ? <span className="etiqueta ok">recebido</span> : <span className="etiqueta info">em trânsito</span>}
                        {i.divergencias.length > 0 && <><br /><span className="etiqueta ruim">{i.divergencias.length} divergência(s)</span></>}
                      </td>
                    )}
                    {monta && aberto && (
                      <td className="acoes">
                        <button className="link" onClick={() => setEditando(i)}>Editar</button>
                        <button className="link" onClick={() => void remover(i.id)}>Remover</button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {c.nfs.length > 0 && <p className="desc" style={{ marginTop: 8 }}>NF(s): {c.nfs.map(nfTexto).join(", ")}</p>}
      {c.observacao && <p className="desc">Observação: {c.observacao}</p>}

      {editando && <JanelaEditarItem cop={c} item={editando} aoFechar={() => setEditando(null)}
        aoGravar={(novo) => { setEditando(null); setC(novo); setAviso(`Item da OP ${editando.op} corrigido.`); }} />}
      {janela === "adicionar" && <JanelaAdicionar cop={c} aoFechar={() => setJanela(null)} aoGravar={(n) => feito(`${n} corte(s) incluído(s) no COP.`)} />}
      {janela === "fechar" && <JanelaFechar cop={c} aoFechar={() => setJanela(null)} aoGravar={() => feito("COP fechado. Itu foi avisado para fazer os SAs.")} />}
      {janela === "nf" && <JanelaNf cop={c} itemIds={sel} aoFechar={() => setJanela(null)} aoGravar={(n) => feito(`NF ${n} informada.`)} />}
      {janela === "reabrir" && <JanelaReabrir cop={c} aoFechar={() => setJanela(null)} aoGravar={() => feito("COP reaberto. As linhas de SA ainda não confirmadas foram apagadas.")} />}
      {janela === "excluir" && <JanelaExcluir cop={c} aoFechar={() => setJanela(null)} aoGravar={() => nav("/cops")} />}
      {janela === "enviar" && <JanelaEnviar cop={c} aoFechar={() => setJanela(null)} aoGravar={() => feito("COP enviado. Itu foi avisado do material em trânsito.")} />}
    </>
  );
}

/* ------------------------------------------------------------------ janelas */

function JanelaAdicionar({ cop, aoFechar, aoGravar }: { cop: Cop; aoFechar: () => void; aoGravar: (n: number) => void }) {
  const [prontos, setProntos] = useState<CortePronto[] | null>(null);
  const [sel, setSel] = useState<number[]>([]);
  const [erro, setErro] = useState("");
  useEffect(() => {
    api.get<CortePronto[]>("/cops/cortes-prontos").then((r) => { setProntos(r); setSel(r.map((x) => x.liberacao_id)); }).catch((e: Error) => setErro(e.message));
  }, []);
  async function ok() {
    try {
      await api.post(`/cops/${cop.id}/itens`, { liberacao_ids: sel });
      aoGravar(sel.length);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível incluir os cortes.");
    }
  }
  return (
    <Janela titulo={`Adicionar cortes prontos ao COP ${cop.numero}`} aoFechar={aoFechar} larga>
      {prontos === null ? <p className="carregando">Buscando cortes…</p> : !prontos.length ? (
        <p className="validacao alerta">Nenhum corte pronto fora de COP. Registre os cortes em "Cortes a fazer no RJ" primeiro.</p>
      ) : (
        <ul className="escolhas">
          {prontos.map((p) => (
            <li key={p.liberacao_id}>
              <label className={sel.includes(p.liberacao_id) ? "escolha-lote marcada" : "escolha-lote"}>
                <input type="checkbox" checked={sel.includes(p.liberacao_id)}
                  onChange={() => setSel(sel.includes(p.liberacao_id) ? sel.filter((x) => x !== p.liberacao_id) : [...sel, p.liberacao_id])} />
                <span>
                  <span className="titulo">OP {p.op} · {p.material}</span>
                  <span className="linha2">{p.cliente ?? "—"} · {p.lote} · {MODO_NOME[p.modo]} · cortado em {data(p.data_corte)}</span>
                </span>
                <span className="kg"><strong>{kg(p.peso_kg)} kg</strong><span className="desc">{p.pecas} peça(s)</span></span>
              </label>
            </li>
          ))}
        </ul>
      )}
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="primario" disabled={!sel.length} onClick={() => void ok()}>Incluir {sel.length} corte(s)</button>
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}

type PreviaEdicao = Validacao<{ frase?: string }>;
const textoNum = (v: number) => String(v).replace(".", ",");

/** Spec v3.24 T11: "Editar" no item do COP aberto. OP, peças e peso real do corte; o peso ajusta o saldo do lote. */
function JanelaEditarItem({ cop, item, aoFechar, aoGravar }: { cop: Cop; item: CopItem; aoFechar: () => void; aoGravar: (c: Cop) => void }) {
  const [op, setOp] = useState(String(item.op));
  const [pecas, setPecas] = useState(String(item.pecas));
  const [peso, setPeso] = useState(textoNum(item.peso_kg));
  const [motivo, setMotivo] = useState("");
  const [v, setV] = useState<PreviaEdicao | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [erro, setErro] = useState("");
  const [gravando, setGravando] = useState(false);
  const mudar = (f: (x: string) => void) => (x: string) => { f(x); setV(null); setErro(""); };

  /** Só os campos que mudaram (campo ausente = não muda; contrato §4). */
  function corpo(c: Confirmacoes) {
    const b: Record<string, unknown> = { confirmacoes: c };
    const nOp = Number(op.trim()), nPecas = Number(pecas.trim()), nPeso = num(peso);
    if (op.trim() && nOp !== item.op) b.op = nOp;
    if (pecas.trim() && nPecas !== item.pecas) b.pecas = nPecas;
    if (nPeso !== undefined && nPeso !== null && Math.abs(nPeso - item.peso_kg) > 0.0005) b.peso_kg = nPeso;
    if (motivo.trim()) b.motivo = motivo.trim();
    return b;
  }
  const invalido = !/^\d+$/.test(op.trim()) || !/^\d+$/.test(pecas.trim()) || Number(pecas) <= 0 || !((num(peso) ?? 0) > 0);
  const algoMudou = Object.keys(corpo({})).some((k) => k !== "confirmacoes" && k !== "motivo");
  const url = `/cops/${cop.id}/itens/${item.id}`;

  async function conferir() {
    setErro("");
    try { setV(await api.post<PreviaEdicao>(`${url}/validar`, corpo({}))); }
    catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível conferir."); }
  }
  async function gravar() {
    if (!v) return;
    setGravando(true);
    try {
      aoGravar(await api.patch<Cop>(url, corpo(confirmacoesValidas(v.ocorrencias, conf))));
    } catch (e) {
      const x = validacaoDoErro<{ frase?: string }>(e);
      if (x) setV(x); else setErro(e instanceof Error ? e.message : "Não foi possível gravar.");
    } finally {
      setGravando(false);
    }
  }
  return (
    <Janela titulo={`Editar item · OP ${item.op}`} aoFechar={aoFechar}>
      <p className="desc">{item.material} · {item.conteiner ?? "sem contêiner"} · {MODO_NOME[item.modo]}. Mudando o peso, o saldo do lote {item.lote} é ajustado pela diferença.</p>
      <div className="barra-filtros">
        <label>OP<input inputMode="numeric" value={op} onChange={(e) => mudar(setOp)(e.target.value.replace(/\D/g, ""))} /></label>
        <label>Peças<input inputMode="numeric" value={pecas} onChange={(e) => mudar(setPecas)(e.target.value.replace(/\D/g, ""))} /></label>
        <label>Peso real (kg)<input inputMode="decimal" value={peso} onChange={(e) => mudar(setPeso)(e.target.value)} /></label>
      </div>
      <p className="desc">Trocando a OP, o cliente vem do Mega e a troca vale para a solicitação inteira.</p>
      <label>Motivo (opcional)<textarea rows={2} value={motivo} onChange={(e) => { setMotivo(e.target.value); setV(null); }} placeholder="Ex.: peso digitado errado" /></label>

      {v?.resultado?.frase && <p className="frase-resultado">{v.resultado.frase}</p>}
      {v && <PainelValidacao ocorrencias={v.ocorrencias} confirmacoes={conf} aoMudar={setConf} semOcorrencias="Pode gravar." />}
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        {!v ? <button className="primario" disabled={invalido || !algoMudou} onClick={() => void conferir()}>Ver o que muda</button>
          : <button className="primario" disabled={gravando || !podeGravar(v.ocorrencias, conf)} onClick={() => void gravar()}>Gravar</button>}
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}

function JanelaFechar({ cop, aoFechar, aoGravar }: { cop: Cop; aoFechar: () => void; aoGravar: () => void }) {
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  async function ok() {
    setOcupado(true);
    try {
      await api.post(`/cops/${cop.id}/fechar`);
      aoGravar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível fechar o COP.");
    } finally {
      setOcupado(false);
    }
  }
  return (
    <Janela titulo={`Fechar COP ${cop.numero}`} aoFechar={aoFechar}>
      <p>Ao fechar, o COP não aceita mais itens e o sistema cria <strong>um pedido de SA por item ({cop.qtd_itens})</strong> em "Cadastro de SA", em Itu.</p>
      <p className="desc">Depois, Itu confirma os SAs e preenche o R$/kg do precificador. Só então o botão "Informar NF" libera; o "Enviar" libera com a NF informada.</p>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="primario" disabled={ocupado} onClick={() => void ok()}>Fechar COP</button>
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}

function JanelaNf({ cop, itemIds, aoFechar, aoGravar }: { cop: Cop; itemIds: number[]; aoFechar: () => void; aoGravar: (n: string) => void }) {
  const [f, setF] = useState({ numero: "", emitente: "FIO_CERTO", data: "" });
  const [erro, setErro] = useState("");
  async function ok(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post(`/cops/${cop.id}/nf`, { numero: f.numero.trim(), emitente: f.emitente, data: f.data || null, item_ids: itemIds.length ? itemIds : null });
      aoGravar(f.numero.trim());
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível informar a NF.");
    }
  }
  return (
    <Janela titulo={itemIds.length ? `NF para ${itemIds.length} item(ns) selecionado(s)` : `NF de transferência do COP ${cop.numero}`} aoFechar={aoFechar}>
      <form onSubmit={(e) => void ok(e)} className="bloco-passo" style={{ gap: "var(--esp-4)" }}>
        <p className="desc">{itemIds.length ? "Vale só para os itens marcados; os outros ficam com a NF do COP." : "Vale para todos os itens do COP. Para algum item com NF diferente, marque-o na lista e use \"NF diferente para itens selecionados\"."}</p>
        <label>Nº da NF<input autoFocus value={f.numero} onChange={(e) => setF({ ...f, numero: e.target.value })} required /></label>
        {EMITENTES_LANCAMENTO.length === 1 ? (
          <p className="desc">Emitente: <strong>{EMITENTES_LANCAMENTO[0].nome}</strong></p>
        ) : (
          <fieldset className="formatos">
            <legend>Emitente</legend>
            {EMITENTES_LANCAMENTO.map((x) => (
              <label key={x.valor} className={f.emitente === x.valor ? "opcao marcada" : "opcao"}>
                <input type="radio" name="emitente-cop" checked={f.emitente === x.valor} onChange={() => setF({ ...f, emitente: x.valor })} />
                {x.nome}
              </label>
            ))}
          </fieldset>
        )}
        <label>Data da NF (opcional)<input type="date" value={f.data} onChange={(e) => setF({ ...f, data: e.target.value })} /></label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario">Informar NF</button>
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
        </div>
      </form>
    </Janela>
  );
}

function JanelaReabrir({ cop, aoFechar, aoGravar }: { cop: Cop; aoFechar: () => void; aoGravar: () => void }) {
  const [j, setJ] = useState("");
  const [erro, setErro] = useState("");
  async function ok() {
    try {
      await api.post(`/cops/${cop.id}/reabrir`, { justificativa: j.trim() });
      aoGravar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível reabrir.");
    }
  }
  const falta = JUSTIFICATIVA_MIN - j.trim().length;
  return (
    <Janela titulo={`Reabrir COP ${cop.numero}`} aoFechar={aoFechar}>
      <p className="desc">Só é possível se nenhum SA deste COP estiver confirmado. As linhas de SA ainda não confirmadas são apagadas e Itu deixa de vê-las.</p>
      <label>Justificativa<textarea autoFocus rows={3} value={j} onChange={(e) => setJ(e.target.value)} /></label>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="perigo" disabled={falta > 0} onClick={() => void ok()}>Reabrir COP</button>
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}

function JanelaExcluir({ cop, aoFechar, aoGravar }: { cop: Cop; aoFechar: () => void; aoGravar: () => void }) {
  const [motivo, setMotivo] = useState("");
  const [erro, setErro] = useState("");
  const [gravando, setGravando] = useState(false);
  const fechado = cop.situacao !== "ABERTO";
  async function ok() {
    setGravando(true);
    try {
      await api.post(`/cops/${cop.id}/excluir`, motivo.trim() ? { motivo: motivo.trim() } : {});
      aoGravar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível excluir.");
      setGravando(false);
    }
  }
  return (
    <Janela titulo={`Excluir COP ${cop.numero}`} aoFechar={aoFechar}>
      <p className="desc">
        O COP nº {cop.numero} deixa de existir. Os {cop.qtd_itens} corte(s) dele voltam para "cortes prontos" e podem entrar em outro COP
        {fechado ? "; as linhas de SA ainda não confirmadas são apagadas e Itu é avisado" : ""}. O saldo não muda. Não dá para desfazer.
      </p>
      <label>Motivo (opcional)<textarea autoFocus rows={2} value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ex.: COP aberto em duplicidade" /></label>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="perigo" disabled={gravando} onClick={() => void ok()}>Excluir COP</button>
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}

function JanelaEnviar({ cop, aoFechar, aoGravar }: { cop: Cop; aoFechar: () => void; aoGravar: () => void }) {
  const [oc, setOc] = useState<Ocorrencia[] | null>(null);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  useEffect(() => {
    api.post<{ ocorrencias: Ocorrencia[] }>(`/cops/${cop.id}/enviar/validar`).then((v) => setOc(v.ocorrencias)).catch((e: Error) => setErro(e.message));
  }, [cop.id]);
  const bloqueia = !!oc?.some((o) => o.nivel !== "ALERTA");
  async function ok() {
    setOcupado(true);
    try {
      await api.post(`/cops/${cop.id}/enviar`);
      aoGravar();
    } catch (e) {
      const v = validacaoDoErro(e);
      if (v) setOc(v.ocorrencias);
      else setErro(e instanceof Error ? e.message : "Não foi possível enviar.");
    } finally {
      setOcupado(false);
    }
  }
  return (
    <Janela titulo={`Enviar COP ${cop.numero}`} aoFechar={aoFechar}>
      <p className="desc">{cop.qtd_itens} item(ns), {kg(cop.peso_total_kg)} kg. Itu é avisado e o material fica em trânsito.</p>
      {oc === null ? <p className="carregando">Conferindo SAs e NF…</p> : <PainelValidacao ocorrencias={oc} confirmacoes={{}} aoMudar={() => undefined} semOcorrencias="SAs confirmados e NF informada. Pode enviar." />}
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="primario" disabled={oc === null || bloqueia || ocupado} onClick={() => void ok()}>Enviar COP</button>
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}
