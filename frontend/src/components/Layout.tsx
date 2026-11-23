import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useSessao } from "../api/sessao";
import { NOME_PERFIL, type Perfil } from "../api/cliente";
import { ACESSO } from "../api/acesso";
import { contadoresDoMenu, lerSeVelho, limparPendencias, recarregarPendencias, usePendencias, type Contador } from "../api/pendencias";
import Sino from "./Sino";
import AvisoVersao from "./AvisoVersao";
import Icone, { type NomeIcone } from "./Icone";

interface Item {
  para: string;
  rotulo: string;
  icone: NomeIcone;
  pronto?: boolean;
  perfis?: Perfil[];
}
interface Grupo { titulo: string; itens: Item[]; admin?: boolean }

/* Layout A "Bancada" (Eduardo, 2026-11-19): o menu segue o caminho do material,
   Hoje → Corte → Envio RJ → Itu → Estoque → Ferramentas (antes: "Rio de Janeiro" e "Itu" misturados com "Estoque"). */
const GRUPOS: Grupo[] = [
  { titulo: "Hoje", itens: [{ para: "/", rotulo: "Para fazer agora", icone: "inicio", pronto: true }] },
  {
    titulo: "Corte",
    itens: [
      { para: "/solicitacoes/nova", rotulo: "Pedir corte", icone: "corte", pronto: true, perfis: ACESSO.novaSolicitacao },
      { para: "/solicitacoes", rotulo: "Acompanhar pedidos", icone: "lista", pronto: true, perfis: ACESSO.solicitacoes },
      { para: "/fila-rj", rotulo: "Cortes a fazer no RJ", icone: "fila", pronto: true, perfis: ACESSO.filaRj },
      // "Registrar corte em Itu" saiu do menu (2026-11-17): o corte começa em "Pedir corte"; /corte-itu abre pelos atalhos
    ],
  },
  {
    titulo: "Envio RJ → Itu",
    itens: [
      { para: "/cops", rotulo: "Montar envio (COP)", icone: "envio", pronto: true, perfis: ACESSO.cop },
      { para: "/sa", rotulo: "Cadastro de SA", icone: "sa", pronto: true, perfis: ACESSO.sa },
      { para: "/recebimentos", rotulo: "Receber em Itu", icone: "receber", pronto: true, perfis: ACESSO.receberCop },
    ],
  },
  {
    titulo: "Estoque",
    itens: [
      { para: "/estoque", rotulo: "Consultar estoque", icone: "estoque", pronto: true, perfis: ACESSO.estoque },
      { para: "/entradas-nf", rotulo: "Entrada por NF (RJ)", icone: "nf", pronto: true, perfis: ACESSO.entradaNf },
      { para: "/entradas-mega", rotulo: "Entradas do Mega sem lote", icone: "mega", pronto: true, perfis: ACESSO.entradasMega },
      { para: "/conciliacao", rotulo: "Conferir com o Mega", icone: "conferir", pronto: true, perfis: ACESSO.conciliacao },
    ],
  },
  {
    titulo: "Ferramentas",
    itens: [
      { para: "/calculadora", rotulo: "Calculadora de peso", icone: "balanca", pronto: true },
      { para: "/relatorios", rotulo: "Relatórios", icone: "relatorio" },
    ],
  },
  {
    titulo: "Administração",
    admin: true,
    itens: [
      { para: "/admin/usuarios", rotulo: "Usuários", icone: "pessoas", pronto: true },
      { para: "/admin/ligas", rotulo: "Ligas e densidades", icone: "camadas", pronto: true },
      { para: "/admin/parametros", rotulo: "Parâmetros do sistema", icone: "ajustes", pronto: true },
    ],
  },
];

/** Item do menu da tela aberta: o de caminho mais longo que é começo do endereço (/cops/12 → Montar envio). */
function itemAtual(grupos: Grupo[], caminho: string): { grupo: Grupo; item: Item } | null {
  let achado: { grupo: Grupo; item: Item } | null = null;
  for (const grupo of grupos) {
    for (const item of grupo.itens) {
      const casa = item.para === "/" ? caminho === "/" : caminho === item.para || caminho.startsWith(`${item.para}/`);
      if (casa && (!achado || item.para.length > achado.item.para.length)) achado = { grupo, item };
    }
  }
  return achado;
}

