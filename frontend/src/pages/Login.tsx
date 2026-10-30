import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useSessao } from "../api/sessao";
import CampoSenha from "../components/CampoSenha";

export default function Login() {
  const { usuario, entrar } = useSessao();
  const nav = useNavigate();
  const local = useLocation();
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [lembrar, setLembrar] = useState(false);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  if (usuario) return <Navigate to="/" replace />;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      const u = await entrar(login.trim().toLowerCase(), senha, lembrar);
      const destino = (local.state as { de?: string } | null)?.de ?? "/";
      nav(u.trocar_senha ? "/trocar-senha" : destino, { replace: true });
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível entrar.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="entrada">
      <form className="entrada-form" onSubmit={enviar}>
        <img className="entrada-logo" src="/logo-acokorte.png" alt="AçoKorte" width={216} height={44} />
        <h1>EstoqueACK</h1>
        <p className="entrada-sub">Controle de matéria-prima de Itu e Barra Mansa</p>
        <label>
          Login
          <input
            autoFocus
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="nome.sobrenome"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            required
          />
        </label>
        <CampoSenha rotulo="Senha" autoComplete="current-password" valor={senha} aoMudar={setSenha} />
        <label className="marcar">
          <input type="checkbox" checked={lembrar} onChange={(e) => setLembrar(e.target.checked)} />
          <span>
            Manter conectado
            <small className="dica">Fica 30 dias neste aparelho. Não use em computador compartilhado.</small>
          </span>
        </label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <button className="primario" disabled={enviando}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
        <Link className="link entrada-link" to="/esqueci-senha" state={{ login }}>
          Esqueci minha senha
        </Link>
      </form>
    </div>
  );
}
