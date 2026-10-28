import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, kg } from "../api/cliente";
import { useSessao } from "../api/sessao";

interface Resumo {
  baldes: Record<"ESTOQUE_MEGA" | "RJ_NO_RIO" | "RJ_EM_ITU", { lotes: number; kg: number }>;
  total_kg: number;
}

const BALDES = [
  { chave: "ESTOQUE_MEGA", nome: "Estoque Mega", desc: "fiscal Itu, físico Itu" },
  { chave: "RJ_NO_RIO", nome: "RJ no Rio", desc: "fiscal RJ, físico Barra Mansa" },
  { chave: "RJ_EM_ITU", nome: "RJ em Itu", desc: "fiscal RJ, físico Itu" },
] as const;

export default function Painel() {
  const { usuario } = useSessao();
  const [resumo, setResumo] = useState<Resumo | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.get<Resumo>("/painel/resumo").then(setResumo).catch((e: Error) => setErro(e.message));
  }, []);

  const total = resumo?.total_kg ?? 0;

  return (
    <>
      <header className="cabecalho">
        <h1>Olá, {usuario?.nome.split(" ")[0]}</h1>
        <p>Saldo de matéria-prima por local de estoque.</p>
      </header>

      {erro && <p className="erro">{erro}</p>}

      <section className="barra-estoque" aria-label="Distribuição do estoque">
        <div className="barra-total">
          <span className="numero">{kg(total)}</span>
          <span className="unidade">kg no total</span>
        </div>
        <div className="barra" role="img" aria-label="Proporção de cada estoque">
          {BALDES.map((b) => {
            const v = resumo?.baldes[b.chave].kg ?? 0;
            const pct = total > 0 ? (v / total) * 100 : 0;
            return <span key={b.chave} className={`seg seg-${b.chave.toLowerCase()}`} style={{ flexBasis: `${pct}%` }} />;
          })}
          {total === 0 && <span className="seg seg-vazio" />}
        </div>
        <dl className="legenda">
          {BALDES.map((b) => {
            const d = resumo?.baldes[b.chave];
            return (
              <div key={b.chave} className={`leg leg-${b.chave.toLowerCase()}`}>
                <dt>{b.nome}</dt>
                <dd className="numero">{kg(d?.kg ?? 0)} kg</dd>
                <dd className="desc">
                  {d?.lotes ?? 0} lotes, {b.desc}
                </dd>
              </div>
            );
          })}
        </dl>
      </section>

      {total === 0 && resumo && (
        <section className="aviso-vazio">
          <h2>Nenhum lote cadastrado ainda</h2>
          <p>
            Os saldos aparecem aqui depois da importação das planilhas (ESTOQUE 2026, Estoque Geral e histórico de SA),
            prevista para a Fase 1. Enquanto isso, a <Link to="/calculadora">calculadora de peso</Link> já usa as
            densidades por liga e a regra dos 20 %.
          </p>
        </section>
      )}
    </>
  );
}
