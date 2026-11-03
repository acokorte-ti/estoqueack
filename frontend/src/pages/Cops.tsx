import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, data, kg, qs } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { nfTexto, SITUACAO_COP, type Cop, type SituacaoCop } from "../api/cop";
import Janela, { fecharJanela } from "../components/Janela";

const GRUPOS: { chave: string; nome: string; situacao: SituacaoCop[] }[] = [
  { chave: "andamento", nome: "Em andamento", situacao: ["ABERTO", "FECHADO", "ENVIADO", "RECEBIDO_PARCIAL"] },
  { chave: "abertos", nome: "Abertos", situacao: ["ABERTO"] },
  { chave: "fechados", nome: "Fechados (SA / NF)", situacao: ["FECHADO"] },
  { chave: "transito", nome: "Em trânsito", situacao: ["ENVIADO", "RECEBIDO_PARCIAL"] },
  { chave: "recebidos", nome: "Recebidos", situacao: ["RECEBIDO"] },
];

/** T11: lista de COPs. Operação RJ cria e monta; Estoque Itu e Análise consultam. */
export default function Cops() {
  const { usuario } = useSessao();
  const nav = useNavigate();
  const monta = usuario?.perfil === "OPERACAO_RJ" || usuario?.perfil === "ADMIN";
  const [grupo, setGrupo] = useState("andamento");
  const [lista, setLista] = useState<Cop[] | null>(null);
  const [erro, setErro] = useState("");
  const [novo, setNovo] = useState(false);

  const carregar = useCallback(async () => {
    setErro("");
    const g = GRUPOS.find((x) => x.chave === grupo)!;
    try {
      setLista(await api.get<Cop[]>(`/cops${qs({ situacao: g.situacao })}`));
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível carregar os COPs.");
    }
  }, [grupo]);
  useEffect(() => {
    void carregar();
  }, [carregar]);

  return (
    <>
      <header className="cabecalho cabecalho-acao">
        <div>
          <h1>COP</h1>
          <p>Monte o COP com os cortes prontos, feche para Itu fazer os SAs e envie quando os SAs e a NF estiverem prontos.</p>
        </div>
        {monta && <button className="primario" onClick={() => setNovo(true)}>Novo COP</button>}
      </header>

      <div className="chips" role="group" aria-label="Situação" style={{ marginBottom: "var(--esp-4)" }}>
        {GRUPOS.map((g) => (
          <button key={g.chave} type="button" className="chip" aria-pressed={grupo === g.chave} onClick={() => setGrupo(g.chave)}>{g.nome}</button>
        ))}
      </div>
      {erro && <p className="erro" role="alert">{erro}</p>}

      {lista && !lista.length ? (
        <div className="estado-vazio"><strong>Nenhum COP aqui</strong>{monta ? "Use \"Novo COP\" para começar a montar o próximo." : "Mude o filtro para ver outros COPs."}</div>
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela tabela-clicavel">
            <thead><tr><th>COP</th><th>Situação</th><th>Data</th><th className="num">Itens</th><th className="num">Peso</th><th>NF</th></tr></thead>
            <tbody>
              {lista?.map((c) => (
                <tr key={c.id} onClick={() => nav(`/cops/${c.id}`)}>
                  <td><Link to={`/cops/${c.id}`} onClick={(e) => e.stopPropagation()}><strong>{c.numero}</strong></Link></td>
                  <td><span className={`etiqueta ${SITUACAO_COP[c.situacao]?.classe ?? ""}`}>{SITUACAO_COP[c.situacao]?.nome ?? c.situacao}</span></td>
                  <td>{data(c.enviado_em ?? c.fechado_em ?? c.data)}</td>
                  <td className="num">{c.qtd_itens}</td>
                  <td className="num">{kg(c.peso_total_kg)} kg</td>
                  <td>{c.nfs.length ? c.nfs.map(nfTexto).join(", ") : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {novo && <JanelaNovoCop aoFechar={() => setNovo(false)} aoGravar={(id) => nav(`/cops/${id}`)} />}
    </>
  );
}

function JanelaNovoCop({ aoFechar, aoGravar }: { aoFechar: () => void; aoGravar: (id: number) => void }) {
  const [numero, setNumero] = useState("");
  const [sugerido, setSugerido] = useState<number | null>(null);
  const [obs, setObs] = useState("");
  const [erro, setErro] = useState("");
  useEffect(() => {
    api.get<{ numero: number }>("/cops/proximo-numero").then((r) => { setSugerido(r.numero); setNumero(String(r.numero)); }).catch(() => undefined);
  }, []);
  async function ok(e: FormEvent) {
    e.preventDefault();
    setErro("");
    try {
      const c = await api.post<Cop>("/cops", { numero: Number(numero) || null, observacao: obs.trim() || null });
      aoGravar(c.id);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível criar o COP.");
    }
  }
  return (
    <Janela titulo="Novo COP" aoFechar={aoFechar}>
      <form onSubmit={(e) => void ok(e)} className="bloco-passo" style={{ gap: "var(--esp-4)" }}>
        <label>
          <span className="rotulo">Nº do COP {sugerido !== null && Number(numero) === sugerido && <span className="sugerido">próximo da sequência</span>}</span>
          <input inputMode="numeric" autoFocus value={numero} onChange={(e) => setNumero(e.target.value)} />
        </label>
        <label>Observação<input value={obs} onChange={(e) => setObs(e.target.value)} /></label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <div className="botoes">
          <button className="primario">Criar COP</button>
          <button type="button" className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
        </div>
      </form>
    </Janela>
  );
}
