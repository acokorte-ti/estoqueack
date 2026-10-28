import { useEffect, useState, type FormEvent } from "react";
import { api, NOME_PERFIL, type Perfil, type Usuario } from "../api/cliente";
import { useSessao } from "../api/sessao";

interface Criado { usuario: Usuario; senha_temporaria: string }

const PERFIS: { valor: Perfil; ajuda: string }[] = [
  { valor: "ESTOQUE", ajuda: "Movimentações em Itu: corte, recebimento, SA, consumo e RETO" },
  { valor: "OPERACAO_RJ", ajuda: "Barra Mansa: entrada por NF, corte, peso real e COP" },
  { valor: "ANALISE", ajuda: "Consulta, relatórios, destinações e notas" },
  { valor: "ADMIN", ajuda: "Tudo, inclusive usuários e parâmetros" },
];

export default function Usuarios() {
  const { usuario: eu } = useSessao();
  const [lista, setLista] = useState<Usuario[]>([]);
  const [form, setForm] = useState({ login: "", nome: "", email: "", perfil: "ESTOQUE" as Perfil, planta: "ITU" as "ITU" | "RJ" });
  const [senhaGerada, setSenhaGerada] = useState<{ nome: string; senha: string } | null>(null);
  const [erro, setErro] = useState("");

  const carregar = () => api.get<Usuario[]>("/usuarios").then(setLista).catch((e: Error) => setErro(e.message));
  useEffect(() => {
    void carregar();
  }, []);

  async function criar(e: FormEvent) {
    e.preventDefault();
    setErro("");
    try {
      const r = await api.post<Criado>("/usuarios", { ...form, email: form.email || null });
      setSenhaGerada({ nome: r.usuario.nome, senha: r.senha_temporaria });
      setForm({ ...form, login: "", nome: "", email: "" });
      void carregar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao criar usuário.");
    }
  }

  async function redefinir(u: Usuario) {
    if (!confirm(`Gerar nova senha temporária para ${u.nome}? As sessões abertas dele serão encerradas.`)) return;
    const r = await api.post<Criado>(`/usuarios/${u.id}/redefinir-senha`);
    setSenhaGerada({ nome: u.nome, senha: r.senha_temporaria });
    void carregar();
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
        <p>Cada pessoa recebe uma senha temporária e cria a própria senha no primeiro acesso.</p>
      </header>

      {senhaGerada && (
        <div className="senha-gerada" role="status">
          <p>
            Senha temporária de <strong>{senhaGerada.nome}</strong>:
          </p>
          <code>{senhaGerada.senha}</code>
          <p className="desc">Entregue pessoalmente ou por canal seguro. Ela não será exibida de novo.</p>
          <button className="link" onClick={() => setSenhaGerada(null)}>Fechar</button>
        </div>
      )}
      {erro && <p className="erro">{erro}</p>}

      <form className="painel-form linha-form" onSubmit={criar}>
        <label>Login<input value={form.login} onChange={(e) => setForm({ ...form, login: e.target.value })} placeholder="fabiano.camargo" required /></label>
        <label>Nome<input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Fabiano Camargo" required /></label>
        <label>E-mail<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        <label>
          Perfil
          <select value={form.perfil} onChange={(e) => setForm({ ...form, perfil: e.target.value as Perfil })}>
            {PERFIS.map((p) => <option key={p.valor} value={p.valor}>{NOME_PERFIL[p.valor]}</option>)}
          </select>
        </label>
        <label>
          Planta
          <select value={form.planta} onChange={(e) => setForm({ ...form, planta: e.target.value as "ITU" | "RJ" })}>
            <option value="ITU">Itu</option>
            <option value="RJ">Barra Mansa</option>
          </select>
        </label>
        <button className="primario">Criar usuário</button>
        <p className="dica largura-total">{PERFIS.find((p) => p.valor === form.perfil)?.ajuda}</p>
      </form>

      <table className="tabela">
        <thead>
          <tr><th>Nome</th><th>Login</th><th>Perfil</th><th>Planta</th><th>Último acesso</th><th>Situação</th><th /></tr>
        </thead>
        <tbody>
          {lista.map((u) => (
            <tr key={u.id} className={u.ativo ? "" : "inativo"}>
              <td>{u.nome}</td>
              <td>{u.login}</td>
              <td>{NOME_PERFIL[u.perfil]}</td>
              <td>{u.planta === "RJ" ? "Barra Mansa" : "Itu"}</td>
              <td>{u.ultimo_login ? new Date(u.ultimo_login).toLocaleString("pt-BR") : "Nunca"}</td>
              <td>{u.ativo ? (u.trocar_senha ? "Aguardando 1º acesso" : "Ativo") : "Desativado"}</td>
              <td className="acoes">
                <button className="link" onClick={() => void redefinir(u)}>Redefinir senha</button>
                {u.id !== eu?.id && (
                  <button className="link" onClick={() => void alternarAtivo(u)}>{u.ativo ? "Desativar" : "Reativar"}</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
