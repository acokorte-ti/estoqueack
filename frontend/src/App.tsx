import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";
import { useSessao } from "./api/sessao";
import type { Perfil } from "./api/cliente";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import TrocarSenha from "./pages/TrocarSenha";
import Painel from "./pages/Painel";
import Calculadora from "./pages/Calculadora";
import Usuarios from "./pages/Usuarios";
import Ligas from "./pages/Ligas";
import EmBreve from "./pages/EmBreve";
import EsqueciSenha from "./pages/EsqueciSenha";
import RedefinirSenha from "./pages/RedefinirSenha";
import NovaSolicitacao from "./pages/NovaSolicitacao";
import Sas from "./pages/Sas";
import Solicitacoes from "./pages/Solicitacoes";
import SolicitacaoDetalhe from "./pages/SolicitacaoDetalhe";
import FilaRj from "./pages/FilaRj";
import RegistrarCorte from "./pages/RegistrarCorte";
import Cops from "./pages/Cops";
import CopDetalhe from "./pages/CopDetalhe";
import { Recebimentos, ReceberCop } from "./pages/Recebimentos";
import CorteItu from "./pages/CorteItu";
import Estoque from "./pages/Estoque";
import LoteDetalhe from "./pages/LoteDetalhe";
import EntradasNf from "./pages/EntradasNf";
import Parametros from "./pages/Parametros";

/** Links antigos/notificações no formato /lotes/:id abrem o detalhe do lote. */
function RedirecionaLote() {
  const { id } = useParams();
  return <Navigate to={`/estoque/${id}`} replace />;
}

import { ACESSO } from "./api/acesso";

function Protegido({ children, admin = false, perfis }: { children: JSX.Element; admin?: boolean; perfis?: Perfil[] }) {
  const { usuario, carregando } = useSessao();
  const local = useLocation();
  if (carregando) return <div className="carregando">Carregando…</div>;
  if (!usuario) return <Navigate to="/entrar" state={{ de: local.pathname + local.search }} replace />;
  if (usuario.trocar_senha && local.pathname !== "/trocar-senha") return <Navigate to="/trocar-senha" replace />;
  if (admin && usuario.perfil !== "ADMIN") return <Navigate to="/" replace />;
  if (perfis && !perfis.includes(usuario.perfil)) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/entrar" element={<Login />} />
      <Route path="/esqueci-senha" element={<EsqueciSenha />} />
      <Route path="/redefinir-senha" element={<RedefinirSenha />} />
      <Route path="/trocar-senha" element={<Protegido><TrocarSenha /></Protegido>} />
      <Route element={<Protegido><Layout /></Protegido>}>
        <Route index element={<Painel />} />
        <Route path="calculadora" element={<Calculadora />} />
        <Route path="estoque" element={<Protegido perfis={ACESSO.estoque}><Estoque /></Protegido>} />
        <Route path="estoque/:id" element={<Protegido perfis={ACESSO.estoque}><LoteDetalhe /></Protegido>} />
        <Route path="lotes/:id" element={<RedirecionaLote />} />
        <Route path="entradas-nf" element={<Protegido perfis={ACESSO.entradaNf}><EntradasNf /></Protegido>} />
        <Route path="admin/parametros" element={<Protegido admin><Parametros /></Protegido>} />
        <Route path="solicitacoes" element={<Protegido perfis={ACESSO.solicitacoes}><Solicitacoes /></Protegido>} />
        <Route path="solicitacoes/nova" element={<Protegido perfis={ACESSO.novaSolicitacao}><NovaSolicitacao /></Protegido>} />
        <Route path="solicitacoes/:id" element={<Protegido perfis={ACESSO.solicitacoes}><SolicitacaoDetalhe /></Protegido>} />
        <Route path="fila-rj" element={<Protegido perfis={ACESSO.filaRj}><FilaRj /></Protegido>} />
        <Route path="fila-rj/:id/corte" element={<Protegido perfis={ACESSO.registrarCorte}><RegistrarCorte /></Protegido>} />
        <Route path="corte" element={<Navigate to="/solicitacoes" replace />} />
        <Route path="corte-itu" element={<Protegido perfis={ACESSO.corteItu}><CorteItu /></Protegido>} />
        <Route path="cops" element={<Protegido perfis={ACESSO.cop}><Cops /></Protegido>} />
        <Route path="cops/:id" element={<Protegido perfis={ACESSO.cop}><CopDetalhe /></Protegido>} />
        <Route path="cop" element={<Navigate to="/cops" replace />} />
        <Route path="recebimentos" element={<Protegido perfis={ACESSO.receberCop}><Recebimentos /></Protegido>} />
        <Route path="recebimentos/:id" element={<Protegido perfis={ACESSO.receberCop}><ReceberCop /></Protegido>} />
        <Route path="sa" element={<Protegido perfis={ACESSO.sa}><Sas /></Protegido>} />
        <Route path="consumo" element={<EmBreve titulo="Consumo, sobra e RETO" fase="Fase 2" />} />
        <Route path="relatorios" element={<EmBreve titulo="Relatórios" fase="Fase 4" />} />
        <Route path="admin/usuarios" element={<Protegido admin><Usuarios /></Protegido>} />
        <Route path="admin/ligas" element={<Protegido admin><Ligas /></Protegido>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
