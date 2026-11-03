import { ATRASO, SITUACAO_SOLIC, type SituacaoSolic } from "../api/solicitacao";

export function EtiquetaSituacao({ s }: { s: SituacaoSolic }) {
  const x = SITUACAO_SOLIC[s] ?? { nome: s, classe: "" };
  return <span className={`etiqueta ${x.classe}`}>{x.nome}</span>;
}

/** Normal (até 7 dias), Atenção (até 15), Atrasado: mesma regra da planilha (T03). Cor + texto, nunca só cor. */
export function EtiquetaAtraso({ a, dias }: { a: string | null; dias?: number | null }) {
  if (!a) return null;
  const x = ATRASO[a] ?? { nome: a, classe: "" };
  return (
    <span className={`etiqueta ${x.classe}`}>
      {x.nome}
      {dias !== null && dias !== undefined && ` · ${dias} d`}
    </span>
  );
}
