/** Documentos anexos (contrato §16.4, spec v3.15 T06 "Documentos anexos"): NF, packing list, precificador, outro. */
import { useEffect, useState } from "react";
import { api, qs } from "./cliente";

export type TipoAnexo = "NF" | "PACKING_LIST" | "PRECIFICADOR" | "OUTRO";
export const TIPOS_ANEXO: TipoAnexo[] = ["NF", "PACKING_LIST", "PRECIFICADOR", "OUTRO"];
export const TIPO_ANEXO: Record<TipoAnexo, string> = {
  NF: "NF", PACKING_LIST: "Packing list", PRECIFICADOR: "Precificador do contêiner", OUTRO: "Outro",
};

export interface Anexo {
  id: number; tipo: TipoAnexo; descricao: string | null; nome_arquivo: string; content_type?: string | null;
  tamanho_bytes: number; ligado_a?: "ENTRADA" | "CONTEINER" | "LOTE"; da_origem?: string | null;
  usuario: string | null; criado_em: string;
  apagado?: boolean; apagado_por?: string | null; apagado_em?: string | null; justificativa?: string | null;
}

/** Anexo escolhido na tela antes de salvar a entrada (T06, T15): vai para a API depois do 201. */
export interface AnexoPendente { chave: number; tipo: TipoAnexo; descricao: string; arquivo: File }

export const MB_PADRAO = 10;
const EXT_BASE = ["pdf", "jpg", "jpeg", "png"];
const EXT_PLANILHA = ["xls", "xlsx"];

/** `accept` do input de arquivo para o tipo escolhido. */
export const aceitos = (tipo: TipoAnexo) =>
  [...EXT_BASE, ...(tipo === "PRECIFICADOR" ? EXT_PLANILHA : [])].map((e) => `.${e}`).join(",") + ",application/pdf,image/jpeg,image/png";

const mbTexto = (bytes: number) => (bytes / 1048576).toLocaleString("pt-BR", { maximumFractionDigits: 1 });

/** Mesmas mensagens do backend (ANEXO_TIPO_NAO_ACEITO, ANEXO_GRANDE), para avisar antes de enviar. */
export function conferirArquivo(f: File, tipo: TipoAnexo, maxMb: number): string | null {
  const ext = (f.name.split(".").pop() ?? "").toLowerCase();
  const ok = EXT_BASE.includes(ext) || (tipo === "PRECIFICADOR" && EXT_PLANILHA.includes(ext));
  if (!ok) return "Envie PDF, JPG ou PNG (no precificador, também XLS ou XLSX).";
  if (f.size === 0) return "O arquivo está vazio.";
  if (f.size > maxMb * 1048576) return `O arquivo tem ${mbTexto(f.size)} MB; o limite é ${maxMb.toLocaleString("pt-BR")} MB. Escaneie com resolução menor ou divida o PDF.`;
  return null;
}

/** "482 KB", "1,2 MB". */
export function tamanhoTexto(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${Math.round(bytes / 1024)} KB`;
  return `${mbTexto(bytes)} MB`;
}

export const urlArquivo = (id: number, baixar = false) => `/api/anexos/${id}/arquivo${baixar ? "?baixar=true" : ""}`;

/** POST do arquivo puro para `/lotes/{id}/anexos` ou `/entradas-nf/{id}/anexos`. */
export const enviarAnexo = (caminho: string, tipo: TipoAnexo, arquivo: File, descricao?: string) =>
  api.arquivo<Anexo>(`${caminho}${qs({ tipo, nome: arquivo.name, descricao: tipo === "OUTRO" ? descricao?.trim() : undefined })}`, arquivo);

/** Envia os anexos escolhidos antes de salvar. Devolve as mensagens dos que falharam (vazio = todos foram). */
export async function enviarPendentes(caminho: string, pendentes: AnexoPendente[]): Promise<string[]> {
  const falhas: string[] = [];
  for (const p of pendentes) {
    try { await enviarAnexo(caminho, p.tipo, p.arquivo, p.descricao); }
    catch (e) { falhas.push(`${p.arquivo.name}: ${e instanceof Error ? e.message : "não foi possível enviar"}`); }
  }
  return falhas;
}

/** Limite de tamanho da T23 (`ANEXO_MAX_MB`); se a leitura falhar, vale o padrão de 10 MB. */
export function useLimiteAnexo(): number {
  const [mb, setMb] = useState(MB_PADRAO);
  useEffect(() => {
    let vivo = true;
    api.get<{ chave: string; valor: string }[]>("/parametros")
      .then((ps) => {
        const v = Number((ps.find((p) => p.chave === "ANEXO_MAX_MB")?.valor ?? "").replace(",", "."));
        if (vivo && v > 0) setMb(v);
      })
      .catch(() => undefined);   // sem a T23, vale o padrão
    return () => { vivo = false; };
  }, []);
  return mb;
}
