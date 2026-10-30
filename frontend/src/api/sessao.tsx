import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ErroApi, type Sessao, type Usuario } from "./cliente";

interface Ctx {
  usuario: Usuario | null;
  carregando: boolean;
  entrar: (login: string, senha: string, lembrar?: boolean) => Promise<Usuario>;
  sair: () => Promise<void>;
  recarregar: () => Promise<void>;
}

const SessaoCtx = createContext<Ctx | null>(null);

export function SessaoProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [carregando, setCarregando] = useState(true);

  const recarregar = useCallback(async () => {
    try {
      const s = await api.get<Sessao>("/auth/eu");
      setUsuario(s.usuario);
    } catch (e) {
      if (!(e instanceof ErroApi) || e.status !== 401) console.error(e);
      setUsuario(null);
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    void recarregar();
  }, [recarregar]);

  const entrar = async (login: string, senha: string, lembrar = false) => {
    const s = await api.post<Sessao>("/auth/login", { login, senha, lembrar });
    setUsuario(s.usuario);
    return s.usuario;
  };

  const sair = async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setUsuario(null);
    }
  };

  return (
    <SessaoCtx.Provider value={{ usuario, carregando, entrar, sair, recarregar }}>{children}</SessaoCtx.Provider>
  );
}

export function useSessao(): Ctx {
  const c = useContext(SessaoCtx);
  if (!c) throw new Error("useSessao fora do SessaoProvider");
  return c;
}
