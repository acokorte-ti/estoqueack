import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, data, kg, num, qs, validacaoDoErro, type Validacao } from "../api/cliente";
import { useSessao } from "../api/sessao";
import Janela, { fecharJanela } from "../components/Janela";
import PainelValidacao, { confirmacoesValidas, JUSTIFICATIVA_MIN, podeGravar, type Confirmacoes } from "../components/PainelValidacao";
import SyncMega from "../components/SyncMega";

type Situacao = "ABERTA" | "RESOLVIDA" | "DESCARTADA" | "ENCERRADA";
interface Pendencia {
  id: number; codigo: number; descricao: string; situacao: Situacao;
  saldo_mega_kg: number; soma_lotes_kg: number; diferenca_kg: number; criado_em: string;
  ultima_entrada?: { nf: string | null; data: string | null; kg: number | null; tpm?: string | null } | null;
  etiquetas?: ("CODIGO_NOVO" | "CODIGO_RETO")[]; aviso?: string | null;
  item?: { id: number; liga: string; formato: string; bitola: string; criado_pela_t15?: boolean } | null;
  item_sugerido?: { legivel: boolean; liga?: string; formato?: string; bitola?: string; mensagem?: string } | null;
  motivo?: string | null; motivo_descricao?: string | null; justificativa?: string | null; tratada_por?: string | null; tratada_em?: string | null;
}
interface Lista { itens: Pendencia[]; total: number; limite_kg: number; abertas: number; mega_indisponivel?: boolean; aviso?: string | null; ultima_sincronizacao?: string | null }
interface Previa { diferenca_kg?: number; diferenca_restante_kg?: number; peso_sugerido_kg?: number; nf?: string | null; data_entrada?: string | null;
  item_novo?: { liga: string; formato: string; bitola: string } | null }
interface Motivo { codigo: string; descricao: string }

const SITUACAO: Record<Situacao, { nome: string; classe: string }> = {
  ABERTA: { nome: "Aberta", classe: "atencao" }, RESOLVIDA: { nome: "Resolvida", classe: "ok" },
  DESCARTADA: { nome: "Não é entrada", classe: "info" }, ENCERRADA: { nome: "Encerrada pelo Mega", classe: "" },
};
const hojeIso = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const haQuanto = (iso: string) => {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  return d <= 0 ? "hoje" : d === 1 ? "1 dia" : `${d} dias`;
};

