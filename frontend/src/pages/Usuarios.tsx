import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, LOGIN_PADRAO, NOME_PERFIL, type Perfil, type Usuario } from "../api/cliente";
import { useSessao } from "../api/sessao";
import CampoSenha from "../components/CampoSenha";

interface Criado { usuario: Usuario; senha_temporaria: string | null }
type Aviso = { nome: string; senha: string | null; acao: "criado" | "redefinida" };

const PERFIS: { valor: Perfil; ajuda: string }[] = [
  { valor: "ESTOQUE", ajuda: "Movimentações em Itu: corte, recebimento, SA, consumo e RETO" },
  { valor: "OPERACAO_RJ", ajuda: "Barra Mansa: entrada por NF, corte, peso real e COP" },
  { valor: "ANALISE", ajuda: "Consulta, relatórios, destinações e notas" },
  { valor: "ADMIN", ajuda: "Tudo, inclusive usuários e parâmetros" },
];

const VAZIO = { login: "", nome: "", email: "", perfil: "ESTOQUE" as Perfil, planta: "ITU" as "ITU" | "RJ", senha: "", trocar_senha: true };
const AJUDA_SENHA = "Em branco: o sistema gera uma senha temporária. Preenchida: mínimo de 10 caracteres, com letras e números, sem o login.";

