import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { api, data, kg, validacaoDoErro, type Ocorrencia } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { EMITENTES, nfTexto, nomeEmitente, SA_ITEM, SITUACAO_COP, type Cop, type CortePronto } from "../api/cop";
import { MODO_NOME } from "../api/solicitacao";
import Janela, { fecharJanela } from "../components/Janela";
import PainelValidacao, { JUSTIFICATIVA_MIN } from "../components/PainelValidacao";

const ETAPAS = ["Montar", "Fechar", "SAs em Itu", "NF", "Enviar", "Recebido"];
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
  const [janela, setJanela] = useState<null | "adicionar" | "fechar" | "nf" | "reabrir" | "enviar">(null);

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
  const e = etapa(c);

  return (
    <>
      <p><Link to="/cops">← COPs</Link></p>
      <header className="cabecalho cabecalho-acao">
        <div>
          <h1>COP {c.numero}</h1>
          <p>
            <span className={`etiqueta ${SITUACAO_COP[c.situacao]?.classe ?? ""}`}>{SITUACAO_COP[c.situacao]?.nome ?? c.situacao}</span>{" "}
            {c.qtd_itens} item(ns) · {kg(c.peso_total_kg)} kg
            {c.enviado_em && ` · enviado em ${data(c.enviado_em)}`}
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
        <p className={saOk === itens.length && comNf === itens.length ? "validacao ok" : "validacao alerta"}>
          <span>
            SAs confirmados em Itu: <strong>{saOk} de {itens.length}</strong> · NF informada: <strong>{comNf} de {itens.length}</strong>.
            {saOk < itens.length && " Itu está fazendo os SAs a partir deste COP."}
            {comNf < itens.length && " Informe a NF de transferência."}
          </span>
        </p>
      )}

      {monta && (aberto || fechado) && (
        <div className="barra-acoes">
          <span className="contagem">{sel.length ? `${sel.length} item(ns) selecionado(s)` : ""}</span>
          {aberto && <button className="secundario" onClick={() => setJanela("adicionar")}>Adicionar cortes prontos</button>}
          {fechado && <button className="secundario" onClick={() => setJanela("nf")}>{sel.length ? "NF diferente para itens selecionados" : "Informar NF"}</button>}
          {fechado && <button className="perigo" onClick={() => setJanela("reabrir")}>Reabrir COP</button>}
        </div>
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
                    </td>
                    <td>{i.nf ? `${i.nf.numero} · ${nomeEmitente(i.nf.emitente)}` : "—"}</td>
                    {!aberto && !fechado && (
                      <td>
                        {i.situacao === "RECEBIDO" ? <span className="etiqueta ok">recebido</span> : <span className="etiqueta info">em trânsito</span>}
                        {i.divergencias.length > 0 && <><br /><span className="etiqueta ruim">{i.divergencias.length} divergência(s)</span></>}
                      </td>
                    )}
                    {monta && aberto && <td className="acoes"><button className="link" onClick={() => void remover(i.id)}>Remover</button></td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {c.nfs.length > 0 && <p className="desc" style={{ marginTop: 8 }}>NF(s): {c.nfs.map(nfTexto).join(", ")}</p>}
      {c.observacao && <p className="desc">Observação: {c.observacao}</p>}

      {janela === "adicionar" && <JanelaAdicionar cop={c} aoFechar={() => setJanela(null)} aoGravar={(n) => feito(`${n} corte(s) incluído(s) no COP.`)} />}
      {janela === "fechar" && <JanelaFechar cop={c} aoFechar={() => setJanela(null)} aoGravar={() => feito("COP fechado. Itu foi avisado para fazer os SAs.")} />}
      {janela === "nf" && <JanelaNf cop={c} itemIds={sel} aoFechar={() => setJanela(null)} aoGravar={(n) => feito(`NF ${n} informada.`)} />}
      {janela === "reabrir" && <JanelaReabrir cop={c} aoFechar={() => setJanela(null)} aoGravar={() => feito("COP reaberto. As linhas de SA ainda não confirmadas foram apagadas.")} />}
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
        <p className="validacao alerta">Nenhum corte pronto fora de COP. Registre os cortes na Fila RJ primeiro.</p>
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
      <p>Ao fechar, o COP não aceita mais itens e o sistema cria <strong>um pedido de SA por item ({cop.qtd_itens})</strong> na fila de Itu.</p>
      <p className="desc">Depois, informe a NF de transferência. O botão "Enviar" libera quando todos os SAs estiverem confirmados e a NF informada.</p>
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
        <fieldset className="formatos">
          <legend>Emitente</legend>
          {EMITENTES.map((x) => (
            <label key={x.valor} className={f.emitente === x.valor ? "opcao marcada" : "opcao"}>
              <input type="radio" name="emitente-cop" checked={f.emitente === x.valor} onChange={() => setF({ ...f, emitente: x.valor })} />
              {x.nome}
            </label>
          ))}
        </fieldset>
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
      <label>Justificativa<textarea autoFocus rows={3} value={j} onChange={(e) => setJ(e.target.value)} />
        <small className="dica">{falta > 0 ? `Faltam ${falta} caractere(s).` : "Ok."}</small></label>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="perigo" disabled={falta > 0} onClick={() => void ok()}>Reabrir COP</button>
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
