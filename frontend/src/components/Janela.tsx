import { useEffect, useRef, type ReactNode } from "react";

/** Janela modal (dialog nativo: prende o foco, fecha com Esc). Abre ao montar; `aoFechar` ao fechar. */
export default function Janela({ titulo, aoFechar, children, larga = false }: { titulo: string; aoFechar: () => void; children: ReactNode; larga?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);
  const id = `janela-${titulo.replace(/\W+/g, "-").toLowerCase()}`;
  return (
    <dialog ref={ref} className={larga ? "janela larga" : "janela"} aria-labelledby={id} onClose={aoFechar}>
      <div className="painel-form">
        <h2 id={id}>{titulo}</h2>
        {children}
      </div>
    </dialog>
  );
}

/** Fecha a janela que contém o elemento (o `onClose` do dialog chama `aoFechar`). */
export const fecharJanela = (el: HTMLElement | null) => el?.closest("dialog")?.close();
