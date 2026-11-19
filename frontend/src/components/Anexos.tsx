import { useRef, useState, type ChangeEvent } from "react";
import { api, data } from "../api/cliente";
import { useSessao } from "../api/sessao";
import {
  aceitos, conferirArquivo, enviarAnexo, tamanhoTexto, TIPO_ANEXO, TIPOS_ANEXO, urlArquivo, useLimiteAnexo,
  type Anexo, type AnexoPendente, type TipoAnexo,
} from "../api/anexos";
import Icone from "./Icone";
import Janela, { fecharJanela } from "./Janela";

const toque = () => typeof window !== "undefined" && !!window.matchMedia?.("(pointer: coarse)").matches;

/**
 * Escolha de um documento: tipo, descrição (no "Outro") e arquivo. No celular/tablet também "Tirar foto".
 * `aoEscolher` recebe o arquivo já conferido (tipo e tamanho) e devolve a mensagem de erro, se houver.
 */
function FormAnexo({ aoEscolher, ocupado = false }: { aoEscolher: (tipo: TipoAnexo, descricao: string, f: File) => Promise<string | null>; ocupado?: boolean }) {
  const maxMb = useLimiteAnexo();
  const [tipo, setTipo] = useState<TipoAnexo>("NF");
  const [descricao, setDescricao] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const falta = tipo === "OUTRO" && !descricao.trim();
  const travado = ocupado || enviando || falta;

  async function escolher(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = "";            // permite escolher o mesmo arquivo de novo
    if (!f) return;
    const problema = conferirArquivo(f, tipo, maxMb);
    if (problema) { setErro(problema); return; }
    setErro(""); setEnviando(true);
    try {
      const r = await aoEscolher(tipo, descricao, f);
      if (r) setErro(r); else setDescricao("");
    } finally { setEnviando(false); }
  }

  return (
    <div className="form-anexo">
      <div className="linha-form" style={{ marginBottom: 0 }}>
        <label>Tipo do documento
          <select value={tipo} onChange={(e) => { setTipo(e.target.value as TipoAnexo); setErro(""); }}>
            {TIPOS_ANEXO.map((t) => <option key={t} value={t}>{TIPO_ANEXO[t]}</option>)}
          </select>
        </label>
        {tipo === "OUTRO" && <label style={{ flex: "1 1 16rem" }}>Descrição<input value={descricao} maxLength={120} onChange={(e) => setDescricao(e.target.value)} placeholder="Ex.: certificado de qualidade" /></label>}
        <div className="botoes">
          <label className={`secundario${travado ? " desabilitado" : ""}`} aria-disabled={travado}>
            <Icone nome="clipe" />{enviando ? "Enviando…" : "Anexar documento"}
            <input type="file" className="sr-only" accept={aceitos(tipo)} disabled={travado} onChange={(e) => void escolher(e)} />
          </label>
          {toque() && (
            <label className={`secundario${travado ? " desabilitado" : ""}`} aria-disabled={travado}>
              Tirar foto
              <input type="file" className="sr-only" accept="image/*" capture="environment" disabled={travado} onChange={(e) => void escolher(e)} />
            </label>
          )}
        </div>
      </div>
      <small className="dica">PDF, JPG ou PNG, até {maxMb.toLocaleString("pt-BR")} MB.{falta ? " Escreva a descrição antes de escolher o arquivo." : ""}</small>
      {erro && <p className="validacao erro" role="alert">{erro}</p>}
    </div>
  );
}

