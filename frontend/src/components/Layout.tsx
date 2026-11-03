import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useSessao } from "../api/sessao";
import { NOME_PERFIL, type Perfil } from "../api/cliente";
import { ACESSO } from "../api/acesso";
import Sino from "./Sino";

interface Item {
  para: string;
  rotulo: string;
  pronto?: boolean;
  perfis?: Perfil[];
}

const OPERACAO: Item[] = [
  { para: "/", rotulo: "Painel", pronto: true },
  { para: "/estoque", rotulo: "Estoque por lote" },
  { para: "/solicitacoes/nova", rotulo: "Nova solicitação de corte", pronto: true, perfis: ACESSO.novaSolicitacao },
  { para: "/solicitacoes", rotulo: "Solicitações de corte", pronto: true, perfis: ACESSO.solicitacoes },
  { para: "/fila-rj", rotulo: "Fila RJ", pronto: true, perfis: ACESSO.filaRj },
  { para: "/cops", rotulo: "COP", pronto: true, perfis: ACESSO.cop },
  { para: "/recebimentos", rotulo: "Receber COP", pronto: true, perfis: ACESSO.receberCop },
  { para: "/corte-itu", rotulo: "Corte em Itu", pronto: true, perfis: ACESSO.corteItu },
  { para: "/sa", rotulo: "SA", pronto: true, perfis: ACESSO.sa },
  { para: "/relatorios", rotulo: "Relatórios" },
  { para: "/calculadora", rotulo: "Calculadora de peso", pronto: true },
];

const ADMIN: Item[] = [
  { para: "/admin/usuarios", rotulo: "Usuários", pronto: true },
  { para: "/admin/ligas", rotulo: "Ligas e densidades", pronto: true },
];

function Lista({ itens }: { itens: Item[] }) {
  return (
    <ul>
      {itens.map((i) => (
        <li key={i.para}>
          <NavLink
            to={i.para}
            end={i.para === "/" || i.para === "/solicitacoes"}
            className={({ isActive }) => [isActive ? "ativo" : "", i.pronto ? "" : "em-breve"].join(" ").trim()}
          >
            <span>{i.rotulo}</span>
            {!i.pronto && <small className="breve">em breve</small>}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

export default function Layout() {
  const { usuario, sair } = useSessao();
  const [menuAberto, setMenuAberto] = useState(false);
  const local = useLocation();
  const planta = usuario?.planta === "RJ" ? "Barra Mansa" : "Itu";

  // fecha o menu do celular ao trocar de tela e com a tecla Esc
  useEffect(() => setMenuAberto(false), [local.pathname]);
  const botaoFechar = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!menuAberto) return;
    botaoFechar.current?.focus();
    const fechar = (e: KeyboardEvent) => e.key === "Escape" && setMenuAberto(false);
    window.addEventListener("keydown", fechar);
    return () => window.removeEventListener("keydown", fechar);
  }, [menuAberto]);

  return (
    <div className="moldura">
      <header className="topo">
        <button
          className="abrir-menu"
          aria-expanded={menuAberto}
          aria-controls="menu-principal"
          onClick={() => setMenuAberto(true)}
        >
          <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M2 4h16M2 10h16M2 16h16" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
          </svg>
          Menu
        </button>
        <Link to="/" className="topo-marca" aria-label="EstoqueACK, ir para o painel">
          <img src="/logo-acokorte.png" alt="AçoKorte" width={167} height={34} />
          <span className="topo-sistema">EstoqueACK</span>
        </Link>
        <span className="topo-espaco" />
        <Sino />
        <div className="topo-usuario">
          <strong>{usuario?.nome}</strong>
          <span>
            {usuario && NOME_PERFIL[usuario.perfil]} em {planta}
          </span>
        </div>
        <button className="secundario topo-sair" onClick={() => void sair()}>
          Sair
        </button>
      </header>

      <aside id="menu-principal" className={menuAberto ? "lateral aberta" : "lateral"} aria-label="Menu">
        <div className="lateral-topo">
          <strong>Menu</strong>
          <button ref={botaoFechar} onClick={() => setMenuAberto(false)} aria-label="Fechar menu">
            ✕
          </button>
        </div>
        <nav aria-label="Navegação principal">
          <Lista itens={OPERACAO.filter((i) => !i.perfis || (usuario && i.perfis.includes(usuario.perfil)))} />
          {usuario?.perfil === "ADMIN" && (
            <>
              <p className="grupo">Administração</p>
              <Lista itens={ADMIN} />
            </>
          )}
        </nav>
        <div className="lateral-sair">
          <strong>{usuario?.nome}</strong>
          {usuario && NOME_PERFIL[usuario.perfil]} em {planta}
          <button className="secundario" onClick={() => void sair()}>
            Sair
          </button>
        </div>
      </aside>
      {menuAberto && <div className="fundo-menu" onClick={() => setMenuAberto(false)} aria-hidden="true" />}

      <main className="conteudo">
        <Outlet />
      </main>
    </div>
  );
}
