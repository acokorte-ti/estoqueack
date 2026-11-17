import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, data, kg } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { MODO_NOME, material, type SolicItem } from "../api/solicitacao";
import { EtiquetaAtraso, EtiquetaSituacao } from "../components/Etiquetas";
import Janela, { fecharJanela } from "../components/Janela";
import { JUSTIFICATIVA_MIN } from "../components/PainelValidacao";

/** Pesquisa sem diferenciar maiúsculas nem acentos. */
const normalizar = (t: string) => t.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Peso estimado (previsto com sobremetal) do que falta cortar; na parcial, proporcional às peças que faltam. */
const estimado = (s: SolicItem) => {
  if (s.peso_previsto_kg === null) return null;
  const faltam = s.quantidade - s.pecas_cortadas;
  return s.pecas_cortadas && s.quantidade > 0 ? (s.peso_previsto_kg * Math.max(faltam, 0)) / s.quantidade : s.peso_previsto_kg;
};

/** Dias esperando no RJ, desde o envio (API: dias_em_aberto; reserva: conta pela data de envio ou da solicitação). */
const diasEsperando = (s: SolicItem) => {
  if (s.dias_em_aberto !== null && s.dias_em_aberto !== undefined) return s.dias_em_aberto;
  const ref = s.enviada_em ?? s.data;
  return ref ? Math.max(0, Math.floor((Date.now() - new Date(ref.length === 10 ? `${ref}T12:00:00` : ref).getTime()) / 86400000)) : null;
};
const inicioEspera = (s: SolicItem) => {
  const ref = s.enviada_em ?? s.data;
  return ref ? new Date(ref.length === 10 ? `${ref}T12:00:00` : ref).getTime() : Number.MAX_SAFE_INTEGER;
};
type Ordem = "ESPERA" | "PRAZO";
const ORDEM_NOME: Record<Ordem, string> = { ESPERA: "há mais tempo esperando", PRAZO: "prazo" };

