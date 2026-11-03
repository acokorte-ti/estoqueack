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
  put: <T,>(c: string, b: unknown) => requisitar<T>("PUT", c, b),
  delete: <T,>(c: string) => requisitar<T>("DELETE", c),
};

/** Resposta do padrão prévia/validação (contrato §1.5). O 409 da gravação traz o mesmo corpo. */
export interface Validacao<R = Record<string, unknown>> {
  ok: boolean;
  ocorrencias: Ocorrencia[];
  resultado: R | null;
}

/** Se o erro for um 409 com corpo de validação, devolve esse corpo; senão, null. */
export function validacaoDoErro<R>(e: unknown): Validacao<R> | null {
  if (e instanceof ErroApi && e.status === 409) {
    const d = e.dados as Partial<Validacao<R>> | undefined;
    if (d && Array.isArray(d.ocorrencias)) return { ok: false, ocorrencias: d.ocorrencias, resultado: d.resultado ?? null };
  }
  return null;
}

/** Monta a query string ignorando vazios; arrays viram parâmetros repetidos. */
export function qs(p: Record<string, string | number | boolean | null | undefined | (string | number)[]>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(p)) {
    if (v === null || v === undefined || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => u.append(k, String(x)));
    else u.append(k, String(v));
  }
  const s = u.toString();
  return s ? `?${s}` : "";
}

export const ESTOQUE_NOME: Record<string, string> = {
  ESTOQUE_MEGA: "Estoque Mega",
  RJ_NO_RIO: "RJ no Rio",
  RJ_EM_ITU: "RJ em Itu",
};

export const data = (iso: string | null | undefined) =>
  iso ? new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).toLocaleDateString("pt-BR") : "—";

export const num = (s: string) => (s.trim() === "" ? undefined : Number(s.replace(",", ".")));

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
