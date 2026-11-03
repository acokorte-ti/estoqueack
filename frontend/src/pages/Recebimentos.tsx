import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, data, kg, num, qs, validacaoDoErro, type Validacao } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { nfTexto, SITUACAO_COP, type Cop, type CopItem } from "../api/cop";
import { MODO_NOME } from "../api/solicitacao";
import Janela, { fecharJanela } from "../components/Janela";
import PainelValidacao, { confirmacoesValidas, podeGravar, type Confirmacoes } from "../components/PainelValidacao";

/** T12: COPs enviados pelo RJ e ainda não recebidos por inteiro. */
export function Recebimentos() {
  const nav = useNavigate();
  const [lista, setLista] = useState<Cop[] | null>(null);
  const [erro, setErro] = useState("");
  useEffect(() => {
    api.get<Cop[]>("/recebimentos").then(setLista).catch((e: Error) => setErro(e.message));
  }, []);
  return (
    <>
      <header className="cabecalho">
        <h1>Receber COP</h1>
        <p>COPs que saíram do RJ. Confira item a item quando o material chegar a Itu.</p>
      </header>
      {erro && <p className="erro" role="alert">{erro}</p>}
      {lista && !lista.length && <div className="estado-vazio"><strong>Nada em trânsito</strong>Quando o RJ enviar um COP, ele aparece aqui e no sino.</div>}
      <ul className="cartoes">
        {lista?.map((c) => (
          <li key={c.id} className="cartao">
            <div className="cartao-topo">
              <span className="cartao-op">COP {c.numero}</span>
              <span className={`etiqueta ${SITUACAO_COP[c.situacao]?.classe ?? ""}`}>{SITUACAO_COP[c.situacao]?.nome ?? c.situacao}</span>
            </div>
            <dl className="dados">
              <div><dt>Enviado em</dt><dd>{data(c.enviado_em)}</dd></div>
              <div><dt>Itens</dt><dd>{c.qtd_itens}</dd></div>
              <div><dt>Peso</dt><dd>{kg(c.peso_total_kg)} kg</dd></div>
              <div><dt>NF</dt><dd>{c.nfs.length ? c.nfs.map(nfTexto).join(", ") : "—"}</dd></div>
            </dl>
            <div className="cartao-acoes"><button className="primario" onClick={() => nav(`/recebimentos/${c.id}`)}>Conferir e receber</button></div>
          </li>
        ))}
      </ul>
    </>
  );
}

interface Linha { marcado: boolean; peso: string }

