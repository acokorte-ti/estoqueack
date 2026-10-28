import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useSessao } from "./api/sessao";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import TrocarSenha from "./pages/TrocarSenha";
import Painel from "./pages/Painel";
import Calculadora from "./pages/Calculadora";
import Usuarios from "./pages/Usuarios";
import Ligas from "./pages/Ligas";
import EmBreve from "./pages/EmBreve";

function Protegido({ children, admin = false }: { children: JSX.Element; admin?: boolean }) {
  const { usuario, carregando } = useSessao();
  const local = useLocation();
  if (carregando) return <div className="carregando">Carregando…</div>;
  if (!usuario) return <Navigate to="/entrar" state={{ de: local.pathname }} replace />;
  if (usuario.trocar_senha && local.pathname !== "/trocar-senha") return <Navigate to="/trocar-senha" replace />;
  if (admin && usuario.perfil !== "ADMIN") return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/entrar" element={<Login />} />
      <Route path="/trocar-senha" element={<Protegido><TrocarSenha /></Protegido>} />
      <Route element={<Protegido><Layout /></Protegido>}>
        <Route index element={<Painel />} />
        <Route path="calculadora" element={<Calculadora />} />
        <Route path="estoque" element={<EmBreve titulo="Consulta de estoque" fase="Fase 1" />} />
        <Route path="corte" element={<EmBreve titulo="Solicitações de corte" fase="Fase 1" />} />
        <Route path="cop" element={<EmBreve titulo="COP" fase="Fase 1" />} />
        <Route path="sa" element={<EmBreve titulo="Cadastro de SA" fase="Fase 1" />} />
        <Route path="consumo" element={<EmBreve titulo="Consumo, sobra e RETO" fase="Fase 2" />} />
        <Route path="relatorios" element={<EmBreve titulo="Relatórios" fase="Fase 4" />} />
        <Route path="admin/usuarios" element={<Protegido admin><Usuarios /></Protegido>} />
        <Route path="admin/ligas" element={<Protegido admin><Ligas /></Protegido>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
