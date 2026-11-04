import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, data, kg } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { MODO_NOME, material, type SolicItem } from "../api/solicitacao";
import { EtiquetaAtraso, EtiquetaSituacao } from "../components/Etiquetas";
import Janela, { fecharJanela } from "../components/Janela";
import { JUSTIFICATIVA_MIN } from "../components/PainelValidacao";

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

  const carregar = useCallback(async () => {
    try {
      const r = await api.get<SolicItem[] | { itens: SolicItem[] }>("/fila-rj");
      setFila(Array.isArray(r) ? r : r.itens);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível carregar a fila.");
    }
  }, []);
  useEffect(() => {
    void carregar();
  }, [carregar]);

  return (
    <>
      <header className="cabecalho cabecalho-acao nao-imprimir">
        <div>
          <h1>Fila RJ</h1>
          <p>Solicitações enviadas e parciais, da mais urgente para a menos urgente.</p>
        </div>
        {!!fila?.length && <button className="secundario" onClick={() => window.print()}>Imprimir lista de corte</button>}
      </header>

      {/* Versão impressa (A4, sem menu): só aparece no papel */}
      {fila && (
        <section className="so-impressao lista-corte">
          <div className="lista-corte-cabeca">
            <img src="/logo-acokorte.png" alt="AçoKorte" width={150} height={30} />
            <div>
              <h1>Lista de corte · RJ</h1>
              <p>Impressa em {new Date().toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })} · {fila.length} solicitação(ões), por prazo</p>
            </div>
          </div>
          <table>
            <thead>
              <tr><th>OP</th><th>Material · contêiner</th><th>Instrução de corte</th><th>Qtd</th><th>Prazo</th><th>Dias</th><th>Item · cliente</th><th>Peças cortadas</th><th>Peso real (kg)</th></tr>
            </thead>
            <tbody>
              {fila.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.op}</strong></td>
                  <td>{material(s.lote)}<br />{s.lote.conteiner ?? "—"}</td>
                  <td><strong>{s.instrucao ?? `${s.quantidade} peça(s)`}</strong>{s.instrucao_processo && <><br />{s.instrucao_processo}</>}{s.modo === "TRAZER_INTEIRA" && <><br />(peça inteira)</>}</td>
                  <td>{s.pecas_cortadas ? `${s.quantidade - s.pecas_cortadas} de ${s.quantidade}` : s.quantidade}</td>
                  <td>{data(s.prazo)}</td>
                  <td>{s.dias_em_aberto ?? "—"}{s.atraso === "ATRASADO" ? " !" : ""}</td>
                  <td>{s.item_descricao ?? "—"}<br />{s.cliente ?? "—"}</td>
                  <td className="em-branco" /><td className="em-branco" />
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
      {erro && <p className="erro" role="alert">{erro}</p>}
      {aviso && <p className="validacao ok" role="status">{aviso}</p>}

      {fila && !fila.length && (
        <div className="estado-vazio"><strong>Fila vazia</strong>Nenhuma solicitação esperando corte no RJ.</div>
      )}

      <ul className="cartoes nao-imprimir">
        {fila?.map((s) => {
          const faltam = s.quantidade - s.pecas_cortadas;
          return (
            <li key={s.id} className={["cartao", s.atraso === "ATRASADO" ? "atrasado" : "", destaque === s.id ? "destaque" : ""].join(" ")}>
              <div className="cartao-topo">
                <span className="cartao-op">OP {s.op}</span>
                <EtiquetaAtraso a={s.atraso} dias={s.dias_em_aberto} />
                {s.situacao !== "ENVIADA" && <EtiquetaSituacao s={s.situacao} />}
              </div>
              <p className="cartao-instrucao">{s.instrucao ?? `${s.quantidade} peça(s)`}</p>
              {s.instrucao_processo && <p className="etiqueta info" style={{ alignSelf: "flex-start" }}>{s.instrucao_processo}</p>}
              <dl className="dados">
                <div><dt>Material</dt><dd>{material(s.lote)}</dd></div>
                <div><dt>Contêiner</dt><dd>{s.lote.conteiner ?? "—"}</dd></div>
                <div><dt>Modo</dt><dd>{MODO_NOME[s.modo]}</dd></div>
                <div><dt>Peças</dt><dd>{s.pecas_cortadas ? `faltam ${faltam} de ${s.quantidade}` : s.quantidade}</dd></div>
                <div><dt>Previsto</dt><dd>{s.peso_previsto_kg !== null ? `${kg(s.peso_previsto_kg)} kg` : "—"}</dd></div>
                <div><dt>Prazo</dt><dd>{data(s.prazo)}</dd></div>
                <div className="largo"><dt>Item / cliente</dt><dd>{s.item_descricao ?? "—"} · {s.cliente ?? "—"}</dd></div>
              </dl>
              {corta && (
                <div className="cartao-acoes">
                  <Link className="primario" to={`/fila-rj/${s.id}/corte`}>Registrar corte</Link>
                  {s.situacao !== "MATERIAL_INSUFICIENTE" && <button className="secundario" onClick={() => setInsuf(s)}>Material insuficiente</button>}
                </div>
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
      <label>O que aconteceu?<textarea autoFocus rows={3} value={t} onChange={(e) => setT(e.target.value)} placeholder="Ex.: barra do CH33K acabou, sobrou só 40 mm" />
        <small className="dica">{falta > 0 ? `Faltam ${falta} caractere(s).` : "Ok."}</small></label>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="primario" disabled={falta > 0} onClick={() => void ok()}>Avisar Itu</button>
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}