/** Documentos já anexados: abrir, baixar, apagar (com justificativa) e, para o Admin, restaurar os apagados. */
export function ListaAnexos({ anexos, aoMudar }: { anexos: Anexo[]; aoMudar: () => void }) {
  const { usuario } = useSessao();
  const admin = usuario?.perfil === "ADMIN";
  const [apagar, setApagar] = useState<Anexo | null>(null);
  const [erro, setErro] = useState("");
  const ativos = anexos.filter((a) => !a.apagado);
  const apagados = admin ? anexos.filter((a) => a.apagado) : [];

  async function restaurar(a: Anexo) {
    setErro("");
    try { await api.post(`/anexos/${a.id}/restaurar`); aoMudar(); }
    catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível restaurar."); }
  }

  return (
    <>
      {!ativos.length ? <p className="desc">Nenhum documento anexado.</p> : (
        <ul className="lista-simples lista-anexos">
          {ativos.map((a) => (
            <li key={a.id}>
              <div className="anexo-info">
                <span className="etiqueta">{TIPO_ANEXO[a.tipo] ?? a.tipo}</span>
                <strong className="anexo-nome">{a.descricao ? `${a.descricao} · ` : ""}{a.nome_arquivo}</strong>
                <span className="desc">{tamanhoTexto(a.tamanho_bytes)} · {data(a.criado_em)} · {a.usuario ?? "—"}</span>
                {a.da_origem && <span className="etiqueta info" title="Documento do lote de origem">da origem {a.da_origem}</span>}
              </div>
              <div className="botoes">
                <a className="link" href={urlArquivo(a.id)} target="_blank" rel="noopener noreferrer">Abrir</a>
                <a className="link" href={urlArquivo(a.id, true)} download={a.nome_arquivo}><Icone nome="baixar" />Baixar</a>
                <button className="link" onClick={() => setApagar(a)}>Apagar</button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {apagados.length > 0 && (
        <details className="avancado">
          <summary>Apagados ({apagados.length}), só o Admin vê</summary>
          <ul className="lista-simples lista-anexos">
            {apagados.map((a) => (
              <li key={a.id}>
                <div className="anexo-info">
                  <span className="etiqueta">{TIPO_ANEXO[a.tipo] ?? a.tipo}</span>
                  <strong className="anexo-nome">{a.nome_arquivo}</strong>
                  <span className="desc">apagado por {a.apagado_por ?? "—"}{a.apagado_em ? `, ${data(a.apagado_em)}` : ""}{a.justificativa ? `: ${a.justificativa}` : ""}</span>
                </div>
                <div className="botoes">
                  <a className="link" href={urlArquivo(a.id)} target="_blank" rel="noopener noreferrer">Abrir</a>
                  <button className="link" onClick={() => void restaurar(a)}>Restaurar</button>
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}
      {erro && <p className="erro" role="alert">{erro}</p>}
      {apagar && <JanelaApagar anexo={apagar} aoFechar={() => setApagar(null)} aoGravar={() => { setApagar(null); aoMudar(); }} />}
    </>
  );
}

function JanelaApagar({ anexo, aoFechar, aoGravar }: { anexo: Anexo; aoFechar: () => void; aoGravar: () => void }) {
  const [just, setJust] = useState("");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  async function ok() {
    setErro(""); setOcupado(true);
    try { await api.post(`/anexos/${anexo.id}/apagar`, { justificativa: just.trim() }); aoGravar(); }
    catch (e) { setErro(e instanceof Error ? e.message : "Não foi possível apagar."); }
    finally { setOcupado(false); }
  }
  return (
    <Janela titulo="Apagar documento" aoFechar={aoFechar}>
      <p><strong>{TIPO_ANEXO[anexo.tipo] ?? anexo.tipo}</strong> · {anexo.nome_arquivo}</p>
      <p className="desc">O documento sai da lista, mas não é destruído: fica guardado no backup e o Admin pode restaurar.</p>
      <label>Justificativa<textarea autoFocus rows={3} value={just} onChange={(e) => setJust(e.target.value)} placeholder="Ex.: anexado no lote errado" /></label>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="botoes">
        <button className="perigo" disabled={!just.trim() || ocupado} onClick={() => void ok()}>Apagar</button>
        <button className="secundario" onClick={(e) => fecharJanela(e.currentTarget)}>Voltar</button>
      </div>
    </Janela>
  );
}

/** T05: lista + "Anexar documento" que envia na hora para `enviarPara` (ex.: `/lotes/41/anexos`). */
export default function Anexos({ anexos, enviarPara, aoMudar }: { anexos: Anexo[]; enviarPara: string; aoMudar: () => void }) {
  return (
    <div className="anexos">
      <ListaAnexos anexos={anexos} aoMudar={aoMudar} />
      <FormAnexo aoEscolher={async (tipo, descricao, f) => {
        try { await enviarAnexo(enviarPara, tipo, f, descricao); aoMudar(); return null; }
        catch (e) { return e instanceof Error ? e.message : "Não foi possível anexar."; }
      }} />
    </div>
  );
}

/** T06 e T15: documentos escolhidos antes de salvar (vão para a API depois que a entrada ou o lote for criado). */
export function AnexosPendentes({ pendentes, aoMudar, ocupado = false }: { pendentes: AnexoPendente[]; aoMudar: (p: AnexoPendente[]) => void; ocupado?: boolean }) {
  const chave = useRef(0);
  chave.current = Math.max(chave.current, ...pendentes.map((p) => p.chave));
  return (
    <div className="anexos">
      {pendentes.length > 0 && (
        <ul className="lista-simples lista-anexos">
          {pendentes.map((p) => (
            <li key={p.chave}>
              <div className="anexo-info">
                <span className="etiqueta">{TIPO_ANEXO[p.tipo]}</span>
                <strong className="anexo-nome">{p.tipo === "OUTRO" && p.descricao ? `${p.descricao} · ` : ""}{p.arquivo.name}</strong>
                <span className="desc">{tamanhoTexto(p.arquivo.size)} · vai junto ao salvar</span>
              </div>
              <div className="botoes"><button type="button" className="link" disabled={ocupado} onClick={() => aoMudar(pendentes.filter((x) => x.chave !== p.chave))}>Tirar</button></div>
            </li>
          ))}
        </ul>
      )}
      <FormAnexo ocupado={ocupado} aoEscolher={async (tipo, descricao, f) => {
        chave.current += 1;
        aoMudar([...pendentes, { chave: chave.current, tipo, descricao: descricao.trim(), arquivo: f }]);
        return null;
      }} />
    </div>
  );
}