/** T15 Entradas Mega a classificar (mínima): transforma a diferença do código Mega em lote ITU/ITU ou diz que não é entrada. */
export default function EntradasMega() {
  const { usuario } = useSessao();
  const altera = usuario?.perfil === "ESTOQUE" || usuario?.perfil === "ADMIN";
  const admin = usuario?.perfil === "ADMIN";
  const [situacao, setSituacao] = useState<"ABERTA" | "TODAS">("ABERTA");
  const [busca, setBusca] = useState("");
  const [lista, setLista] = useState<Lista | null>(null);
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [acao, setAcao] = useState<{ tipo: "criar" | "nao" | "reabrir"; p: Pendencia } | null>(null);

  const carregar = useCallback(() => {
    setErro("");
    return api.get<Lista>(`/entradas-mega${qs({ situacao, busca: busca.trim() })}`).then(setLista).catch((e: Error) => setErro(e.message));
  }, [situacao, busca]);
  useEffect(() => {
    const t = window.setTimeout(() => void carregar(), 250);
    return () => window.clearTimeout(t);
  }, [carregar]);

  const feito = (msg: string) => { setAcao(null); setOk(msg); void carregar(); };

  return (
    <>
      <header className="cabecalho">
        <h1>Entradas Mega a classificar</h1>
        <p>Código com mais saldo no Mega do que nos lotes do sistema (mais de {lista?.limite_kg ?? 5} kg). Crie o lote da entrada ou diga que a diferença não é entrada.{!altera && " Você só consulta esta tela."}</p>
      </header>
      <SyncMega />
      {erro && <p className="erro" role="alert">{erro}</p>}
      {ok && <p className="validacao ok" role="status">{ok}</p>}
      {lista?.mega_indisponivel && <p className="validacao alerta">{lista.aviso ?? "Não foi possível ler as entradas no Mega agora. A lista usa o último saldo sincronizado."}</p>}

      <div className="barra-filtros">
        <label style={{ flexBasis: "18rem" }}>Código ou descrição<input value={busca} onChange={(e) => setBusca(e.target.value)} /></label>
        <div className="chips" role="group" aria-label="Situação">
          <button type="button" className="chip" aria-pressed={situacao === "ABERTA"} onClick={() => setSituacao("ABERTA")}>Abertas{lista && situacao === "ABERTA" ? ` (${lista.abertas})` : ""}</button>
          <button type="button" className="chip" aria-pressed={situacao === "TODAS"} onClick={() => setSituacao("TODAS")}>Todas</button>
        </div>
      </div>

      {lista && !lista.itens.length ? (
        <div className="estado-vazio"><strong>{situacao === "ABERTA" ? "Nenhuma entrada a classificar" : "Nenhuma pendência"}</strong>{situacao === "ABERTA" && "O saldo dos lotes bate com o Mega em todos os códigos."}</div>
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead><tr><th>Código</th><th className="num">Saldo Mega</th><th className="num">Soma dos lotes</th><th className="num">Diferença</th><th>Última entrada no Mega</th><th>Há quanto tempo</th><th>Situação</th><th><span className="sr-only">Ações</span></th></tr></thead>
            <tbody>
              {lista?.itens.map((p) => (
                <tr key={p.id}>
                  <td>
                    <strong>{p.codigo}</strong> <span className="desc">{p.descricao}</span>
                    {p.etiquetas?.includes("CODIGO_NOVO") && <> <span className="etiqueta info">Código novo</span></>}
                    {p.etiquetas?.includes("CODIGO_RETO") && <> <span className="etiqueta atencao">Código RETO</span></>}
                    {p.aviso && <small className="desc" style={{ display: "block" }}>{p.aviso}</small>}
                  </td>
                  <td className="num">{kg(p.saldo_mega_kg)}</td>
                  <td className="num">{kg(p.soma_lotes_kg)}</td>
                  <td className="num"><strong>{p.diferenca_kg > 0 ? "+" : ""}{kg(p.diferenca_kg)}</strong></td>
                  <td>{p.ultima_entrada ? <>NF {p.ultima_entrada.nf ?? "—"} · {data(p.ultima_entrada.data)} · {p.ultima_entrada.kg !== null ? `${kg(p.ultima_entrada.kg)} kg` : "—"}</> : <span className="desc">não disponível</span>}</td>
                  <td>{haQuanto(p.criado_em)}</td>
                  <td>
                    <span className={`etiqueta ${SITUACAO[p.situacao].classe}`}>{SITUACAO[p.situacao].nome}</span>
                    {p.motivo_descricao && <small className="desc" style={{ display: "block" }} title={p.justificativa ?? ""}>{p.motivo_descricao}: {p.justificativa} ({p.tratada_por}{p.tratada_em ? `, ${data(p.tratada_em)}` : ""})</small>}
                  </td>
                  <td>
                    <div className="botoes">
                      {altera && p.situacao === "ABERTA" && <button className="primario" onClick={() => { setOk(""); setAcao({ tipo: "criar", p }); }}>Criar lote</button>}
                      {altera && p.situacao === "ABERTA" && <button className="secundario" onClick={() => { setOk(""); setAcao({ tipo: "nao", p }); }}>Não é entrada</button>}
                      {admin && p.situacao === "DESCARTADA" && <button className="secundario" onClick={() => { setOk(""); setAcao({ tipo: "reabrir", p }); }}>Reabrir</button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="dica" style={{ marginTop: "var(--esp-3)" }}>A lista é refeita a cada sincronização com o Mega (6h, 13h e "Sincronizar agora"). A diferença que você explicar aparece como "explicada na T15" na <Link to="/conciliacao">Conciliação</Link>.</p>

      {acao?.tipo === "criar" && <JanelaCriarLote p={acao.p} aoFechar={() => setAcao(null)} aoGravar={feito} />}
      {acao?.tipo === "nao" && <JanelaNaoEntrada p={acao.p} aoFechar={() => setAcao(null)} aoGravar={() => feito(`Código ${acao.p.codigo}: diferença marcada como "não é entrada".`)} />}
      {acao?.tipo === "reabrir" && <JanelaReabrir p={acao.p} aoFechar={() => setAcao(null)} aoGravar={() => feito(`Código ${acao.p.codigo}: pendência reaberta.`)} />}
    </>
  );
}

function JanelaCriarLote({ p, aoFechar, aoGravar }: { p: Pendencia; aoFechar: () => void; aoGravar: (msg: string) => void }) {
  const [f, setF] = useState({ peso: String(p.diferenca_kg).replace(".", ","), conteiner: "", sem: false, pecas: "", data: "", nf: "", obs: "" });
  const [v, setV] = useState<Validacao<Previa> | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const mudar = (x: Partial<typeof f>) => { setF({ ...f, ...x }); setV(null); };

  const corpo = (c: Confirmacoes) => ({
    peso_kg: num(f.peso) ?? 0, conteiner: f.sem ? undefined : f.conteiner.trim().toUpperCase() || undefined, sem_conteiner: f.sem || undefined,
    pecas: num(f.pecas), data_entrada: f.data || undefined, nf: f.nf.trim() || undefined, observacao: f.obs.trim() || undefined, confirmacoes: c,
  });
  const completo = (num(f.peso) ?? 0) > 0 && (f.sem || f.conteiner.trim().length >= 2);
  const item = p.item ?? (p.item_sugerido?.legivel ? p.item_sugerido : null);
  const ilegivel = !p.item && p.item_sugerido && !p.item_sugerido.legivel;

  async function conferir() {
    setErro(""); setOcupado(true);
    try { setV(await api.post<Validacao<Previa>>(`/entradas-mega/${p.id}/criar-lote/validar`, corpo({}))); }
    catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível conferir."); }
    finally { setOcupado(false); }
  }
  async function gravar() {
    if (!v) return;
    setErro(""); setOcupado(true);
    try {
      const r = await api.post<{ mensagem?: string; lote?: { codigo: string; peso_kg: number } }>(`/entradas-mega/${p.id}/criar-lote`, corpo(confirmacoesValidas(v.ocorrencias, conf)));
      aoGravar(r.mensagem ?? `Lote ${r.lote?.codigo ?? ""} criado.`);
    } catch (e) {
      const x = validacaoDoErro<Previa>(e);
      if (x) setV(x); else setErro(e instanceof Error ? e.message : "Não foi possível criar o lote.");
    } finally { setOcupado(false); }
  }
  const r = v?.resultado;
  const bloqueado = v ? !podeGravar(v.ocorrencias, conf) : true;

  return (
    <Janela titulo={`Criar lote · código ${p.codigo}`} aoFechar={aoFechar} larga>
      <div className="bloco-passo" style={{ gap: "var(--esp-4)" }}>
        <dl className="ficha">
          <div><dt>Descrição no Mega</dt><dd>{p.descricao}</dd></div>
          <div><dt>Material</dt><dd>{item ? `${item.liga} ${item.bitola} (${item.formato})` : "—"}{!p.item && item && <> <span className="etiqueta info">item novo no catálogo</span></>}</dd></div>
          <div><dt>Diferença</dt><dd>{kg(p.diferenca_kg)} kg (Mega {kg(p.saldo_mega_kg)} − lotes {kg(p.soma_lotes_kg)})</dd></div>
        </dl>
        {ilegivel && <p className="validacao erro">{p.item_sugerido?.mensagem ?? "Não consegui ler liga e bitola desta descrição. Peça ao Admin para cadastrar o item no Catálogo (T22)."}</p>}
        {p.aviso && <p className="validacao alerta">{p.aviso}</p>}
        <div className="grade-form">
          <label>Peso do lote (kg)<input inputMode="decimal" autoFocus value={f.peso} onChange={(e) => mudar({ peso: e.target.value })} />
            <small className="dica">Sugerido: a diferença. Se for menor, a pendência continua aberta com o que sobrou.</small></label>
          <label>Contêiner<input value={f.conteiner} disabled={f.sem} onChange={(e) => mudar({ conteiner: e.target.value.toUpperCase() })} placeholder="CH11EA" /></label>
          <label className="marcar"><input type="checkbox" checked={f.sem} onChange={(e) => mudar({ sem: e.target.checked })} /><span>Sem contêiner</span></label>
          <label>Peças (opcional)<input inputMode="numeric" value={f.pecas} onChange={(e) => mudar({ pecas: e.target.value })} /></label>
          <label>Data de entrada<input type="date" max={hojeIso()} value={f.data} onChange={(e) => mudar({ data: e.target.value })} /><small className="dica">Vazio: data da NF no Mega.</small></label>
          <label>NF (opcional)<input value={f.nf} onChange={(e) => mudar({ nf: e.target.value })} placeholder={p.ultima_entrada?.nf ?? ""} /></label>
        </div>
        <label>Observação (opcional)<textarea rows={2} value={f.obs} onChange={(e) => mudar({ obs: e.target.value })} /></label>

        {v && (
          <>
            <PainelValidacao ocorrencias={v.ocorrencias} confirmacoes={conf} aoMudar={setConf} semOcorrencias="Nenhum problema encontrado." />
            {r && (
              <p className="desc">
                {r.item_novo && <>Item novo: {r.item_novo.liga} {r.item_novo.bitola}. </>}
                Lote com {kg(num(f.peso) ?? 0)} kg{r.nf ? `, NF ${r.nf}` : ""}{r.data_entrada ? `, entrada em ${data(r.data_entrada)}` : ""}. Diferença restante: {kg(r.diferenca_restante_kg ?? 0)} kg.
              </p>
            )}
          </>
        )}
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          {!v || v.ocorrencias.some((o) => o.nivel === "ERRO")
            ? <button className="primario" disabled={!completo || ocupado || !!ilegivel} onClick={() => void conferir()}>Conferir</button>
            : <button className="primario" disabled={bloqueado || ocupado} onClick={() => void gravar()}>Criar lote</button>}
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
        </div>
      </div>
    </Janela>
  );
}

function JanelaNaoEntrada({ p, aoFechar, aoGravar }: { p: Pendencia; aoFechar: () => void; aoGravar: () => void }) {
  const [motivos, setMotivos] = useState<Motivo[]>([]);
  const [motivo, setMotivo] = useState("");
  const [j, setJ] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  useEffect(() => { api.get<Motivo[]>("/entradas-mega/motivos").then(setMotivos).catch((e: Error) => setErro(e.message)); }, []);
  const falta = JUSTIFICATIVA_MIN - j.trim().length;
  async function ok(e: FormEvent) {
    e.preventDefault();
    setErro(""); setOcupado(true);
    try { await api.post(`/entradas-mega/${p.id}/nao-e-entrada`, { motivo, justificativa: j.trim() }); aoGravar(); }
    catch (err) { setErro(err instanceof Error ? err.message : "Não foi possível concluir."); }
    finally { setOcupado(false); }
  }
  return (
    <Janela titulo={`Não é entrada · código ${p.codigo}`} aoFechar={aoFechar}>
      <form onSubmit={(e) => void ok(e)} className="bloco-passo" style={{ gap: "var(--esp-4)" }}>
        <p className="desc">Os {kg(p.diferenca_kg)} kg ficam como diferença explicada e não voltam na próxima sincronização. Se o Mega subir de novo, só o aumento gera nova pendência.</p>
        <label>Motivo
          <select value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus>
            <option value="">Escolha</option>
            {motivos.map((m) => <option key={m.codigo} value={m.codigo}>{m.descricao}</option>)}
          </select>
        </label>
        <label>Justificativa<textarea rows={3} value={j} onChange={(e) => setJ(e.target.value)} />
          <small className="dica">{falta > 0 ? `Faltam ${falta} caractere(s).` : "Ok."}</small></label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario" disabled={!motivo || falta > 0 || ocupado}>Não é entrada</button>
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
        </div>
      </form>
    </Janela>
  );
}

function JanelaReabrir({ p, aoFechar, aoGravar }: { p: Pendencia; aoFechar: () => void; aoGravar: () => void }) {
  const [j, setJ] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const falta = JUSTIFICATIVA_MIN - j.trim().length;
  async function ok(e: FormEvent) {
    e.preventDefault();
    setErro(""); setOcupado(true);
    try { await api.post(`/entradas-mega/${p.id}/reabrir`, { justificativa: j.trim() }); aoGravar(); }
    catch (err) { setErro(err instanceof Error ? err.message : "Não foi possível reabrir."); }
    finally { setOcupado(false); }
  }
  return (
    <Janela titulo={`Reabrir · código ${p.codigo}`} aoFechar={aoFechar}>
      <form onSubmit={(e) => void ok(e)} className="bloco-passo" style={{ gap: "var(--esp-4)" }}>
        <p className="desc">A pendência volta a Aberta e a diferença deixa de ser explicada.</p>
        <label>Justificativa<textarea autoFocus rows={3} value={j} onChange={(e) => setJ(e.target.value)} />
          <small className="dica">{falta > 0 ? `Faltam ${falta} caractere(s).` : "Ok."}</small></label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario" disabled={falta > 0 || ocupado}>Reabrir</button>
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
        </div>
      </form>
    </Janela>
  );
}
