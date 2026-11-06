import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, data, kg } from "../api/cliente";

type Item = Record<string, unknown>;
interface Pendencia { codigo: string; titulo: string; quantidade: number; nivel: "ALERTA" | "NORMAL"; link: string | null; itens: Item[] }
interface Resposta {
  perfil: string;
  grupos: Record<string, Pendencia[]>;
  atrasos: { NORMAL: number; ATENCAO: number; ATRASADO: number };
  divergencias_mega: { quantidade: number | null; limite_kg: number };
  entradas_mega_a_classificar?: { quantidade: number | null } | null; // null para Operação RJ (P10)
}

const NOME_GRUPO: Record<string, string> = { ESTOQUE: "Itu", OPERACAO_RJ: "Barra Mansa", ANALISE: "Análise" };
const s = (v: unknown) => (v === null || v === undefined ? "" : String(v));

/** Uma linha curta para cada item, conforme o tipo de pendência (contrato F1 §11). */
function resumo(codigo: string, i: Item): { texto: string; link?: string } {
  switch (codigo) {
    case "SA_SEGURANDO_COP":
      return { texto: `COP ${s(i.cop)}: ${s(i.sas_pendentes)} SA(s) pendente(s) de ${s(i.itens)}`, link: i.cop_id ? `/cops/${s(i.cop_id)}` : undefined };
    case "COP_EM_TRANSITO": case "COP_ABERTO": case "COP_AGUARDANDO_SA": case "COP_AGUARDANDO_NF":
      return { texto: `COP ${s(i.numero)} · ${s(i.qtd_itens)} item(ns) · ${typeof i.peso_total_kg === "number" ? `${kg(i.peso_total_kg)} kg` : ""}`,
        link: codigo === "COP_EM_TRANSITO" ? `/recebimentos/${s(i.id)}` : `/cops/${s(i.id)}` };
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

/** T03: "o que eu tenho para fazer agora", antes da barra de estoque. */
export default function Pendencias() {
  const [r, setR] = useState<Resposta | null>(null);
  const [erro, setErro] = useState("");
  useEffect(() => {
    api.get<Resposta>("/painel/pendencias").then(setR).catch((e: Error) => setErro(e.message));
  }, []);

  if (erro) return <p className="erro" role="alert">Pendências: {erro}</p>;
  if (!r) return <p className="carregando">Carregando pendências…</p>;

  const grupos = Object.entries(r.grupos);
  const varios = grupos.length > 1;
  const entradas = r.entradas_mega_a_classificar?.quantidade;
  const temAtraso = r.atrasos.ATENCAO + r.atrasos.ATRASADO > 0;

  return (
    <section className="pendencias" aria-label="Pendências">
      {(temAtraso || (r.divergencias_mega.quantidade ?? 0) > 0 || (entradas ?? 0) > 0) && (
        <div className="pendencias-resumo">
          <span className="desc">Solicitações em aberto no RJ:</span>
          <span className="etiqueta ok">{r.atrasos.NORMAL} normal</span>
          <span className={`etiqueta ${r.atrasos.ATENCAO ? "atencao" : ""}`}>{r.atrasos.ATENCAO} atenção</span>
          <span className={`etiqueta ${r.atrasos.ATRASADO ? "ruim" : ""}`}>{r.atrasos.ATRASADO} atrasada(s)</span>
          {entradas !== null && entradas !== undefined && (
            <Link to="/entradas-mega" className={`etiqueta ${entradas ? "atencao" : "ok"}`}>Entradas Mega a classificar: {entradas}</Link>
          )}
          {r.divergencias_mega.quantidade !== null && r.divergencias_mega.quantidade !== undefined && (
            <Link to="/conciliacao" className={`etiqueta ${r.divergencias_mega.quantidade ? "ruim" : "ok"}`}>
              {r.divergencias_mega.quantidade} divergência(s) com o Mega (&gt; {r.divergencias_mega.limite_kg} kg)
            </Link>
          )}
        </div>
      )}
      {grupos.map(([g, lista]) => {
        const comAlgo = lista.filter((p) => p.quantidade > 0);
        return (
          <div key={g} className="pendencias-grupo">
            {varios && <h2>{NOME_GRUPO[g] ?? g}</h2>}
            {!comAlgo.length ? <p className="validacao ok">Nada pendente{varios ? ` em ${NOME_GRUPO[g] ?? g}` : ""}.</p> : (
              <ul className="cartoes-pendencia">
                {comAlgo.map((p) => (
                  <li key={p.codigo} className={p.nivel === "ALERTA" ? "pendencia alerta" : "pendencia"}>
                    <div className="pendencia-topo">
                      <strong className="numero">{p.quantidade}</strong>
                      <span>{p.titulo}</span>
                    </div>
                    <ul className="pendencia-itens">
                      {p.itens.slice(0, 5).map((i, k) => {
                        const x = resumo(p.codigo, i);
                        return <li key={k}>{x.link ? <Link to={x.link}>{x.texto}</Link> : x.texto}</li>;
                      })}
                    </ul>
                    {p.link && <Link className="secundario" to={p.link}>Abrir{p.quantidade > 5 ? ` todas (${p.quantidade})` : ""}</Link>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </section>
  );
}
