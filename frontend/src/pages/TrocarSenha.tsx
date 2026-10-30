import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/cliente";
import { useSessao } from "../api/sessao";
import CampoSenha from "../components/CampoSenha";

export default function TrocarSenha() {
  const { usuario, recarregar } = useSessao();
  const nav = useNavigate();
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [repetir, setRepetir] = useState("");
  const [erro, setErro] = useState("");

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    if (nova !== repetir) return setErro("A confirmação não confere com a nova senha.");
    try {
      await api.post("/auth/trocar-senha", { senha_atual: atual, nova_senha: nova });
      await recarregar();
      nav("/", { replace: true });
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível trocar a senha.");
    }
  }

  return (
    <div className="entrada">
      <form className="entrada-form" onSubmit={enviar}>
        <img className="entrada-logo" src="/logo-acokorte.png" alt="AçoKorte" width={216} height={44} />
        <h1>Nova senha</h1>
        <p className="entrada-sub">
          {usuario?.trocar_senha
            ? "Sua senha é temporária. Crie uma senha pessoal para continuar."
            : "Troque sua senha de acesso."}
        </p>
        <CampoSenha rotulo="Senha atual" autoComplete="current-password" valor={atual} aoMudar={setAtual} autoFocus />
        <CampoSenha rotulo="Nova senha" autoComplete="new-password" valor={nova} aoMudar={setNova} />
        <CampoSenha rotulo="Repita a nova senha" autoComplete="new-password" valor={repetir} aoMudar={setRepetir} />
        <p className="dica">Mínimo de 10 caracteres, com letras e números, sem conter o seu login.</p>
        {erro && <p className="erro" role="alert">{erro}</p>}
        <button className="primario">Salvar nova senha</button>
      </form>
    </div>
  );
}