/** T12: conferência de um COP. Diferença acima de 2 % pede justificativa, mas não bloqueia. */
export function ReceberCop() {
  const { id } = useParams();
  const { usuario } = useSessao();
  const recebe = usuario?.perfil === "ESTOQUE" || usuario?.perfil === "ADMIN";
  const [c, setC] = useState<Cop | null>(null);
  const [linhas, setLinhas] = useState<Record<number, Linha>>({});
  const [v, setV] = useState<Validacao | null>(null);
  const [conf, setConf] = useState<Confirmacoes>({});
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [divDe, setDivDe] = useState<CopItem | null>(null);
  const [recebidos, setRecebidos] = useState<CopItem[] | null>(null);

  const carregar = useCallback(() => api.get<Cop>(`/cops/${id}`).then((x) => {
    setC(x);
    const l: Record<number, Linha> = {};
    (x.itens ?? []).filter((i) => i.situacao === "EM_TRANSITO").forEach((i) => { l[i.id] = { marcado: true, peso: "" }; });
    setLinhas(l);
  }).catch((e: Error) => setErro(e.message)), [id]);
  useEffect(() => {
    void carregar();
  }, [carregar]);

  if (!c) return erro ? <p className="erro" role="alert">{erro}</p> : <p className="carregando">Carregando…</p>;

  const itens = c.itens ?? [];
  const transito = itens.filter((i) => i.situacao === "EM_TRANSITO");
  const corpo = (cf: Confirmacoes) => ({
    itens: transito.filter((i) => linhas[i.id]?.marcado).map((i) => ({ cop_item_id: i.id, peso_conferido_kg: num(linhas[i.id].peso) ?? null })),
    confirmacoes: cf,
  });
  const qtd = transito.filter((i) => linhas[i.id]?.marcado).length;
  const mudar = (iid: number, p: Partial<Linha>) => { setLinhas({ ...linhas, [iid]: { ...linhas[iid], ...p } }); setV(null); };

  async function conferir() {
    setErro("");
    setOcupado(true);
    try {
      setV(await api.post<Validacao>(`/cops/${id}/receber/validar`, corpo({})));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível conferir.");
    } finally {
      setOcupado(false);
    }
  }

  async function receber() {
    if (!v) return;
    setErro("");
    setOcupado(true);
    try {
      const marcados = new Set(corpo({}).itens.map((x) => x.cop_item_id));
      const r = await api.post<Cop>(`/cops/${id}/receber`, corpo(confirmacoesValidas(v.ocorrencias, conf)));
      setRecebidos((r.itens ?? []).filter((i) => marcados.has(i.id)));
      setV(null);
      setConf({});
      setC(r);
    } catch (e) {
      const x = validacaoDoErro(e);
      if (x) setV(x);
      else setErro(e instanceof Error ? e.message : "Não foi possível registrar o recebimento.");
    } finally {
      setOcupado(false);
    }
  }

  const pecasInteiras = recebidos?.filter((i) => i.modo === "TRAZER_INTEIRA") ?? [];

  return (
    <>
      <p><Link to="/recebimentos">← Receber COP</Link></p>
      <header className="cabecalho">
        <h1>Receber COP {c.numero}</h1>
        <p><span className={`etiqueta ${SITUACAO_COP[c.situacao]?.classe ?? ""}`}>{SITUACAO_COP[c.situacao]?.nome ?? c.situacao}</span> · enviado em {data(c.enviado_em)} · NF {c.nfs.length ? c.nfs.map(nfTexto).join(", ") : "—"}</p>
      </header>

      {recebidos && (
        <div className="validacao ok" role="status">
          <span>{recebidos.length} item(ns) recebido(s). Peças cortadas ficam concluídas.</span>
          {pecasInteiras.map((i) => (
            <span key={i.id}>
              Peça inteira da OP {i.op} virou lote RJ em Itu.{" "}
              {i.lote_itu_id && <Link to={`/corte-itu${qs({ op: i.op, lote_id: i.lote_itu_id })}`}>Cortar em Itu agora</Link>}
            </span>
          ))}
        </div>
      )}
      {erro && <p className="erro" role="alert">{erro}</p>}

      <ul className="cartoes cartoes-lista">
        {itens.map((i) => {
          const l = linhas[i.id];
          const emTransito = i.situacao === "EM_TRANSITO";
          return (
            <li key={i.id} className={emTransito ? "cartao" : "cartao inativo"}>
              <div className="cartao-topo">
                <span className="cartao-op">OP {i.op}</span>
                {emTransito ? <span className="etiqueta info">em trânsito</span> : <span className="etiqueta ok">recebido</span>}
                {i.divergencias.length > 0 && <span className="etiqueta ruim">{i.divergencias.length} divergência(s)</span>}
              </div>
              <dl className="dados">
                <div><dt>Material</dt><dd>{i.material}</dd></div>
                <div><dt>Contêiner</dt><dd>{i.conteiner ?? "—"}</dd></div>
                <div><dt>Modo</dt><dd>{MODO_NOME[i.modo]}</dd></div>
                <div><dt>Peças</dt><dd>{i.pecas}</dd></div>
                <div><dt>Peso enviado</dt><dd>{kg(i.peso_kg)} kg</dd></div>
                {i.peso_conferido_kg !== null && <div><dt>Conferido em Itu</dt><dd>{kg(i.peso_conferido_kg)} kg</dd></div>}
              </dl>
              {emTransito && recebe && l && (
                <div className="grade-form">
                  <label className="marcar">
                    <input type="checkbox" checked={l.marcado} onChange={(e) => mudar(i.id, { marcado: e.target.checked })} />
                    <span>Chegou</span>
                  </label>
                  <label>Peso conferido em Itu (kg), opcional<input inputMode="decimal" value={l.peso} disabled={!l.marcado} onChange={(e) => mudar(i.id, { peso: e.target.value })} /></label>
                </div>
              )}
              {recebe && <div className="cartao-acoes"><button className="secundario" onClick={() => setDivDe(i)}>Registrar divergência</button></div>}
            </li>
          );
        })}
      </ul>

      {v && <div style={{ marginTop: "var(--esp-4)" }}><PainelValidacao ocorrencias={v.ocorrencias} confirmacoes={conf} aoMudar={setConf} semOcorrencias="Pesos dentro do esperado." /></div>}

      {recebe && transito.length > 0 && (
        <div className="rodape-acao">
          <span className="resultado-frase">{qtd} de {transito.length} item(ns) marcados</span>
          {!v ? (
            <button className="primario" disabled={!qtd || ocupado} onClick={() => void conferir()}>{ocupado ? "Conferindo…" : "Conferir recebimento"}</button>
          ) : (
            <button className="primario" disabled={ocupado || !podeGravar(v.ocorrencias, conf)} onClick={() => void receber()}>{ocupado ? "Gravando…" : "Confirmar recebimento"}</button>
          )}
        </div>
      )}

      {divDe && <JanelaDivergencia cop={c} item={divDe} aoFechar={() => setDivDe(null)} aoGravar={() => { setDivDe(null); void carregar(); }} />}
    </>
  );
}

