import { useId, useState } from "react";

/** Campo de senha com botão "Mostrar": no tablet, evita errar a senha sem perceber. */
export default function CampoSenha({
  rotulo,
  valor,
  aoMudar,
  autoComplete,
  autoFocus,
  obrigatorio = true,
  ajuda,
}: {
  rotulo: string;
  valor: string;
  aoMudar: (v: string) => void;
  autoComplete: "current-password" | "new-password";
  autoFocus?: boolean;
  obrigatorio?: boolean;
  ajuda?: string;
}) {
  const [visivel, setVisivel] = useState(false);
  const id = useId();
  return (
    <div className="campo-senha">
      <label htmlFor={id}>{rotulo}</label>
      <div className="campo-senha-linha">
        <input
          id={id}
          type={visivel ? "text" : "password"}
          autoComplete={autoComplete}
          autoCapitalize="none"
          spellCheck={false}
          autoFocus={autoFocus}
          value={valor}
          onChange={(e) => aoMudar(e.target.value)}
          required={obrigatorio}
          aria-describedby={ajuda ? `${id}-ajuda` : undefined}
        />
        <button
          type="button"
          className="secundario"
          aria-pressed={visivel}
          aria-label={visivel ? `Ocultar ${rotulo.toLowerCase()}` : `Mostrar ${rotulo.toLowerCase()}`}
          onClick={() => setVisivel(!visivel)}
        >
          {visivel ? "Ocultar" : "Mostrar"}
        </button>
      </div>
      {ajuda && <small id={`${id}-ajuda`} className="dica">{ajuda}</small>}
    </div>
  );
}
