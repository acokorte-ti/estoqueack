// Cliente HTTP da API. Sessão em cookie HttpOnly; CSRF enviado no header (double-submit).

export class ErroApi extends Error {
  constructor(public status: number, message: string, public dados?: unknown) {
    super(message);
  }
}

function lerCookie(nome: string): string | undefined {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(nome + "="))
    ?.split("=")[1];
}

async function requisitar<T>(metodo: string, caminho: string, corpo?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (corpo !== undefined) headers["Content-Type"] = "application/json";
  if (metodo !== "GET") {
    const csrf = lerCookie("ack_csrf");
    if (csrf) headers["X-CSRF-Token"] = decodeURIComponent(csrf);
  }
  const r = await fetch(`/api${caminho}`, {
    method: metodo,
    headers,
    credentials: "same-origin",
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  });
  if (r.status === 204) return undefined as T;
  const dados = await r.json().catch(() => undefined);
  if (!r.ok) {
    const detalhe = (dados as { detail?: unknown } | undefined)?.detail;
    const msg =
      typeof detalhe === "string"
        ? detalhe
        : Array.isArray(detalhe)
          ? mensagemCampos(detalhe as ErroCampo[])
          : `Não foi possível concluir (erro ${r.status}).`;
    throw new ErroApi(r.status, msg, dados);
  }
  return dados as T;
}

// 422 do FastAPI/Pydantic: transforma a lista técnica em frase para o usuário.
interface ErroCampo { loc?: (string | number)[]; type?: string }
const NOME_CAMPO: Record<string, string> = {
  login: "Login", nome: "Nome completo", email: "E-mail", senha: "Senha", nova_senha: "Nova senha",
  identificador: "Login ou e-mail", perfil: "Perfil", planta: "Planta",
};
const MSG_CAMPO: Record<string, string> = {
  login: "Login: use nome.sobrenome, em minúsculas e sem acento (ex.: fabiano.camargo).",
  email: "E-mail inválido. Confira o endereço (ex.: nome@acokorte.com.br).",
};
function mensagemCampos(erros: ErroCampo[]): string {
  const campos = [...new Set(erros.map((e) => String(e.loc?.[e.loc.length - 1] ?? "")).filter(Boolean))];
  if (!campos.length) return "Confira os campos preenchidos.";
  return campos.map((c) => MSG_CAMPO[c] ?? `Confira o campo ${NOME_CAMPO[c] ?? c}.`).join(" ");
}

/** Mesmo padrão do backend (schemas.LOGIN_PADRAO): nome.sobrenome */
export const LOGIN_PADRAO = "[a-z]+(\\.[a-z]+)+";

export const api = {
  get: <T,>(c: string) => requisitar<T>("GET", c),
  post: <T,>(c: string, b?: unknown) => requisitar<T>("POST", c, b ?? {}),
  patch: <T,>(c: string, b: unknown) => requisitar<T>("PATCH", c, b),
};

export type Perfil = "ADMIN" | "ESTOQUE" | "OPERACAO_RJ" | "ANALISE";

export interface Usuario {
  id: number;
  login: string;
  nome: string;
  email: string | null;
  perfil: Perfil;
  planta: "ITU" | "RJ";
  ativo: boolean;
  trocar_senha: boolean;
  ultimo_login: string | null;
}

export interface Sessao {
  usuario: Usuario;
  csrf: string;
  expira_em: string;
}

export interface Ocorrencia {
  codigo: string;
  nivel: "ERRO" | "CIENCIA" | "ALERTA";
  mensagem: string;
  dados: Record<string, unknown>;
}

export const NOME_PERFIL: Record<Perfil, string> = {
  ADMIN: "Administrador",
  ESTOQUE: "Estoque Itu",
  OPERACAO_RJ: "Operação RJ",
  ANALISE: "Análise",
};

export const kg = (v: number) =>
  v.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
