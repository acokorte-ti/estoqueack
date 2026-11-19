import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, kg, type Perfil } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { usePendencias } from "../api/pendencias";
import { ACESSO } from "../api/acesso";
import SyncMega from "../components/SyncMega";
import Pendencias, { totalPendencias } from "../components/Pendencias";
import Icone from "../components/Icone";

interface Resumo {
  baldes: Partial<Record<"ESTOQUE_MEGA" | "RJ_NO_RIO" | "RJ_EM_ITU", { lotes: number; kg: number }>>; // Operação RJ só recebe RJ_NO_RIO (P10)
  total_kg: number;
}

const TODOS_BALDES = [
  { chave: "ESTOQUE_MEGA", nome: "Estoque Mega", desc: "fiscal Itu, físico Itu" },
  { chave: "RJ_NO_RIO", nome: "RJ no Rio", desc: "fiscal RJ, físico Barra Mansa" },
  { chave: "RJ_EM_ITU", nome: "RJ em Itu", desc: "fiscal RJ, físico Itu" },
] as const;

const hoje = () => {
  const t = new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  return t.charAt(0).toUpperCase() + t.slice(1);
};

/** T03 no layout A: "Para fazer agora" (pendências) à esquerda, saldo por estoque à direita. */
export default function Painel() {
  const { usuario } = useSessao();
  const { dados } = usePendencias();
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.get<Resumo>("/painel/resumo").then(setResumo).catch((e: Error) => setErro(e.message));
  }, []);

  const total = resumo?.total_kg ?? 0;
  // só os baldes que a API mandou (Operação RJ não vê Mega nem RJ em Itu)
  const BALDES = resumo ? TODOS_BALDES.filter((b) => resumo.baldes[b.chave]) : TODOS_BALDES;
  const qtd = dados ? totalPendencias(dados.grupos) : null;
  const veEstoque = !!usuario && (ACESSO.estoque as Perfil[]).includes(usuario.perfil);

  return (
    <>
      <header className="cabecalho cabecalho-acao">
        <div>
          <h1>Para fazer agora</h1>
          <p>
            Olá, {usuario?.nome.split(" ")[0]} · {hoje()}
            {qtd !== null && (qtd ? ` · ${qtd} pendência(s), da mais urgente para a menos urgente.` : " · nada pendente.")}
          </p>
        </div>
        <div className="acoes-cabecalho"><SyncMega /></div>
      </header>

      <div className="grade-painel">
        <div className="coluna">
          <Pendencias />
        </div>

        <div className="coluna">
          <section className="quadro" aria-label="Saldo por estoque">
            <header>
              <h2>Saldo por estoque</h2>
              {veEstoque && <Link className="fantasma pequeno" to="/estoque">Consultar<Icone nome="seta" /></Link>}
            </header>
            {erro && <p className="erro" role="alert" style={{ margin: "var(--esp-3) 1.125rem" }}>{erro}</p>}
            <div className="saldo-total">
              <span className="numero">{kg(total)}</span>
              <span className="desc">kg no total</span>
            </div>
            <ul className="saldo-lista">
              {BALDES.map((b) => {
                const d = resumo?.baldes[b.chave];
                const v = d?.kg ?? 0;
                const pct = total > 0 ? (v / total) * 100 : 0;
                const cor = `cor-${b.chave.toLowerCase()}`;
                return (
                  <li key={b.chave} className="saldo">
                    <div className="saldo-topo">
                      <span className="saldo-nome"><i className={cor} aria-hidden="true" />{b.nome}</span>
                      <span className="saldo-kg">{kg(v)}</span>
                    </div>
                    <small>kg · {d?.lotes ?? 0} lotes · {b.desc}</small>
                    <div className="saldo-barra" role="img" aria-label={`${b.nome}: ${Math.round(pct)} % do total`}>
                      <i className={cor} style={{ width: `${pct}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>

          {total === 0 && resumo && (
            <section className="aviso-vazio">
              <h2>Nenhum lote cadastrado ainda</h2>
              <p>
                Os saldos aparecem aqui depois da importação das planilhas (ESTOQUE 2026, Estoque Geral e histórico de SA).
                Enquanto isso, a <Link to="/calculadora">calculadora de peso</Link> já usa as densidades por liga e a regra de tolerância de 5 %.
              </p>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