export default function Usuarios() {
  const { usuario: eu } = useSessao();
  const [lista, setLista] = useState<Usuario[]>([]);
  const [form, setForm] = useState(VAZIO);
  const [aviso, setAviso] = useState<Aviso | null>(null);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  // Redefinir senha (janela)
  const janela = useRef<HTMLDialogElement>(null);
  const [alvo, setAlvo] = useState<Usuario | null>(null);
  const [red, setRed] = useState({ senha: "", trocar_senha: true });
  const [erroRed, setErroRed] = useState("");

  // Editar dados (janela)
  const janelaEd = useRef<HTMLDialogElement>(null);
  const [ed, setEd] = useState<{ id: number; nome: string; email: string; perfil: Perfil; planta: "ITU" | "RJ" } | null>(null);
  const [erroEd, setErroEd] = useState("");

  function abrirEditar(u: Usuario) {
    setEd({ id: u.id, nome: u.nome, email: u.email ?? "", perfil: u.perfil, planta: u.planta });
    setErroEd("");
    janelaEd.current?.showModal();
  }

  async function salvarEdicao(e: FormEvent) {
    e.preventDefault();
    if (!ed) return;
    setErroEd("");
    try {
      const corpo: Record<string, unknown> = { nome: ed.nome.trim(), perfil: ed.perfil, planta: ed.planta };
      if (ed.email.trim()) corpo.email = ed.email.trim();
      await api.patch(`/usuarios/${ed.id}`, corpo);
      janelaEd.current?.close();
      void carregar();
    } catch (err) {
      setErroEd(err instanceof Error ? err.message : "Erro ao salvar.");
    }
  }

  const carregar = () => api.get<Usuario[]>("/usuarios").then(setLista).catch((e: Error) => setErro(e.message));
  useEffect(() => {
    void carregar();
  }, []);

  async function criar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    setAviso(null);
    setEnviando(true);
    try {
      const r = await api.post<Criado>("/usuarios", {
        ...form,
        login: form.login.trim().toLowerCase(),
        email: form.email.trim() || null,
        senha: form.senha || null,
      });
      setAviso({ nome: r.usuario.nome, senha: r.senha_temporaria, acao: "criado" });
      setForm({ ...VAZIO, perfil: form.perfil, planta: form.planta });
      void carregar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao criar usuário.");
    } finally {
      setEnviando(false);
    }
  }

  function abrirRedefinir(u: Usuario) {
    setAlvo(u);
    setRed({ senha: "", trocar_senha: true });
    setErroRed("");
    janela.current?.showModal();
  }

  async function redefinir(e: FormEvent) {
    e.preventDefault();
    if (!alvo) return;
    setErroRed("");
    try {
      const r = await api.post<Criado>(`/usuarios/${alvo.id}/redefinir-senha`, {
        senha: red.senha || null,
        trocar_senha: red.trocar_senha,
      });
      janela.current?.close();
      setAviso({ nome: alvo.nome, senha: r.senha_temporaria, acao: "redefinida" });
      void carregar();
    } catch (err) {
      setErroRed(err instanceof Error ? err.message : "Erro ao redefinir a senha.");
    }
  }

  async function alternarAtivo(u: Usuario) {
    try {
      await api.patch(`/usuarios/${u.id}`, { ativo: !u.ativo });
      void carregar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao alterar usuário.");
    }
  }

  return (
    <>
      <header className="cabecalho">
        <h1>Usuários</h1>
        <p>Login no padrão nome.sobrenome. Com e-mail cadastrado, a pessoa pode recuperar a senha sozinha.</p>
      </header>

      {aviso && (
        <div className={aviso.senha ? "senha-gerada" : "validacao ok"} role="status">
          {aviso.senha ? (
            <>
              <p>
                Senha temporária de <strong>{aviso.nome}</strong>:
              </p>
              <code>{aviso.senha}</code>
              <p className="desc">Entregue pessoalmente ou por canal seguro. Ela não será exibida de novo.</p>
            </>
          ) : (
            <p>
              {aviso.acao === "criado" ? "Usuário" : "Senha de"} <strong>{aviso.nome}</strong>{" "}
              {aviso.acao === "criado" ? "criado com a senha que você definiu." : "redefinida com a senha que você definiu."}{" "}
              Informe a pessoa por canal seguro.
            </p>
          )}
          <button className="link" onClick={() => setAviso(null)}>Fechar</button>
        </div>
      )}
      {erro && <p className="erro" role="alert">{erro}</p>}

      <form className="painel-form form-usuario" onSubmit={criar}>
        <h2>Novo usuário</h2>
        <div className="grade-form">
          <label>
            Login
            <input
              value={form.login}
              onChange={(e) => setForm({ ...form, login: e.target.value })}
              placeholder="fabiano.camargo"
              autoCapitalize="none"
              spellCheck={false}
              pattern={LOGIN_PADRAO}
              title="nome.sobrenome, em minúsculas e sem acento"
              required
            />
            <small className="dica">nome.sobrenome, minúsculo, sem acento</small>
          </label>
          <label>
            Nome completo
            <input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Fabiano Camargo" required minLength={2} />
          </label>
          <label>
            E-mail
            <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="fabiano.camargo@acokorte.com.br" />
            <small className="dica">Necessário para "Esqueci minha senha"</small>
          </label>
          <label>
            Perfil
            <select value={form.perfil} onChange={(e) => setForm({ ...form, perfil: e.target.value as Perfil })}>
              {PERFIS.map((p) => <option key={p.valor} value={p.valor}>{NOME_PERFIL[p.valor]}</option>)}
            </select>
            <small className="dica">{PERFIS.find((p) => p.valor === form.perfil)?.ajuda}</small>
          </label>
          <label>
            Planta
            <select value={form.planta} onChange={(e) => setForm({ ...form, planta: e.target.value as "ITU" | "RJ" })}>
              <option value="ITU">Itu</option>
              <option value="RJ">Barra Mansa</option>
            </select>
          </label>
          <CampoSenha rotulo="Senha" autoComplete="new-password" valor={form.senha} aoMudar={(v) => setForm({ ...form, senha: v })} obrigatorio={false} ajuda={AJUDA_SENHA} />
        </div>
        <label className="marcar">
          <input type="checkbox" checked={form.trocar_senha} onChange={(e) => setForm({ ...form, trocar_senha: e.target.checked })} />
          <span>Obrigar troca de senha no primeiro acesso</span>
        </label>
        <div className="botoes">
          <button className="primario" disabled={enviando}>{enviando ? "Criando…" : "Criar usuário"}</button>
        </div>
      </form>

      <div className="tabela-rolagem">
      <table className="tabela">
        <thead>
          <tr><th>Nome</th><th>Login</th><th>E-mail</th><th>Perfil</th><th>Planta</th><th>Último acesso</th><th>Situação</th><th><span className="sr-only">Ações</span></th></tr>
        </thead>
        <tbody>
          {lista.map((u) => (
            <tr key={u.id} className={u.ativo ? "" : "inativo"}>
              <td>{u.nome}</td>
              <td>{u.login}</td>
              <td>{u.email ?? <span className="desc">sem e-mail</span>}</td>
              <td>{NOME_PERFIL[u.perfil]}</td>
              <td>{u.planta === "RJ" ? "Barra Mansa" : "Itu"}</td>
              <td>{u.ultimo_login ? new Date(u.ultimo_login).toLocaleString("pt-BR") : "Nunca"}</td>
              <td>{u.ativo ? (u.trocar_senha ? "Aguardando troca de senha" : "Ativo") : "Desativado"}</td>
              <td className="acoes">
                <button className="link" onClick={() => abrirEditar(u)}>Editar</button>
                <button className="link" onClick={() => abrirRedefinir(u)}>Redefinir senha</button>
                {u.id !== eu?.id && (
                  <button className="link" onClick={() => void alternarAtivo(u)}>{u.ativo ? "Desativar" : "Reativar"}</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>

      <dialog ref={janelaEd} className="janela" aria-labelledby="titulo-editar" onClose={() => setEd(null)}>
        {ed && (
          <form className="painel-form" onSubmit={salvarEdicao}>
            <h2 id="titulo-editar">Editar usuário</h2>
            <label>
              Nome completo
              <input value={ed.nome} onChange={(e) => setEd({ ...ed, nome: e.target.value })} required minLength={2} autoFocus />
            </label>
            <label>
              E-mail
              <input type="email" value={ed.email} onChange={(e) => setEd({ ...ed, email: e.target.value })} placeholder="nome.sobrenome@acokorte.com.br" />
              <small className="dica">Necessário para "Esqueci minha senha"</small>
            </label>
            <label>
              Perfil
              <select value={ed.perfil} onChange={(e) => setEd({ ...ed, perfil: e.target.value as Perfil })} disabled={ed.id === eu?.id}>
                {PERFIS.map((p) => <option key={p.valor} value={p.valor}>{NOME_PERFIL[p.valor]}</option>)}
              </select>
              {ed.id === eu?.id && <small className="dica">Você não pode mudar o seu próprio perfil.</small>}
            </label>
            <label>
              Planta
              <select value={ed.planta} onChange={(e) => setEd({ ...ed, planta: e.target.value as "ITU" | "RJ" })}>
                <option value="ITU">Itu</option>
                <option value="RJ">Barra Mansa</option>
              </select>
            </label>
            {erroEd && <p className="erro" role="alert">{erroEd}</p>}
            <div className="botoes">
              <button className="primario">Salvar alterações</button>
              <button type="button" className="secundario" onClick={() => janelaEd.current?.close()}>Cancelar</button>
            </div>
          </form>
        )}
      </dialog>

      <dialog ref={janela} className="janela" aria-labelledby="titulo-redefinir" onClose={() => setAlvo(null)}>
        <form className="painel-form" onSubmit={redefinir}>
          <h2 id="titulo-redefinir">Redefinir senha de {alvo?.nome}</h2>
          <p className="desc">As sessões abertas de {alvo?.login} serão encerradas.</p>
          <CampoSenha rotulo="Nova senha" autoComplete="new-password" valor={red.senha} aoMudar={(v) => setRed({ ...red, senha: v })} obrigatorio={false} ajuda={AJUDA_SENHA} autoFocus />
          <label className="marcar">
            <input type="checkbox" checked={red.trocar_senha} onChange={(e) => setRed({ ...red, trocar_senha: e.target.checked })} />
            <span>Obrigar troca de senha no próximo acesso</span>
          </label>
          {erroRed && <p className="erro" role="alert">{erroRed}</p>}
          <div className="botoes">
            <button className="primario">Redefinir senha</button>
            <button type="button" className="secundario" onClick={() => janela.current?.close()}>Cancelar</button>
          </div>
        </form>
      </dialog>
    </>
  );
}
