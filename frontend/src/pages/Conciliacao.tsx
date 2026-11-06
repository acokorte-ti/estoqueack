import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, kg } from "../api/cliente";
import SyncMega from "../components/SyncMega";

interface Linha { codigo: number; descricao: string; saldo_mega_kg: number; soma_lotes_kg: number; diferenca_kg: number; status: "OK" | "MEGA_MAIOR" | "MEGA_MENOR"; lotes: number;
  explicada_na_t15?: boolean; explicada_t15_kg?: number; diferenca_nao_explicada_kg?: number;
  explicacoes?: { pendencia_id: number; kg: number; motivo: string; motivo_descricao: string; justificativa: string; usuario: string; em: string }[] }
interface Resposta { limite_kg: number; ultima_sincronizacao: string | null;
  totais: { codigos: number; ok: number; mega_maior: number; mega_menor: number; saldo_mega_kg: number; soma_lotes_kg: number }; itens: Linha[] }

const STATUS = { OK: { nome: "OK", classe: "ok" }, MEGA_MAIOR: { nome: "Mega maior", classe: "ruim" }, MEGA_MENOR: { nome: "Mega menor", classe: "atencao" } } as const;

/** T16 Conciliação com o Mega, versão mínima (só leitura): código Mega × soma dos lotes do Estoque Mega. */
export default function Conciliacao() {
  const [soDiv, setSoDiv] = useState(true);
  const [busca, setBusca] = useState("");
  const [r, setR] = useState<Resposta | null>(null);
  const [erro, setErro] = useState("");
  useEffect(() => {
    api.get<Resposta>(`/conciliacao?somente_divergentes=${soDiv}`).then(setR).catch((e: Error) => setErro(e.message));
  }, [soDiv]);

  const q = busca.trim().toUpperCase();
  const itens = (r?.itens ?? []).filter((i) => !q || String(i.codigo).includes(q) || i.descricao.toUpperCase().includes(q));

  return (
    <>
      <header className="cabecalho">
        <h1>Conciliação com o Mega</h1>
        <p>Para cada código do Estoque Mega: saldo no Mega × soma dos lotes no sistema. Diferença acima de {r?.limite_kg ?? 5} kg aparece em destaque. Só consulta nesta versão.</p>
      </header>
      <SyncMega />
      {erro && <p className="erro" role="alert">{erro}</p>}

      {r && (
        <div className="saldos ficha" style={{ marginBottom: "var(--esp-4)" }}>
          <div><span className="desc">Códigos</span><strong className="numero">{r.totais.codigos}</strong></div>
          <div><span className="desc">OK</span><strong className="numero">{r.totais.ok}</strong></div>
          <div><span className="desc">Mega maior</span><strong className="numero">{r.totais.mega_maior}</strong></div>
          <div><span className="desc">Mega menor</span><strong className="numero">{r.totais.mega_menor}</strong></div>
          <div><span className="desc">Saldo Mega</span><strong className="numero">{kg(r.totais.saldo_mega_kg)} kg</strong></div>
          <div><span className="desc">Soma dos lotes</span><strong className="numero">{kg(r.totais.soma_lotes_kg)} kg</strong></div>
        </div>
      )}

      <div className="barra-filtros">
        <label>Código ou descrição<input value={busca} onChange={(e) => setBusca(e.target.value)} /></label>
        <label className="marcar"><input type="checkbox" checked={soDiv} onChange={(e) => setSoDiv(e.target.checked)} /><span>Só divergentes</span></label>
      </div>

      {r && !itens.length ? (
        <div className="estado-vazio"><strong>{soDiv ? "Nenhuma divergência acima do limite" : "Nenhum código"}</strong>{soDiv && "O saldo do sistema bate com o Mega em todos os códigos."}</div>
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead><tr><th>Código</th><th>Descrição</th><th className="num">Saldo Mega</th><th className="num">Soma dos lotes</th><th className="num">Diferença</th><th>Situação</th><th className="num">Lotes</th></tr></thead>
            <tbody>
              {itens.map((i) => (
                <tr key={i.codigo}>
                  <td><Link to={`/estoque?estoque=ESTOQUE_MEGA`} title="Ver lotes do Estoque Mega">{i.codigo}</Link></td>
                  <td>{i.descricao}</td>
                  <td className="num">{kg(i.saldo_mega_kg)}</td>
                  <td className="num">{kg(i.soma_lotes_kg)}</td>
                  <td className={`num ${i.status === "OK" ? "" : "negativo"}`}><strong>{i.diferenca_kg > 0 ? "+" : ""}{kg(i.diferenca_kg)}</strong>{i.explicada_na_t15 && i.diferenca_nao_explicada_kg !== undefined && <small className="desc" style={{ display: "block", fontWeight: 400 }}>sem explicação: {kg(i.diferenca_nao_explicada_kg)}</small>}</td>
                  <td>
                    <span className={`etiqueta ${STATUS[i.status].classe}`}>{STATUS[i.status].nome}</span>
                    {i.explicada_na_t15 && (
                      <span className="etiqueta info" title={(i.explicacoes ?? []).map((x) => `${kg(x.kg)} kg · ${x.motivo_descricao}: ${x.justificativa} (${x.usuario})`).join(" | ")}>
                        explicada na T15{i.explicada_t15_kg ? ` · ${kg(i.explicada_t15_kg)} kg` : ""}
                      </span>
                    )}
                    {i.explicada_na_t15 && i.explicacoes?.map((x) => <small key={x.pendencia_id} className="desc" style={{ display: "block" }}>{x.motivo_descricao}: {x.justificativa}</small>)}
                  </td>
                  <td className="num">{i.lotes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="dica" style={{ marginTop: "var(--esp-3)" }}>"Mega maior": há saldo no Mega que não está em lote (ex.: entrada nova ainda não classificada). "Mega menor": faltou fazer a baixa no Mega (o "Fazer no Mega" do corte em Itu).</p>
    </>
  );
}
