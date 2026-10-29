import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useSessao } from "../api/sessao";

export default function Login() {
  const { usuario, entrar } = useSessao();
  const nav = useNavigate();
  const local = useLocation();
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  if (usuario) return <Navigate to="/" replace />;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      const u = await entrar(login, senha);
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
          <input autoFocus autoComplete="username" value={login} onChange={(e) => setLogin(e.target.value)} required />
        </label>
        <label>
          Senha
          <input
            type="password"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
          />
        </label>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <button className="primario" disabled={enviando}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
        <p className="dica">Esqueceu a senha? Peça ao administrador para redefinir.</p>
      </form>
    </div>
  );
}
