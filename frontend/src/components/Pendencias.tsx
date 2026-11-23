import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { data, kg } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { lerSeVelho, recarregarPendencias, usePendencias, type ItemPendencia, type Pendencia } from "../api/pendencias";
import { CODIGOS_PESO_REAL, diasDe, encerrarPendenciaPesoReal, linkPeca, resumirPesoReal, textoPeca, vencida, type PecaPesoReal, type PendenciaPesoReal } from "../api/pesoReal";
import Janela, { fecharJanela } from "./Janela";
import Icone, { type NomeIcone } from "./Icone";
import { JUSTIFICATIVA_MIN } from "./PainelValidacao";

const NOME_GRUPO: Record<string, string> = { ESTOQUE: "Itu", OPERACAO_RJ: "Barra Mansa", ANALISE: "Análise", FINANCEIRO: "Financeiro" };
const s = (v: unknown) => (v === null || v === undefined ? "" : String(v));

/** Ícone e verbo do botão de cada tipo de pendência (layout A: a tarefa diz o que fazer). */
const TIPO: Record<string, { icone: NomeIcone; verbo: string }> = {
  SA_SEGURANDO_COP: { icone: "sa", verbo: "Abrir Cadastro de SA" },
  SA_SEM_CONFIRMACAO: { icone: "relogio", verbo: "Abrir Cadastro de SA" },
  SA_SEM_PRECIFICADOR: { icone: "sa", verbo: "Informar R$/kg" },
  COP_EM_TRANSITO: { icone: "receber", verbo: "Receber" },
  COP_ABERTO: { icone: "envio", verbo: "Abrir envios" },
  COP_AGUARDANDO_SA: { icone: "envio", verbo: "Abrir envios" },
  COP_AGUARDANDO_NF: { icone: "nf", verbo: "Informar NF" },
  CORTES_FORA_DE_COP: { icone: "envio", verbo: "Montar envio" },
  FILA_CORTE: { icone: "fila", verbo: "Ver cortes" },
  FILA_CORTE_ATRASADA: { icone: "fila", verbo: "Ver cortes" },
  MATERIAL_INSUFICIENTE: { icone: "alerta", verbo: "Ver pedidos" },
  RESERVA_VENCENDO: { icone: "relogio", verbo: "Ver reservas" },
  DIVERGENCIA_MEGA: { icone: "conferir", verbo: "Conferir" },
  ENTRADA_MEGA_A_CLASSIFICAR: { icone: "mega", verbo: "Classificar" },
  EXCECOES_SEMANA: { icone: "relatorio", verbo: "Ver" },
};
const tipo = (codigo: string) => TIPO[codigo] ?? { icone: "lista" as NomeIcone, verbo: "Abrir" };

/** Uma linha curta para cada item, conforme o tipo de pendência (contrato F1 §11). */
function resumo(codigo: string, i: ItemPendencia): { texto: string; link?: string } {
  switch (codigo) {
    case "SA_SEGURANDO_COP":
      // spec v3.16: precificador_pendentes é campo novo (opcional; API antiga não manda)
      return { texto: `COP ${s(i.cop)}: ${s(i.sas_pendentes)} SA(s) e ${s(i.precificador_pendentes ?? 0)} R$/kg pendente(s) de ${s(i.itens)}`, link: i.cop_id ? `/cops/${s(i.cop_id)}` : undefined };
    case "COP_EM_TRANSITO": case "COP_ABERTO": case "COP_AGUARDANDO_SA": case "COP_AGUARDANDO_NF":
      return { texto: `COP ${s(i.numero)} · ${s(i.qtd_itens)} item(ns) · ${typeof i.peso_total_kg === "number" ? `${kg(i.peso_total_kg)} kg` : ""}`,
        link: codigo === "COP_EM_TRANSITO" ? `/recebimentos/${s(i.id)}` : `/cops/${s(i.id)}` };
    case "SA_SEM_PRECIFICADOR": // spec v3.21 (Financeiro): no Mega = falta só o R$/kg para o SA fechar
      return { texto: `OP ${s(i.op)}${i.cop ? ` · COP ${s(i.cop)}` : " · corte em Itu"}${i.material ? ` · ${s(i.material)} ${s(i.dimensao)}` : ""}${typeof i.peso_kg === "number" ? ` · ${kg(i.peso_kg)} kg` : ""}${i.sa_no_mega ? " · SA no Mega, falta só o R$/kg" : ""}`,
        link: i.cop ? `/sa?cop=${s(i.cop)}` : "/sa" };
    case "SA_SEM_CONFIRMACAO":
      return { texto: `OP ${s(i.op)} · SA ${s(i.sa_codigo) || "sem código"} · desde ${data(s(i.criado_em))}`, link: "/sa" };
    case "CORTES_FORA_DE_COP":
      return { texto: `OP ${s(i.op)} · ${s(i.material)} · ${s(i.pecas)} pç · ${typeof i.peso_kg === "number" ? `${kg(i.peso_kg)} kg` : ""}`, link: "/cops" };
    case "RESERVA_VENCENDO":
      return { texto: `${s(i.lote)} · ${s(i.descricao)} · vence ${data(s(i.validade))}`, link: i.lote_id ? `/estoque/${s(i.lote_id)}` : undefined };
    case "DIVERGENCIA_MEGA":
      return { texto: `Código ${s(i.codigo)} · ${s(i.descricao)} · diferença ${typeof i.diferenca_kg === "number" ? `${kg(i.diferenca_kg)} kg` : ""}`, link: "/conciliacao" };
    case "ENTRADA_MEGA_A_CLASSIFICAR":
      return { texto: `Código ${s(i.codigo)} · ${s(i.descricao)} · diferença ${typeof i.diferenca_kg === "number" ? `${kg(i.diferenca_kg)} kg` : ""}`, link: "/entradas-mega" };
    case "EXCECOES_SEMANA":
      return { texto: `${s(i.tipo)} · ${typeof i.kg === "number" ? `${kg(i.kg)} kg` : ""}${i.op ? ` · OP ${s(i.op)}` : ""} · ${s(i.usuario)}`, link: i.lote_id ? `/estoque/${s(i.lote_id)}` : undefined };
    default: // solicitações (fila, peça inteira, material insuficiente…)
      if (i.op !== undefined) {
        const link = codigo.startsWith("FILA_CORTE") ? `/fila-rj?solicitacao=${s(i.id)}` : i.id ? `/solicitacoes/${s(i.id)}` : undefined;
        return { texto: `OP ${s(i.op)}${i.material ? ` · ${s(i.material)}` : ""}${i.cliente ? ` · ${s(i.cliente)}` : ""}${i.prazo ? ` · prazo ${data(s(i.prazo))}` : ""}`, link };
      }
      return { texto: Object.values(i).filter((v) => typeof v === "string" || typeof v === "number").slice(0, 3).join(" · ") };
  }
}

