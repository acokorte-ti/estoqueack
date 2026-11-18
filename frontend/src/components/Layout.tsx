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

const PAINEL: Item[] = [{ para: "/", rotulo: "Painel de pendências", pronto: true }];

const GRUPOS: { titulo: string; itens: Item[] }[] = [
  {
    titulo: "Estoque",
    itens: [
      { para: "/estoque", rotulo: "Consultar estoque", pronto: true, perfis: ACESSO.estoque },
      { para: "/entradas-nf", rotulo: "Registrar entrada de material no RJ (NF)", pronto: true, perfis: ACESSO.entradaNf },
      { para: "/entradas-mega", rotulo: "Entradas do Mega sem lote", pronto: true, perfis: ACESSO.entradasMega },
      { para: "/conciliacao", rotulo: "Conferir estoque com o Mega", pronto: true, perfis: ACESSO.conciliacao },
    ],
  },
  {
    titulo: "Pedidos de corte",
    itens: [
      { para: "/solicitacoes/nova", rotulo: "Pedir corte de material", pronto: true, perfis: ACESSO.novaSolicitacao },
      { para: "/solicitacoes", rotulo: "Acompanhar pedidos de corte", pronto: true, perfis: ACESSO.solicitacoes },
    ],
  },
  {
    titulo: "Rio de Janeiro",
    itens: [
      { para: "/fila-rj", rotulo: "Cortes a fazer no RJ", pronto: true, perfis: ACESSO.filaRj },
      { para: "/cops", rotulo: "Montar envio para Itu (COP)", pronto: true, perfis: ACESSO.cop },
    ],
  },
  {
    titulo: "Itu",
    itens: [
      { para: "/recebimentos", rotulo: "Receber material do RJ", pronto: true, perfis: ACESSO.receberCop },
      // "Registrar corte em Itu" saiu do menu (2026-11-17): o corte começa em "Pedir corte de material"; /corte-itu abre pelos atalhos
      { para: "/sa", rotulo: "Cadastro de SA (semiacabado)", pronto: true, perfis: ACESSO.sa },
    ],
  },
  {
    titulo: "Ferramentas",
    itens: [
      { para: "/calculadora", rotulo: "Calculadora de peso", pronto: true },
      { para: "/relatorios", rotulo: "Relatórios" },
    ],
  },
];

const ADMIN: Item[] = [
  { para: "/admin/usuarios", rotulo: "Usuários", pronto: true },
  { para: "/admin/ligas", rotulo: "Ligas e densidades", pronto: true },
  { para: "/admin/parametros", rotulo: "Parâmetros do sistema", pronto: true },
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
  const { usuario, sair, modoTeste } = useSessao();
  const [menuAberto, setMenuAberto] = useState(false);
  // spec v3.16 §4 (Eduardo, 2026-11-18): no computador, o menu lateral pode ser escondido; o navegador lembra a escolha
  const [menuRecolhido, setMenuRecolhido] = useState(() => localStorage.getItem("menu-recolhido") === "1");
  const alternarMenu = () => setMenuRecolhido((v) => {
    localStorage.setItem("menu-recolhido", v ? "0" : "1");
    return !v;
  });
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
    <div className={menuRecolhido ? "moldura menu-recolhido" : "moldura"}>
      <header className="topo">
        <button
          type="button"
          className="recolher-menu"
          aria-controls="menu-principal"
          aria-expanded={!menuRecolhido}
          onClick={alternarMenu}
          title={menuRecolhido ? "Mostrar o menu lateral" : "Esconder o menu lateral e usar a tela toda"}
        >
          <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M2 4h16M2 10h16M2 16h16" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
          </svg>
          {menuRecolhido ? "Mostrar menu" : "Esconder menu"}
        </button>
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
          <Lista itens={PAINEL} />
          {GRUPOS.map((g) => {
            const visiveis = g.itens.filter((i) => !i.perfis || (usuario && i.perfis.includes(usuario.perfil)));
            if (visiveis.length === 0) return null;
            return (
              <div key={g.titulo}>
                <p className="grupo">{g.titulo}</p>
                <Lista itens={visiveis} />
              </div>
            );
          })}
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
        {modoTeste && (
          <p className="faixa-teste" role="note">Ambiente de teste (homologação): os dados podem ser apagados na próxima recarga.</p>
        )}
        <Outlet />
      </main>
    </div>
  );
}
