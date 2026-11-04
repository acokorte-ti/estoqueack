import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, data, kg, qs } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { MODO_NOME, material, numerosCop, type SituacaoSolic, type SolicItem } from "../api/solicitacao";
import { EtiquetaAtraso, EtiquetaSituacao } from "../components/Etiquetas";

const GRUPOS: { chave: string; nome: string; situacao: SituacaoSolic[] }[] = [
  { chave: "abertas", nome: "Em andamento", situacao: ["RASCUNHO", "ENVIADA", "MATERIAL_INSUFICIENTE", "CORTADA_PARCIAL", "CORTADA", "EM_COP", "SA_PRONTO", "EM_TRANSITO", "AGUARDANDO_CORTE_ITU"] },
  { chave: "rj", nome: "No RJ para cortar", situacao: ["ENVIADA", "CORTADA_PARCIAL", "MATERIAL_INSUFICIENTE"] },
  { chave: "rascunhos", nome: "Rascunhos", situacao: ["RASCUNHO"] },
  { chave: "transito", nome: "COP / trânsito", situacao: ["CORTADA", "EM_COP", "SA_PRONTO", "EM_TRANSITO"] },
  { chave: "itu", nome: "Aguardando corte em Itu", situacao: ["AGUARDANDO_CORTE_ITU"] },
  { chave: "concluidas", nome: "Concluídas", situacao: ["CONCLUIDA"] },
  { chave: "canceladas", nome: "Canceladas", situacao: ["CANCELADA"] },
];

interface Pagina { itens: SolicItem[]; total: number; pagina: number; por_pagina: number }

