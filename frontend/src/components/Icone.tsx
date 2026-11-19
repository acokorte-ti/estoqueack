/** Ícones de traço do layout A "Bancada" (24×24, cor = currentColor). Sempre ao lado de um texto ou com aria-label no botão. */
const CAMINHOS = {
  inicio: <path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />,
  corte: <><circle cx="6" cy="6" r="3" /><circle cx="6" cy="18" r="3" /><path d="M8.2 8.2 20 20M8.2 15.8 20 4" /></>,
  lista: <path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01" />,
  fila: <><rect x="3" y="4" width="18" height="5" rx="1" /><rect x="3" y="11" width="18" height="5" rx="1" /><path d="M3 20h18" /></>,
  envio: <><path d="M2 6h12v10H2zM14 9h4l3 3v4h-7z" /><circle cx="6" cy="18" r="2" /><circle cx="17" cy="18" r="2" /></>,
  sa: <><path d="M3 12V4h8l10 10-8 8z" /><circle cx="7.5" cy="8.5" r="1.3" /></>,
  receber: <><path d="M3 13h5l1 3h6l1-3h5" /><path d="M5 5h14l2 8v6H3v-6z" /></>,
  estoque: <><path d="M3 7l9-4 9 4v10l-9 4-9-4z" /><path d="M3 7l9 4 9-4M12 11v10" /></>,
  nf: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4M9 12h6M9 16h6" /></>,
  mega: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></>,
  conferir: <><path d="M4 12l4 4L20 5" /><path d="M4 20h16" /></>,
  balanca: <path d="M12 4v16M6 20h12M5 8h14M5 8l-3 6a3 3 0 0 0 6 0zM19 8l-3 6a3 3 0 0 0 6 0z" />,
  relatorio: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />,
  pessoas: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14.5a6.5 6.5 0 0 1 3.5 5.5" /></>,
  camadas: <><path d="M12 3 2 8l10 5 10-5z" /><path d="M2 13l10 5 10-5" /></>,
  ajustes: <><path d="M4 7h10M18 7h2M4 17h4M12 17h8" /><circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" /></>,
  sino: <><path d="M6 16v-5a6 6 0 1 1 12 0v5l2 2H4z" /><path d="M10 21a2 2 0 0 0 4 0" /></>,
  mais: <path d="M12 5v14M5 12h14" />,
  cadeado: <><rect x="5" y="11" width="14" height="10" rx="1.5" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  ok: <path d="M5 12l5 5 9-10" />,
  relogio: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  alerta: <><path d="M12 3 2 20h20z" /><path d="M12 10v4M12 17v.01" /></>,
  seta: <path d="M9 6l6 6-6 6" />,
  baixar: <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />,
  atualizar: <><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4v7h-7" /></>,
  editar: <><path d="M4 20h4L19 9l-4-4L4 16z" /><path d="M13 7l4 4" /></>,
  codigo: <path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18" />,
  recolher: <><rect x="3" y="4" width="18" height="16" rx="1.5" /><path d="M9 4v16M15 10l-2 2 2 2" /></>,
  expandir: <><rect x="3" y="4" width="18" height="16" rx="1.5" /><path d="M9 4v16M13 10l2 2-2 2" /></>,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.01" /></>,
  x: <path d="M6 6l12 12M18 6 6 18" />,
  sair: <><path d="M14 4h5a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-5" /><path d="M10 16l-4-4 4-4M6 12h10" /></>,
} as const;

export type NomeIcone = keyof typeof CAMINHOS;

export default function Icone({ nome, className }: { nome: NomeIcone; className?: string }) {
  return (
    <svg className={className ? `ic ${className}` : "ic"} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {CAMINHOS[nome]}
    </svg>
  );
}
