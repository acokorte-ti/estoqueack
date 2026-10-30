import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/cliente";
import CampoSenha from "../components/CampoSenha";

type Estado = { fase: "verificando" } | { fase: "invalido"; mensagem: string } | { fase: "pronto"; login: string } | { fase: "feito" };

/** Tela "Criar nova senha", aberta pelo link do e-mail: /redefinir-senha?token=… */
export default function RedefinirSenha() {
  const [params] = useSearchParams();
  const [token] = useState(() => params.get("token") ?? "");
  const [estado, setEstado] = useState<Estado>({ fase: "verificando" });
  const [nova, setNova] = useState("");
  const [repetir, setRepetir] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    // tira o token da barra de endereço e do histórico do navegador
    window.history.replaceState(null, "", "/redefinir-senha");
    if (token.length < 20) {
      setEstado({ fase: "invalido", mensagem: "Link incompleto. Abra de novo o link do e-mail ou peça um novo." });
      return;
    }
    api
      .post<{ valido: boolean; login?: string; mensagem?: string }>("/auth/recuperar/verificar", { token })
      .then((r) =>
        setEstado(r.valido ? { fase: "pronto", login: r.login ?? "" } : { fase: "invalido", mensagem: r.mensagem ?? "Link inválido ou expirado." }),
      )
      .catch((e: Error) => setEstado({ fase: "invalido", mensagem: e.message }));
  }, [token]);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    if (nova !== repetir) return setErro("A repetição não confere com a nova senha.");
    setEnviando(true);
    try {
      await api.post("/auth/recuperar/redefinir", { token, nova_senha: nova });
      setEstado({ fase: "feito" });
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível salvar a nova senha.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="entrada">
      <form className="entrada-form" onSubmit={enviar}>
        <img className="entrada-logo" src="/logo-acokorte.png" alt="AçoKorte" width={216} height={44} />
        <h1>Criar nova senha</h1>

        {estado.fase === "verificando" && <p className="entrada-sub">Conferindo o link…</p>}

        {estado.fase === "invalido" && (
          <>
            <p className="erro" role="alert">{estado.mensagem}</p>
            <Link className="primario" to="/esqueci-senha">Pedir um novo link</Link>
            <Link className="link entrada-link" to="/entrar">Voltar para o login</Link>
          </>
        )}

        {estado.fase === "pronto" && (
          <>
            <p className="entrada-sub">
              Login: <strong>{estado.login}</strong>
            </p>
            <CampoSenha rotulo="Nova senha" autoComplete="new-password" valor={nova} aoMudar={setNova} autoFocus />
            <CampoSenha rotulo="Repita a nova senha" autoComplete="new-password" valor={repetir} aoMudar={setRepetir} />
            <p className="dica">Mínimo de 6 caracteres.</p>
            {erro && <p className="erro" role="alert">{erro}</p>}
            <button className="primario" disabled={enviando}>
              {enviando ? "Salvando…" : "Salvar nova senha"}
            </button>
          </>
        )}

        {estado.fase === "feito" && (
          <>
            <p className="validacao ok" role="status">
              Nova senha salva. Por segurança, as sessões abertas foram encerradas.
            </p>
            <Link className="primario" to="/entrar">Entrar com a nova senha</Link>
          </>
        )}
      </form>
    </div>
  );
}