const TIPOS = [
  { valor: "FALTANDO", nome: "Faltando" },
  { valor: "DANIFICADO", nome: "Danificado" },
  { valor: "PESO_DIFERENTE", nome: "Peso diferente" },
];

function JanelaDivergencia({ cop, item, aoFechar, aoGravar }: { cop: Cop; item: CopItem; aoFechar: () => void; aoGravar: () => void }) {
  const [f, setF] = useState({ tipo: "FALTANDO", pecas: "", kg: "", observacao: "" });
  const [erro, setErro] = useState("");
  async function ok(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post(`/cops/${cop.id}/divergencias`, { cop_item_id: item.id, tipo: f.tipo, pecas: num(f.pecas) ?? null, kg: num(f.kg) ?? null, observacao: f.observacao.trim() });
      aoGravar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível registrar.");
    }
  }
  return (
    <Janela titulo={`Divergência · OP ${item.op}`} aoFechar={aoFechar}>
      <form onSubmit={(e) => void ok(e)} className="bloco-passo" style={{ gap: "var(--esp-4)" }}>
        <p className="desc">Não bloqueia o recebimento. O RJ e o administrador são avisados e a diferença entra no relatório de exceções.</p>
        <fieldset className="formatos">
          <legend>O que houve</legend>
          {TIPOS.map((t) => (
            <label key={t.valor} className={f.tipo === t.valor ? "opcao marcada" : "opcao"}>
              <input type="radio" name="tipo-div" checked={f.tipo === t.valor} onChange={() => setF({ ...f, tipo: t.valor })} />{t.nome}
            </label>
          ))}
        </fieldset>
        <div className="grade-form">
          <label>Peças<input inputMode="numeric" value={f.pecas} onChange={(e) => setF({ ...f, pecas: e.target.value })} /></label>
          <label>Kg<input inputMode="decimal" value={f.kg} onChange={(e) => setF({ ...f, kg: e.target.value })} /></label>
        </div>
        <label>Observação<textarea rows={3} value={f.observacao} onChange={(e) => setF({ ...f, observacao: e.target.value })} required minLength={3} /></label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario" disabled={f.observacao.trim().length < 3}>Registrar divergência</button>
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
        </div>
      </form>
    </Janela>
  );
}