const iniciais = (nome = "") => {
  const p = nome.trim().split(/\s+/).filter(Boolean);
  return ((p[0]?.[0] ?? "") + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase();
};

function ItemMenu({ i, ativo, contador }: { i: Item; ativo: boolean; contador?: Contador }) {
  const qtd = contador?.qtd ?? 0;
  return (
    <li>
      <Link
        to={i.para}
        className={["item-menu", i.pronto ? "" : "em-breve"].join(" ").trim()}
        aria-current={ativo ? "page" : undefined}
        title={i.rotulo}
      >
        <Icone nome={i.icone} />
        <span className="rotulo">{i.rotulo}</span>
        {!i.pronto && <small className="breve">em breve</small>}
        {qtd > 0 && (
          <span className={contador?.urgente ? "qtd urgente" : "qtd"} aria-label={`${qtd} pendente(s)`}>{qtd > 99 ? "99+" : qtd}</span>
        )}
      </Link>
    </li>
  );
}

export default function Layout() {
  const { usuario, sair, modoTeste } = useSessao();
  const [menuAberto, setMenuAberto] = useState(false);
  // spec v3.16 §4 (Eduardo, 2026-11-18): no computador, o menu lateral pode ser escondido (fica só a coluna de ícones);
  // o navegador lembra a escolha
  const [menuRecolhido, setMenuRecolhido] = useState(() => localStorage.getItem("menu-recolhido") === "1");
  const alternarMenu = () => setMenuRecolhido((v) => {
    localStorage.setItem("menu-recolhido", v ? "0" : "1");
    return !v;
  });
  const local = useLocation();
  const planta = usuario?.planta === "RJ" ? "Barra Mansa" : "Itu";

  // contadores do menu: a mesma leitura do Painel, renovada a cada 2 min e ao trocar de tela (se tiver mais de 1 min)
  const { dados } = usePendencias();
  const contadores = contadoresDoMenu(dados);
  useEffect(() => {
    void recarregarPendencias();
    const t = window.setInterval(() => void recarregarPendencias(), 120_000);
    return () => { window.clearInterval(t); limparPendencias(); };
  }, []);
  useEffect(() => lerSeVelho(60_000), [local.pathname]);

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

  const grupos = GRUPOS
    .filter((g) => !g.admin || usuario?.perfil === "ADMIN")
    .map((g) => ({ ...g, itens: g.itens.filter((i) => !i.perfis || (usuario && i.perfis.includes(usuario.perfil))) }))
    .filter((g) => g.itens.length > 0);
  const atual = itemAtual(grupos, local.pathname);
  const podePedirCorte = !!usuario && (ACESSO.novaSolicitacao as Perfil[]).includes(usuario.perfil) && local.pathname !== "/solicitacoes/nova";

  return (
    <div className={menuRecolhido ? "moldura menu-recolhido" : "moldura"}>
      <header className="topo">
        <button
          type="button"
          className="icone-botao abrir-menu"
          aria-expanded={menuAberto}
          aria-controls="menu-principal"
          aria-label="Abrir menu"
          onClick={() => setMenuAberto(true)}
        >
          <Icone nome="menu" />
        </button>
        <Link to="/" className="topo-marca" aria-label="EstoqueACK, ir para Para fazer agora">
          <img src="/logo-acokorte.png" alt="AçoKorte" width={138} height={28} />
          <span className="topo-sistema">EstoqueACK</span>
        </Link>
        <span className="topo-espaco" />
        {podePedirCorte && (
          <Link to="/solicitacoes/nova" className="secundario pequeno topo-pedir"><Icone nome="mais" />Pedir corte</Link>
        )}
        <Sino />
        <div className="topo-usuario">
          <span className="avatar" aria-hidden="true">{iniciais(usuario?.nome)}</span>
          <span className="topo-usuario-texto">
            <strong>{usuario?.nome}</strong>
            <small>{usuario && NOME_PERFIL[usuario.perfil]} · {planta}</small>
          </span>
        </div>
        <button type="button" className="fantasma pequeno topo-sair" onClick={() => void sair()}>
          <Icone nome="sair" />Sair
        </button>
      </header>

      <aside id="menu-principal" className={menuAberto ? "lateral aberta" : "lateral"} aria-label="Menu">
        <div className="lateral-topo">
          <strong>Menu</strong>
          <button ref={botaoFechar} type="button" className="icone-botao" onClick={() => setMenuAberto(false)} aria-label="Fechar menu">
            <Icone nome="x" />
          </button>
        </div>
        <nav aria-label="Navegação principal">
          {grupos.map((g) => (
            <div key={g.titulo} className="grupo-menu">
              <p className="grupo">{g.titulo}</p>
              <ul>
                {g.itens.map((i) => (
                  <ItemMenu key={i.para} i={i} ativo={atual?.item.para === i.para} contador={contadores[i.para]} />
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="lateral-rodape">
          <button
            type="button"
            className="item-menu recolher-menu"
            aria-controls="menu-principal"
            aria-expanded={!menuRecolhido}
            onClick={alternarMenu}
            title={menuRecolhido ? "Mostrar o menu lateral" : "Esconder o menu e usar a tela toda"}
          >
            <Icone nome={menuRecolhido ? "expandir" : "recolher"} />
            <span className="rotulo">{menuRecolhido ? "Mostrar menu" : "Esconder menu"}</span>
          </button>
        </div>
        <div className="lateral-sair">
          <strong>{usuario?.nome}</strong>
          {usuario && NOME_PERFIL[usuario.perfil]} · {planta}
          <button type="button" className="secundario" onClick={() => void sair()}>
            <Icone nome="sair" />Sair
          </button>
        </div>
      </aside>
      {menuAberto && <div className="fundo-menu" onClick={() => setMenuAberto(false)} aria-hidden="true" />}

      <main className="conteudo">
        <AvisoVersao />
        {modoTeste && (
          <p className="faixa-teste" role="note">Ambiente de teste (homologação): os dados podem ser apagados na próxima recarga.</p>
        )}
        {atual && atual.item.para !== "/" && (
          <nav className="trilha" aria-label="Você está em">
            <span>{atual.grupo.titulo}</span>
            <Icone nome="seta" />
            {local.pathname === atual.item.para
              ? <span aria-current="page">{atual.item.rotulo}</span>
              : <Link to={atual.item.para}>{atual.item.rotulo}</Link>}
          </nav>
        )}
        <Outlet />
      </main>
    </div>
  );
}