/** T09 Fila RJ: o que o Marcelo tem para cortar, por prazo. Cartões grandes para tablet/celular. */
export default function FilaRj() {
  const { usuario } = useSessao();
  const corta = usuario?.perfil === "OPERACAO_RJ" || usuario?.perfil === "ADMIN";
  const [params] = useSearchParams();
  const destaque = Number(params.get("solicitacao")) || null;
  const [fila, setFila] = useState<SolicItem[] | null>(null);
  const [erro, setErro] = useState("");
  const [insuf, setInsuf] = useState<SolicItem | null>(null);
  const [aviso, setAviso] = useState("");
  const [busca, setBusca] = useState("");
  // padrão: há mais tempo esperando no topo (Eduardo, 2026-11-17); "prazo" = ordem da API
  const [ordem, setOrdem] = useState<Ordem>("ESPERA");
  // cartões compactos: abrem ao clicar; o que veio do link do sino já abre
  const [abertos, setAbertos] = useState<Set<number>>(() => new Set(destaque ? [destaque] : []));
  const alternar = (id: number) => setAbertos((a) => { const n = new Set(a); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const visiveis = useMemo(() => {
    const termo = normalizar(busca.trim());
    const achados = !fila ? [] : !termo ? fila
      : fila.filter((s) => normalizar([s.op, s.cliente, s.lote.liga, s.lote.bitola, s.lote.conteiner, s.lote.codigo, material(s.lote)].filter(Boolean).join(" ")).includes(termo));
    if (ordem === "PRAZO") return achados;
    // sort estável: empate no envio fica na ordem de prazo da API
    return [...achados].sort((a, b) => inicioEspera(a) - inicioEspera(b));
  }, [fila, busca, ordem]);
  const totalEstimado = useMemo(() => visiveis.reduce((t, s) => t + (estimado(s) ?? 0), 0), [visiveis]);

  const carregar = useCallback(async () => {
    try {
      const r = await api.get<SolicItem[] | { itens: SolicItem[] }>("/fila-rj");
      setFila(Array.isArray(r) ? r : r.itens);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível carregar os cortes a fazer.");
    }
  }, []);
  useEffect(() => {
    void carregar();
  }, [carregar]);

  return (
    <>
      <header className="cabecalho cabecalho-acao nao-imprimir">
        <div>
          <h1>Cortes a fazer no RJ</h1>
          <p>Solicitações enviadas e parciais, {ordem === "ESPERA" ? "da que está há mais tempo esperando para a mais nova" : "da mais urgente (prazo) para a menos urgente"}.</p>
        </div>
        {!!visiveis.length && <button className="secundario" onClick={() => window.print()}>Imprimir lista de corte</button>}
      </header>

      {/* Versão impressa (A4 deitada, sem menu nem cabeçalho/rodapé do navegador): só aparece no papel.
          Margem da folha = 0 só enquanto esta tela está aberta; o respiro vem do padding e das linhas de cabeça/pé da tabela, que se repetem em cada página. */}
      {fila && (
        <section className="so-impressao lista-corte">
          <style>{"@page { size: A4 landscape; margin: 0; }"}</style>
          <table>
            <colgroup>
              <col style={{ width: "17mm" }} /><col style={{ width: "36mm" }} /><col /><col style={{ width: "17mm" }} /><col style={{ width: "21mm" }} />
              <col style={{ width: "23mm" }} /><col style={{ width: "11mm" }} /><col style={{ width: "36mm" }} /><col style={{ width: "21mm" }} /><col style={{ width: "23mm" }} />
            </colgroup>
            <thead>
              <tr className="lista-corte-titulo">
                <th colSpan={10}>
                  <strong>Lista de corte · RJ</strong> · {new Date().toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })}
                  {" "}· {visiveis.length} item(ns) · {kg(totalEstimado)} kg estimados · por {ORDEM_NOME[ordem]}{busca.trim() ? ` · pesquisa “${busca.trim()}”` : ""}
                </th>
              </tr>
              <tr className="lista-corte-colunas">
                <th>OP</th><th>Material · contêiner</th><th>Instrução de corte</th><th>Qtd</th><th className="num">Peso estimado (kg)</th>
                <th>Prazo</th><th>Dias</th><th>Item · cliente</th><th>Peças cortadas</th><th>Peso real (kg)</th>
              </tr>
            </thead>
            <tbody>
              {visiveis.map((s) => {
                const est = estimado(s);
                return (
                  <tr key={s.id}>
                    <td className="sem-quebra"><strong>{s.op}</strong></td>
                    <td><strong>{material(s.lote)}</strong><br />{s.lote.conteiner ?? "—"}</td>
                    <td><strong>{s.instrucao ?? `${s.quantidade} peça(s)`}</strong>{s.instrucao_processo && <><br />{s.instrucao_processo}</>}{s.modo === "TRAZER_INTEIRA" && <><br />(peça inteira)</>}</td>
                    <td>{s.pecas_cortadas ? `faltam ${s.quantidade - s.pecas_cortadas} de ${s.quantidade}` : s.quantidade}</td>
                    <td className="num sem-quebra">{est === null ? "—" : kg(est)}</td>
                    <td className="sem-quebra">{data(s.prazo)}</td>
                    <td className="sem-quebra">{diasEsperando(s) ?? "—"}{s.atraso === "ATRASADO" ? " !" : ""}</td>
                    <td>{s.item_descricao ?? "—"}<br />{s.cliente ?? "—"}</td>
                    <td className="em-branco" /><td className="em-branco" />
                  </tr>
                );
              })}
              <tr className="lista-corte-total">
                <td colSpan={4}>Total estimado · {visiveis.length} item(ns)</td>
                <td className="num sem-quebra">{kg(totalEstimado)}</td>
                <td colSpan={3} /><td className="em-branco" /><td className="em-branco" />
              </tr>
            </tbody>
            <tfoot><tr className="lista-corte-pe"><td colSpan={10} /></tr></tfoot>
          </table>
        </section>
      )}
      {erro && <p className="erro" role="alert">{erro}</p>}
      {aviso && <p className="validacao ok" role="status">{aviso}</p>}

      {fila && !fila.length && (
        <div className="estado-vazio"><strong>Nenhum corte a fazer</strong>Nenhuma solicitação esperando corte no RJ.</div>
      )}

      {!!fila?.length && (
        <div className="barra-filtros nao-imprimir">
          <label style={{ flexBasis: "24rem" }}>Pesquisar
            <input type="search" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="OP, cliente, liga, bitola, contêiner ou lote" />
          </label>
          <label>Ordem
            <select value={ordem} onChange={(e) => setOrdem(e.target.value as Ordem)}>
              <option value="ESPERA">Há mais tempo esperando</option>
              <option value="PRAZO">Prazo</option>
            </select>
          </label>
          <span className="desc">{busca.trim() ? `${visiveis.length} de ${fila.length}` : `${fila.length}`} corte(s) · {kg(totalEstimado)} kg estimados</span>
        </div>
      )}
      {fila && !!fila.length && !visiveis.length && (
        <div className="estado-vazio nao-imprimir"><strong>Nada encontrado</strong>Nenhum corte com “{busca.trim()}”.</div>
      )}

      <ul className="cartoes cartoes-lista nao-imprimir">
        {visiveis.map((s) => {
          const faltam = s.quantidade - s.pecas_cortadas;
          const pecas = s.pecas_cortadas ? `faltam ${faltam} de ${s.quantidade}` : `${s.quantidade}`;
          const aberto = abertos.has(s.id);
          const est = estimado(s);
          const espera = diasEsperando(s);
          return (
            <li key={s.id} className={["cartao", "cartao-compacto", s.atraso === "ATRASADO" ? "atrasado" : "", destaque === s.id ? "destaque" : ""].join(" ")}>
              <button type="button" className="cartao-linha" aria-expanded={aberto} onClick={() => alternar(s.id)}>
                <span className="cartao-op">OP {s.op}</span>
                <span className="cartao-linha-material">{material(s.lote)}</span>
                {espera !== null && <span className="cartao-espera">há {espera} dia{espera === 1 ? "" : "s"}</span>}
                <span>{pecas} peça(s)</span>
                {est !== null && <span>≈ {kg(est)} kg</span>}
                <span>prazo {data(s.prazo)}</span>
                <span className="cartao-linha-etiquetas">
                  <EtiquetaAtraso a={s.atraso} />
                  {s.situacao !== "ENVIADA" && <EtiquetaSituacao s={s.situacao} />}
                </span>
                <span className="cartao-linha-seta" aria-hidden="true">{aberto ? "▴" : "▾"}</span>
              </button>
              {aberto && (
                <>
                  <p className="cartao-instrucao">{s.instrucao ?? `${s.quantidade} peça(s)`}</p>
                  {s.instrucao_processo && <p className="etiqueta info" style={{ alignSelf: "flex-start" }}>{s.instrucao_processo}</p>}
                  <dl className="dados">
                    <div><dt>Material</dt><dd>{material(s.lote)}</dd></div>
                    <div><dt>Contêiner</dt><dd>{s.lote.conteiner ?? "—"}</dd></div>
                    <div><dt>Lote</dt><dd>{s.lote.codigo}</dd></div>
                    <div><dt>Modo</dt><dd>{MODO_NOME[s.modo]}</dd></div>
                    <div><dt>Peças</dt><dd>{pecas}</dd></div>
                    <div><dt>Peso estimado</dt><dd>{est === null ? "—" : `${kg(est)} kg`}{s.pecas_cortadas > 0 && s.peso_previsto_kg !== null && <span className="desc"> (das que faltam; {kg(s.peso_previsto_kg)} kg no total)</span>}</dd></div>
                    <div><dt>Prazo</dt><dd>{data(s.prazo)}</dd></div>
                    <div className="largo"><dt>Item / cliente</dt><dd>{s.item_descricao ?? "—"} · {s.cliente ?? "—"}</dd></div>
                  </dl>
                  {corta && (
                    <div className="cartao-acoes">
                      <Link className="primario" to={`/fila-rj/${s.id}/corte`}>Registrar corte</Link>
                      {s.situacao !== "MATERIAL_INSUFICIENTE" && <button className="secundario" onClick={() => setInsuf(s)}>Material insuficiente</button>}
                    </div>
                  )}
                </>
              )}
            </li>
          );
        })}
      </ul>

      {insuf && <JanelaInsuficiente s={insuf} aoFechar={() => setInsuf(null)} aoGravar={() => { setInsuf(null); setAviso(`OP ${insuf.op}: Itu foi avisado do material insuficiente.`); void carregar(); }} />}
    </>
  );
}

function JanelaInsuficiente({ s, aoFechar, aoGravar }: { s: SolicItem; aoFechar: () => void; aoGravar: () => void }) {
  const [t, setT] = useState("");
  const [erro, setErro] = useState("");
  async function ok() {
    try {
      await api.post(`/solicitacoes/${s.id}/material-insuficiente`, { observacao: t.trim() });
      aoGravar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível registrar.");
    }
  }
  const falta = JUSTIFICATIVA_MIN - t.trim().length;
  return (
    <Janela titulo={`Material insuficiente · OP ${s.op}`} aoFechar={aoFechar}>
      <p className="desc">Itu é avisado e troca o lote ou cancela a solicitação.</p>
      <label>O que aconteceu?<textarea autoFocus rows={3} value={t} onChange={(e) => setT(e.target.value)} placeholder="Ex.: barra do CH33K acabou, sobrou só 40 mm" /></label>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="primario" disabled={falta > 0} onClick={() => void ok()}>Avisar Itu</button>
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}