/** Total de pendências (para o subtítulo do Painel). */
export function totalPendencias(grupos: Record<string, Pendencia[]> | undefined) {
  return Object.values(grupos ?? {}).flat().reduce((t, p) => t + Math.max(p.quantidade, 0), 0);
}

/** T03: "o que eu tenho para fazer agora". Uma lista de tarefas por grupo; a mais urgente (ALERTA) primeiro. */
export default function Pendencias() {
  const { dados: r, erro } = usePendencias();
  const [msg, setMsg] = useState("");
  useEffect(() => lerSeVelho(30_000), []);

  if (erro && !r) return <p className="erro" role="alert">Pendências: {erro}</p>;
  if (!r) return <p className="carregando">Carregando pendências…</p>;

  const grupos = Object.entries(r.grupos);
  const varios = grupos.length > 1;
  const entradas = r.entradas_mega_a_classificar?.quantidade;
  const temAtraso = r.atrasos.ATENCAO + r.atrasos.ATRASADO > 0;
  const mostrarResumo = temAtraso || (r.divergencias_mega.quantidade ?? 0) > 0 || (entradas ?? 0) > 0;

  return (
    <>
      {msg && <p className="validacao ok" role="status">{msg}</p>}
      {grupos.map(([g, lista], n) => {
        const comAlgo = lista
          .filter((p) => p.quantidade > 0)
          .sort((a, b) => Number(b.nivel === "ALERTA") - Number(a.nivel === "ALERTA"));
        return (
          <section key={g} className="quadro" aria-label={varios ? `Pendências de ${NOME_GRUPO[g] ?? g}` : "Pendências"}>
            <header>
              <h2>{varios ? `Pendências · ${NOME_GRUPO[g] ?? g}` : "Pendências"}</h2>
              {comAlgo.length > 0 && <span className="desc">{comAlgo.length} tipo(s) de tarefa</span>}
            </header>
            {n === 0 && mostrarResumo && (
              <div className="pendencias-resumo">
                <span className="desc">Pedidos de corte em aberto no RJ:</span>
                <span className="etiqueta ok">{r.atrasos.NORMAL} normal</span>
                <span className={`etiqueta ${r.atrasos.ATENCAO ? "atencao" : ""}`}>{r.atrasos.ATENCAO} atenção</span>
                <span className={`etiqueta ${r.atrasos.ATRASADO ? "ruim" : ""}`}>{r.atrasos.ATRASADO} atrasada(s)</span>
                {entradas !== null && entradas !== undefined && (
                  <Link to="/entradas-mega" className={`etiqueta ${entradas ? "atencao" : "ok"}`}>Entradas do Mega sem lote: {entradas}</Link>
                )}
                {r.divergencias_mega.quantidade !== null && r.divergencias_mega.quantidade !== undefined && (
                  <Link to="/conciliacao" className={`etiqueta ${r.divergencias_mega.quantidade ? "ruim" : "ok"}`}>
                    {r.divergencias_mega.quantidade} divergência(s) com o Mega (&gt; {r.divergencias_mega.limite_kg} kg)
                  </Link>
                )}
              </div>
            )}
            {!comAlgo.length ? (
              <div className="tarefa-ok"><p className="validacao ok">Nada pendente{varios ? ` em ${NOME_GRUPO[g] ?? g}` : ""}.</p></div>
            ) : (
              <ul className="tarefas">
                {comAlgo.map((p) => CODIGOS_PESO_REAL.includes(p.codigo) && p.itens.some((i) => diasDe(i as PecaPesoReal) !== null) ? (
                  <TarefaPesoReal key={p.codigo} p={p as unknown as PendenciaPesoReal} aoEncerrar={(m) => { setMsg(m); void recarregarPendencias(); }} />
                ) : (
                  <li key={p.codigo} className={p.nivel === "ALERTA" ? "tarefa urgente" : "tarefa"}>
                    <span className="tarefa-ic"><Icone nome={tipo(p.codigo).icone} /></span>
                    <div>
                      <h3>{p.titulo}</h3>
                      <ul className="tarefa-itens">
                        {p.itens.slice(0, 4).map((i, k) => {
                          const x = resumo(p.codigo, i);
                          return <li key={k}>{x.link ? <Link to={x.link}>{x.texto}</Link> : x.texto}</li>;
                        })}
                        {p.quantidade > 4 && <li>e mais {p.quantidade - 4}</li>}
                      </ul>
                    </div>
                    <span className="tarefa-qtd" aria-label={`${p.quantidade} pendente(s)`}>{p.quantidade}</span>
                    {p.link ? (
                      <Link className="secundario pequeno" to={p.link}>{tipo(p.codigo).verbo}<Icone nome="seta" /></Link>
                    ) : <span />}
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </>
  );
}

/** Tarefa "Peças inteiras do RJ aguardando peso real" (spec v3.11 T03): dias desde o recebimento, vermelho acima do prazo. */
function TarefaPesoReal({ p, aoEncerrar }: { p: PendenciaPesoReal; aoEncerrar: (msg: string) => void }) {
  const { usuario } = useSessao();
  const podeEncerrar = usuario?.perfil === "ESTOQUE" || usuario?.perfil === "ADMIN";
  const [encerrar, setEncerrar] = useState<PecaPesoReal | null>(null);
  const r = resumirPesoReal({ X: [p] });
  const outras = p.itens.filter((i) => diasDe(i) === null);
  return (
    <li className={r.vencidas || p.nivel === "ALERTA" ? "tarefa urgente" : "tarefa"}>
      <span className="tarefa-ic"><Icone nome="balanca" /></span>
      <div>
        <h3>Peças inteiras do RJ aguardando peso real</h3>
        {r.vencidas > 0 && <p className="validacao erro">{r.vencidas} com mais de {r.limite} dias: bloqueando novas solicitações.</p>}
        <ul className="tarefa-itens">
          {[...r.pecas, ...outras].slice(0, 4).map((i, k) => {
            const d = diasDe(i);
            const venc = vencida(i, r.limite);
            return (
              <li key={i.pendencia_id ?? i.solicitacao_id ?? i.id ?? k} className={venc ? "peso-real-vencida" : undefined}>
                <Link to={linkPeca(i)}>{textoPeca(i)}{i.conteiner ? ` · ${i.conteiner}` : ""}</Link>
                {d !== null && <> · <strong>{d} dia(s)</strong></>}
                {podeEncerrar && i.pendencia_id && (
                  <button type="button" className="link" onClick={() => setEncerrar(i)}>Encerrar pendência</button>
                )}
              </li>
            );
          })}
        </ul>
      </div>
      <span className="tarefa-qtd" aria-label={`${p.quantidade} pendente(s)`}>{p.quantidade}</span>
      <Link className="secundario pequeno" to={linkPeca(r.maisAntiga)}>Informar peso real<Icone nome="seta" /></Link>
      {encerrar && <JanelaEncerrar peca={encerrar} aoFechar={() => setEncerrar(null)} aoGravar={(m) => { setEncerrar(null); aoEncerrar(m); }} />}
    </li>
  );
}

function JanelaEncerrar({ peca, aoFechar, aoGravar }: { peca: PecaPesoReal; aoFechar: () => void; aoGravar: (m: string) => void }) {
  const [just, setJust] = useState("");
  const [erro, setErro] = useState("");
  async function ok() {
    try {
      await encerrarPendenciaPesoReal(peca.pendencia_id!, just.trim());
      aoGravar(`Pendência encerrada: ${textoPeca(peca)}.`);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível encerrar a pendência.");
    }
  }
  return (
    <Janela titulo="Encerrar pendência do peso real" aoFechar={aoFechar}>
      <p><strong>{textoPeca(peca)}</strong>{peca.lote ? ` · lote ${peca.lote}` : ""}</p>
      <p className="desc">Use só para peça que não vai mais ser cortada (ex.: OP cancelada). O estoque não muda; a justificativa fica na auditoria.</p>
      <label>Justificativa<textarea autoFocus rows={3} value={just} onChange={(e) => setJust(e.target.value)} /></label>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="perigo" disabled={just.trim().length < JUSTIFICATIVA_MIN} onClick={() => void ok()}>Encerrar pendência</button>
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}
