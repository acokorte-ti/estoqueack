import { useId } from "react";
import type { Ocorrencia } from "../api/cliente";

/** Justificativas digitadas, por código de ocorrência (exatamente como veio, inclusive o sufixo "#2"). */
export type Confirmacoes = Record<string, string>;

export const JUSTIFICATIVA_MIN = 10;

/** A gravação só libera sem ERRO e com toda CIENCIA justificada (≥ 10 caracteres). */
export function podeGravar(ocorrencias: Ocorrencia[], conf: Confirmacoes): boolean {
  return ocorrencias.every(
    (o) => o.nivel === "ALERTA" || (o.nivel === "CIENCIA" && (conf[o.codigo] ?? "").trim().length >= JUSTIFICATIVA_MIN),
  );
}

/** Só as confirmações das ocorrências atuais (descarta justificativas de validações que sumiram). */
export function confirmacoesValidas(ocorrencias: Ocorrencia[], conf: Confirmacoes): Confirmacoes {
  const r: Confirmacoes = {};
  for (const o of ocorrencias) if (o.nivel === "CIENCIA" && conf[o.codigo]) r[o.codigo] = conf[o.codigo].trim();
  return r;
}

const TITULO = { ERRO: "Bloqueia a operação", CIENCIA: "Exige “estou ciente”", ALERTA: "Atenção" } as const;

/**
 * Painel de validações com a mesma linguagem em todas as telas:
 * vermelho bloqueia, amarelo pede justificativa (o "estou ciente"), cinza só avisa.
 */
export default function PainelValidacao({
  ocorrencias,
  confirmacoes,
  aoMudar,
  semOcorrencias = "Tudo certo. Nenhuma confirmação necessária.",
}: {
  ocorrencias: Ocorrencia[];
  confirmacoes: Confirmacoes;
  aoMudar: (c: Confirmacoes) => void;
  semOcorrencias?: string;
}) {
  const base = useId();
  if (!ocorrencias.length) return <p className="validacao ok">{semOcorrencias}</p>;
  const ordem = { ERRO: 0, CIENCIA: 1, ALERTA: 2 } as const;
  const lista = [...ocorrencias].sort((a, b) => ordem[a.nivel] - ordem[b.nivel]);
  return (
    <ul className="validacoes" aria-label="Validações">
      {lista.map((o) => {
        const id = `${base}-${o.codigo}`;
        const texto = confirmacoes[o.codigo] ?? "";
        const falta = JUSTIFICATIVA_MIN - texto.trim().length;
        return (
          <li key={o.codigo} className={`validacao ${o.nivel.toLowerCase()}`}>
            <strong>{TITULO[o.nivel]}</strong>
            <span>{o.mensagem}</span>
            {o.nivel === "CIENCIA" && (
              <label className="justificativa" htmlFor={id}>
                Estou ciente. Justificativa
                <textarea
                  id={id}
                  rows={2}
                  value={texto}
                  onChange={(e) => aoMudar({ ...confirmacoes, [o.codigo]: e.target.value })}
                  placeholder="Explique o motivo (mínimo de 10 caracteres)"
                />
                <small className="dica" aria-live="polite">
                  {falta > 0 ? `Faltam ${falta} caractere(s).` : "Justificativa aceita."}
                </small>
              </label>
            )}
          </li>
        );
      })}
    </ul>
  );
}
