import { useEffect, useState } from "react";
import { api, data } from "../api/cliente";

interface Parametro { chave: string; valor: string; tipo: string; descricao: string; atualizado_em: string | null }

/** Unidade pelo nome do parâmetro (ex.: TOLERANCIA_EXCESSO_RJ_INTEIRO_PCT = 8 %, SA_JANELA_ANTES_DIAS = 7 dias). */
const unidade = (chave: string) => (/_PCT$/.test(chave) ? "%" : /_DIAS$/.test(chave) ? "dias" : /_KG$/.test(chave) ? "kg" : /_MM$/.test(chave) ? "mm" : "");

/** T23 Parâmetros (mínima): os parâmetros que a API já tem, editáveis pelo Admin. */
export default function Parametros() {
  const [lista, setLista] = useState<Parametro[] | null>(null);
  const [edit, setEdit] = useState<Record<string, string>>({});
  const [erro, setErro] = useState("");
  const [msg, setMsg] = useState("");

  const carregar = () => api.get<Parametro[]>("/parametros").then(setLista).catch((e: Error) => setErro(e.message));
  useEffect(() => { void carregar(); }, []);

  async function salvar(p: Parametro) {
    setErro(""); setMsg("");
    try {
      await api.patch(`/parametros/${p.chave}`, { valor: edit[p.chave].trim().replace(",", p.tipo === "NUMERO" ? "." : ",") });
      const { [p.chave]: _, ...resto } = edit; void _;
      setEdit(resto);
      setMsg(`${p.descricao}: salvo.`);
      void carregar();
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível salvar.");
    }
  }

  return (
    <>
      <header className="cabecalho">
        <h1>Parâmetros</h1>
        <p>Tolerâncias, prazos e horários usados pelas validações e avisos. A mudança vale a partir da próxima operação e fica na auditoria.</p>
      </header>
      {msg && <p className="validacao ok" role="status">{msg}</p>}
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="tabela-rolagem">
        <table className="tabela">
          <thead><tr><th>Parâmetro</th><th>Valor</th><th>Alterado em</th><th /></tr></thead>
          <tbody>
            {lista?.map((p) => (
              <tr key={p.chave}>
                <td><strong>{p.descricao}</strong><br /><span className="desc">{p.chave}</span></td>
                <td>
                  <input className={p.tipo === "NUMERO" ? "campo-curto" : ""} inputMode={p.tipo === "NUMERO" ? "decimal" : "text"}
                    aria-label={p.descricao} value={edit[p.chave] ?? (p.tipo === "NUMERO" ? p.valor.replace(".", ",") : p.valor)}
                    onChange={(e) => setEdit({ ...edit, [p.chave]: e.target.value })} />
                  {unidade(p.chave) && <span className="desc"> {unidade(p.chave)}</span>}
                </td>
                <td className="desc">{data(p.atualizado_em)}</td>
                <td>{edit[p.chave] !== undefined && <button className="secundario" onClick={() => void salvar(p)}>Salvar</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
