import { useEffect, useState } from "react";
import { api } from "../api/cliente";

interface Liga { id: number; codigo: string; nome: string; apelidos: string[]; densidade: number; ativo: boolean }

export default function Ligas() {
  const [ligas, setLigas] = useState<Liga[]>([]);
  const [editando, setEditando] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState("");
  const [erro, setErro] = useState("");

  const carregar = () => api.get<Liga[]>("/ligas").then(setLigas).catch((e: Error) => setErro(e.message));
  useEffect(() => {
    void carregar();
  }, []);

  async function salvar(l: Liga) {
    setErro("");
    setMsg("");
    const valor = Number((editando[l.id] ?? "").replace(",", "."));
    try {
      await api.patch(`/ligas/${l.id}`, { densidade: valor });
      setMsg(`Densidade de ${l.codigo} salva: ${valor.toLocaleString("pt-BR")} g/cm³.`);
      const { [l.id]: _, ...resto } = editando;
      void _;
      setEditando(resto);
      void carregar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao salvar.");
    }
  }

  return (
    <>
      <header className="cabecalho">
        <h1>Ligas e densidades</h1>
        <p>
          A densidade é usada só na previsão de peso e nos alertas. Os valores iniciais são de referência técnica;
          confirme com os certificados dos fornecedores.
        </p>
      </header>
      {msg && <p className="validacao ok">{msg}</p>}
      {erro && <p className="erro">{erro}</p>}
      <table className="tabela">
        <thead>
          <tr><th>Liga</th><th>Nome</th><th>Também aparece como</th><th className="num">Densidade (g/cm³)</th><th /></tr>
        </thead>
        <tbody>
          {ligas.map((l) => (
            <tr key={l.id}>
              <td><strong>{l.codigo}</strong></td>
              <td>{l.nome}</td>
              <td className="desc">{l.apelidos.join(", ") || "Sem apelidos"}</td>
              <td className="num">
                <input
                  className="campo-curto"
                  inputMode="decimal"
                  aria-label={`Densidade de ${l.codigo}`}
                  value={editando[l.id] ?? l.densidade.toString().replace(".", ",")}
                  onChange={(e) => setEditando({ ...editando, [l.id]: e.target.value })}
                />
              </td>
              <td>
                {editando[l.id] !== undefined && (
                  <button className="secundario" onClick={() => void salvar(l)}>Salvar</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