/** T08 Solicitações de corte. */
export default function Solicitacoes() {
  const { usuario } = useSessao();
  const nav = useNavigate();
  const podeCriar = usuario?.perfil === "ESTOQUE" || usuario?.perfil === "ADMIN";
  const [grupo, setGrupo] = useState("abertas");
  const [f, setF] = useState({ op: "", cliente: "", liga: "", conteiner: "", de: "", ate: "", somente_atrasadas: false });
  const [pag, setPag] = useState(1);
  const [r, setR] = useState<Pagina | null>(null);
  const [erro, setErro] = useState("");

  const g = GRUPOS.find((x) => x.chave === grupo)!;
  const base = { situacao: g.situacao, op: f.op.trim(), cliente: f.cliente.trim(), liga: f.liga.trim(),
    conteiner: f.conteiner.trim(), de: f.de, ate: f.ate, somente_atrasadas: f.somente_atrasadas || undefined };
  const exportar = `/api/exportar/solicitacoes.xlsx${qs(base)}`;

  const carregar = useCallback(async () => {
    setErro("");
    try {
      setR(await api.get<Pagina>(`/solicitacoes${qs({ ...base, pagina: pag, por_pagina: 50 })}`));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível carregar as solicitações.");
    }
  }, [grupo, f, pag]);

  useEffect(() => {
    const t = window.setTimeout(() => void carregar(), 250); // espera parar de digitar
    return () => window.clearTimeout(t);
  }, [carregar]);

  const itens = r?.itens ?? [];
  const paginas = r ? Math.max(1, Math.ceil(r.total / r.por_pagina)) : 1;

  return (
    <>
      <header className="cabecalho cabecalho-acao">
        <div>
          <h1>Solicitações de corte</h1>
          <p>Todas as solicitações, do rascunho até a conclusão. Clique numa linha para ver o detalhe e as ações.</p>
        </div>
        <div className="botoes">
          <a className="secundario" href={exportar} download>Exportar para Excel</a>
          {podeCriar && <Link className="primario" to="/solicitacoes/nova">Nova solicitação</Link>}
        </div>
      </header>

      <div className="chips" role="group" aria-label="Situação" style={{ marginBottom: "var(--esp-4)" }}>
        {GRUPOS.map((g) => (
          <button key={g.chave} type="button" className="chip" aria-pressed={grupo === g.chave} onClick={() => { setGrupo(g.chave); setPag(1); }}>{g.nome}</button>
        ))}
      </div>

      <div className="barra-filtros">
        <label>OP<input inputMode="numeric" value={f.op} onChange={(e) => { setF({ ...f, op: e.target.value }); setPag(1); }} /></label>
        <label>Cliente<input value={f.cliente} onChange={(e) => { setF({ ...f, cliente: e.target.value }); setPag(1); }} /></label>
        <label className="marcar">
          <input type="checkbox" checked={f.somente_atrasadas} onChange={(e) => { setF({ ...f, somente_atrasadas: e.target.checked }); setPag(1); }} />
          <span>Só atrasadas</span>
        </label>
      </div>
      <details className="avancado mais-filtros" open={!!(f.liga || f.conteiner || f.de || f.ate)}>
        <summary>Mais filtros (liga, contêiner, período)</summary>
        <div className="barra-filtros">
          <label>Liga<input value={f.liga} onChange={(e) => { setF({ ...f, liga: e.target.value.toUpperCase() }); setPag(1); }} /></label>
          <label>Contêiner<input value={f.conteiner} onChange={(e) => { setF({ ...f, conteiner: e.target.value.toUpperCase() }); setPag(1); }} /></label>
          <label>De<input type="date" value={f.de} onChange={(e) => { setF({ ...f, de: e.target.value }); setPag(1); }} /></label>
          <label>Até<input type="date" value={f.ate} onChange={(e) => { setF({ ...f, ate: e.target.value }); setPag(1); }} /></label>
        </div>
      </details>

      {erro && <p className="erro" role="alert">{erro}</p>}

      {r && !itens.length ? (
        <div className="estado-vazio">
          <strong>Nenhuma solicitação aqui</strong>
          {podeCriar ? "Use \"Nova solicitação\" para pedir um corte ao RJ." : "Mude o filtro para ver outras situações."}
        </div>
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela tabela-clicavel">
            <thead>
              <tr>
                <th>Solicitação</th><th>OP / cliente</th><th>Material / contêiner</th><th>Modo</th>
                <th className="num">Peças</th><th className="num">Previsto</th><th className="num">Real</th>
                <th>Prazo</th><th>Situação</th><th>COP</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((s) => (
                <tr key={s.id} className={s.atraso === "ATRASADO" ? "atrasado" : ""} onClick={() => nav(`/solicitacoes/${s.id}`)}>
                  <td><Link to={`/solicitacoes/${s.id}`} onClick={(e) => e.stopPropagation()}>{s.numero}</Link><br /><span className="desc">{data(s.data)}</span></td>
                  <td><strong>{s.op}</strong>{!s.op_confirmada_mega && <span className="etiqueta atencao" title="Dados da OP não confirmados no Mega"> não confirmada</span>}<br /><span className="desc">{s.cliente ?? "—"}</span></td>
                  <td>{material(s.lote)}<br /><span className="desc">{s.lote.conteiner ?? "—"} · {s.lote.codigo}</span></td>
                  <td>{MODO_NOME[s.modo]}</td>
                  <td className="num">{s.pecas_cortadas ? `${s.pecas_cortadas} / ${s.quantidade}` : s.quantidade}</td>
                  <td className="num">{s.peso_previsto_kg !== null ? `${kg(s.peso_previsto_kg)} kg` : "—"}</td>
                  <td className="num">{s.peso_real_kg !== null ? `${kg(s.peso_real_kg)} kg` : "—"}</td>
                  <td>{data(s.prazo)}{s.atraso && <><br /><EtiquetaAtraso a={s.atraso} dias={s.dias_em_aberto} /></>}</td>
                  <td><EtiquetaSituacao s={s.situacao} />{s.encerrada_saldo_pendente && <><br /><span className="desc">encerrada com saldo pendente</span></>}</td>
                  <td>{numerosCop(s.cops) || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {r && paginas > 1 && (
        <div className="paginacao">
          <button className="secundario" disabled={pag <= 1} onClick={() => setPag(pag - 1)}>Anterior</button>
          <span>Página {pag} de {paginas} · {r.total} solicitações</span>
          <button className="secundario" disabled={pag >= paginas} onClick={() => setPag(pag + 1)}>Próxima</button>
        </div>
      )}
    </>
  );
}
