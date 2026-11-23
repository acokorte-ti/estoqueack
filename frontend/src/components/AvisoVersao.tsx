import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

/**
 * Versão nova publicada (2026-11-23, Matheus via o Eduardo: "estou vendo a versão antiga"): a aba aberta continua
 * rodando o JavaScript de quando foi carregada, porque o sistema não recarrega a página sozinho. A cada 5 min e
 * quando a aba volta a ficar visível, lê o index.html do servidor e compara o arquivo principal (index-<hash>.js).
 * Se mudou: mostra a faixa "Atualizar" e, na próxima troca de tela, recarrega sozinho (o formulário da tela anterior
 * já foi deixado). Em desenvolvimento (Vite, sem /assets/index-*.js) não faz nada.
 */
const INTERVALO_MS = 5 * 60 * 1000;
const PADRAO = /\/assets\/index-[^"']+\.js/;

function scriptAtual(): string | null {
  const s = document.querySelector<HTMLScriptElement>('script[type="module"][src*="/assets/index-"]');
  return s ? new URL(s.src, location.href).pathname : null;
}

export default function AvisoVersao() {
  const atual = useRef(scriptAtual());
  const [nova, setNova] = useState(false);
  const local = useLocation();
  const primeiraTela = useRef(local.key);

  useEffect(() => {
    if (!atual.current) return;
    let vivo = true;
    async function conferir() {
      if (document.visibilityState !== "visible") return;
      try {
        const r = await fetch("/", { cache: "no-store", credentials: "same-origin" });
        if (!r.ok) return;
        const publicado = (await r.text()).match(PADRAO)?.[0];
        if (vivo && publicado && publicado !== atual.current) setNova(true);
      } catch {
        /* sem rede: tenta na próxima */
      }
    }
    const t = window.setInterval(() => void conferir(), INTERVALO_MS);
    const aoVoltar = () => void conferir();
    document.addEventListener("visibilitychange", aoVoltar);
    return () => {
      vivo = false;
      window.clearInterval(t);
      document.removeEventListener("visibilitychange", aoVoltar);
    };
  }, []);

  // versão nova já avisada: a próxima troca de tela carrega a página de novo (sem perder trabalho em andamento)
  useEffect(() => {
    if (nova && local.key !== primeiraTela.current) window.location.reload();
    primeiraTela.current = local.key;
  }, [local.key, nova]);

  if (!nova) return null;
  return (
    <div className="aviso-versao" role="status">
      <span>Há uma versão nova do sistema.</span>
      <button type="button" className="secundario pequeno" onClick={() => window.location.reload()}>Atualizar agora</button>
    </div>
  );
}
