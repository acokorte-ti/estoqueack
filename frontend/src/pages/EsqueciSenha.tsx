import { useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api/cliente";

export default function EsqueciSenha() {
  const local = useLocation();
  const [identificador, setIdentificador] = useState((local.state as { login?: string } | null)?.login ?? "");
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      const r = await api.post<{ mensagem: string }>("/auth/recuperar", { identificador: identificador.trim() });
      setMensagem(r.mensagem);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível enviar o pedido.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="entrada">
      <form className="entrada-form" onSubmit={enviar}>
        <img className="entrada-logo" src="/logo-acokorte.png" alt="AçoKorte" width={216} height={44} />
        <h1>Esqueci minha senha</h1>
        {mensagem ? (
          <>
            <p className="validacao ok" role="status">{mensagem}</p>
            <p className="dica">
              O link vale 30 minutos e só pode ser usado uma vez. Não chegou em alguns minutos? Peça ao administrador
              para redefinir a sua senha.
            </p>
            <Link className="primario" to="/entrar">Voltar para o login</Link>
          </>
        ) : (
          <>
            <p className="entrada-sub">Informe seu login ou e-mail. Enviaremos um link para você criar uma senha nova.</p>
            <label>
              Login ou e-mail
              <input
                autoFocus
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                placeholder="nome.sobrenome"
                value={identificador}
                onChange={(e) => setIdentificador(e.target.value)}
                minLength={3}
                required
              />
            </label>
            {erro && <p className="erro" role="alert">{erro}</p>}
            <button className="primario" disabled={enviando}>
              {enviando ? "Enviando…" : "Enviar link por e-mail"}
            </button>
            <Link className="link entrada-link" to="/entrar">Voltar para o login</Link>
          </>
        )}
      </form>
    </div>
  );
}
