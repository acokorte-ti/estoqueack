import type { Ocorrencia } from "../api/cliente";

const TITULO = { ERRO: "Bloqueia a operação", CIENCIA: "Exige “estou ciente”", ALERTA: "Atenção" } as const;

export default function Ocorrencias({ itens }: { itens: Ocorrencia[] }) {
  if (!itens.length) return <p className="validacao ok">Dentro da tolerância. Nenhuma confirmação necessária.</p>;
  return (
    <ul className="validacoes">
      {itens.map((o) => (
        <li key={o.codigo} className={`validacao ${o.nivel.toLowerCase()}`}>
          <strong>{TITULO[o.nivel]}</strong>
          <span>{o.mensagem}</span>
        </li>
      ))}
    </ul>
  );
}
