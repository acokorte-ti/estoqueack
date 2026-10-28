import { NavLink, Outlet } from "react-router-dom";
import { useSessao } from "../api/sessao";
import { NOME_PERFIL } from "../api/cliente";

interface Item {
  para: string;
  rotulo: string;
  pronto?: boolean;
}

const OPERACAO: Item[] = [
  { para: "/", rotulo: "Painel", pronto: true },
  { para: "/estoque", rotulo: "Estoque por lote" },
  { para: "/corte", rotulo: "Solicitações de corte" },
  { para: "/cop", rotulo: "COP" },
  { para: "/sa", rotulo: "Cadastro de SA" },
  { para: "/consumo", rotulo: "Consumo, sobra e RETO" },
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
          <NavLink to={i.para} end={i.para === "/"} className={({ isActive }) => (isActive ? "ativo" : "")}>
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
  return (
    <div className="moldura">
      <aside className="lateral">
        <div className="marca">
          <span className="marca-nome">EstoqueACK</span>
          <span className="marca-sub">Matéria-prima AçoKorte</span>
        </div>
        <nav aria-label="Navegação principal">
          <Lista itens={OPERACAO} />
          {usuario?.perfil === "ADMIN" && (
            <>
              <p className="grupo">Administração</p>
              <Lista itens={ADMIN} />
            </>
          )}
        </nav>
        <div className="quem">
          <strong>{usuario?.nome}</strong>
          <span>
            {usuario && NOME_PERFIL[usuario.perfil]} em {usuario?.planta === "RJ" ? "Barra Mansa" : "Itu"}
          </span>
          <button className="link" onClick={() => void sair()}>
            Sair
          </button>
        </div>
      </aside>
      <main className="conteudo">
        <Outlet />
      </main>
    </div>
  );
}
