import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ESTOQUE_NOME, kg, num, qs } from "../api/cliente";
import { useSessao } from "../api/sessao";
import { TIPO_LOTE, type Agrupado, type Lote } from "../api/lote";

interface Pagina<T> { itens: T[]; total: number; pagina: number; por_pagina: number }

const ESTOQUES = [
  { valor: "", nome: "Todos" },
  { valor: "ESTOQUE_MEGA", nome: "Estoque Mega" },
  { valor: "RJ_NO_RIO", nome: "RJ no Rio" },
  { valor: "RJ_EM_ITU", nome: "RJ em Itu" },
];
const VAZIO = { liga: "", formato: "", conteiner: "", codigo_mega: "", busca: "", esp_de: "", esp_ate: "", lar_de: "", lar_ate: "", dia_de: "", dia_ate: "",
  com_saldo: true, com_destinacao: false, origem_nao_identificada: false };

/** T04 Consulta de estoque. Operação RJ vê só RJ no Rio (a API já força). */
export default function Estoque() {
  const { usuario } = useSessao();
  const nav = useNavigate();
  const soRj = usuario?.perfil === "OPERACAO_RJ";
  const [params, setParams] = useSearchParams();
  const [estoque, setEstoque] = useState(soRj ? "RJ_NO_RIO" : params.get("estoque") ?? "");
  const [visao, setVisao] = useState<"lote" | "item">("lote");
  const [f, setF] = useState(VAZIO);
  const [pag, setPag] = useState(1);
  const [lotes, setLotes] = useState<Pagina<Lote> | null>(null);
  const [grupos, setGrupos] = useState<Pagina<Agrupado> | null>(null);
  const [erro, setErro] = useState("");

  const filtros = useCallback(() => qs({
    estoque: estoque || undefined, liga: f.liga.trim(), formato: f.formato, conteiner: f.conteiner.trim(), codigo_mega: num(f.codigo_mega),
    busca: f.busca.trim(), espessura_de: num(f.esp_de), espessura_ate: num(f.esp_ate), largura_de: num(f.lar_de), largura_ate: num(f.lar_ate),
    diametro_de: num(f.dia_de), diametro_ate: num(f.dia_ate), com_saldo: f.com_saldo, com_destinacao: f.com_destinacao || undefined,
    origem_nao_identificada: f.origem_nao_identificada || undefined, pagina: pag, por_pagina: 50,
  }), [estoque, f, pag]);

  useEffect(() => {
    const t = window.setTimeout(async () => {
      setErro("");
      try {
        if (visao === "lote") setLotes(await api.get<Pagina<Lote>>(`/lotes${filtros()}`));
        else setGrupos(await api.get<Pagina<Agrupado>>(`/lotes/agrupado${filtros()}`));
      } catch (e) {
        setErro(e instanceof Error ? e.message : "Não foi possível consultar o estoque.");
      }
    }, 300);
    return () => window.clearTimeout(t);
  }, [filtros, visao]);

  const mudar = (p: Partial<typeof f>) => { setF({ ...f, ...p }); setPag(1); };
  const atual = visao === "lote" ? lotes : grupos;
  const paginas = atual ? Math.max(1, Math.ceil(atual.total / atual.por_pagina)) : 1;
  const somaSaldo = visao === "lote" ? lotes?.itens.reduce((a, l) => a + l.saldo_kg, 0) : grupos?.itens.reduce((a, g) => a + g.saldo_kg, 0);

  return (
    <>
      <header className="cabecalho">
        <h1>Consulta de estoque</h1>
        <p>{soRj ? "Lotes do RJ no Rio." : "Lotes dos três estoques. Clique num lote para ver movimentos, origem, reservas e notas."}</p>
      </header>

      {!soRj && (
        <div className="chips" role="group" aria-label="Estoque" style={{ marginBottom: "var(--esp-3)" }}>
          {ESTOQUES.map((e) => (
            <button key={e.valor} type="button" className="chip" aria-pressed={estoque === e.valor}
              onClick={() => { setEstoque(e.valor); setPag(1); setParams(e.valor ? { estoque: e.valor } : {}); }}>{e.nome}</button>
          ))}
        </div>
      )}

      <div className="barra-filtros">
        <label style={{ flexBasis: "18rem" }}>Buscar<input value={f.busca} onChange={(e) => mudar({ busca: e.target.value })} placeholder="lote, contêiner ou descrição" /></label>
        <label>Liga<input value={f.liga} onChange={(e) => mudar({ liga: e.target.value.toUpperCase() })} placeholder="H13" /></label>
        <label>Contêiner<input value={f.conteiner} onChange={(e) => mudar({ conteiner: e.target.value.toUpperCase() })} /></label>
        <label className="marcar"><input type="checkbox" checked={f.com_saldo} onChange={(e) => mudar({ com_saldo: e.target.checked })} /><span>Só com saldo</span></label>
      </div>
      <details className="avancado mais-filtros">
        <summary>Mais filtros (formato, bitola, código Mega, reserva, origem)</summary>
        <div className="barra-filtros">
          <label>Formato
            <select value={f.formato} onChange={(e) => mudar({ formato: e.target.value })}>
              <option value="">Todos</option><option value="RETANGULAR">Retangular</option><option value="REDONDO">Redondo</option><option value="RETO">RETO</option>
            </select>
          </label>
          <label>Espessura de<input inputMode="decimal" value={f.esp_de} onChange={(e) => mudar({ esp_de: e.target.value })} /></label>
          <label>até<input inputMode="decimal" value={f.esp_ate} onChange={(e) => mudar({ esp_ate: e.target.value })} /></label>
          <label>Largura de<input inputMode="decimal" value={f.lar_de} onChange={(e) => mudar({ lar_de: e.target.value })} /></label>
          <label>até<input inputMode="decimal" value={f.lar_ate} onChange={(e) => mudar({ lar_ate: e.target.value })} /></label>
          <label>Diâmetro de<input inputMode="decimal" value={f.dia_de} onChange={(e) => mudar({ dia_de: e.target.value })} /></label>
          <label>até<input inputMode="decimal" value={f.dia_ate} onChange={(e) => mudar({ dia_ate: e.target.value })} /></label>
          {!soRj && <label>Código Mega<input inputMode="numeric" value={f.codigo_mega} onChange={(e) => mudar({ codigo_mega: e.target.value })} /></label>}
          <label className="marcar"><input type="checkbox" checked={f.com_destinacao} onChange={(e) => mudar({ com_destinacao: e.target.checked })} /><span>Só com reserva ou restrição</span></label>
          <label className="marcar"><input type="checkbox" checked={f.origem_nao_identificada} onChange={(e) => mudar({ origem_nao_identificada: e.target.checked })} /><span>Só origem não identificada</span></label>
        </div>
        <div className="botoes"><button className="link" onClick={() => { setF(VAZIO); setPag(1); }}>Limpar filtros</button></div>
      </details>

      <div className="barra-acoes">
        <span className="contagem">
          {atual ? `${atual.total.toLocaleString("pt-BR")} ${visao === "lote" ? "lote(s)" : "item(ns)"}` : ""}
          {somaSaldo !== undefined && ` · ${kg(somaSaldo)} kg nesta página`}
        </span>
        <div className="chips" role="group" aria-label="Visão">
          <button type="button" className="chip" aria-pressed={visao === "lote"} onClick={() => { setVisao("lote"); setPag(1); }}>Por lote</button>
          <button type="button" className="chip" aria-pressed={visao === "item"} onClick={() => { setVisao("item"); setPag(1); }}>Agrupado por item</button>
        </div>
      </div>

      {erro && <p className="erro" role="alert">{erro}</p>}

      {visao === "lote" && lotes && (lotes.itens.length ? (
        <div className="tabela-rolagem">
          <table className="tabela tabela-clicavel">
            <thead><tr><th>Lote</th><th>Material</th><th>Contêiner</th><th>Estoque</th><th className="num">Saldo</th><th className="num">Reservado</th><th className="num">Disponível</th><th>Origem</th><th><span className="sr-only">Indicadores</span></th></tr></thead>
            <tbody>
              {lotes.itens.map((l) => (
                <tr key={l.id} onClick={() => nav(`/estoque/${l.id}`)}>
                  <td><Link to={`/estoque/${l.id}`} onClick={(e) => e.stopPropagation()}>{l.codigo}</Link>{l.tipo !== "ORIGINAL" && <><br /><span className="etiqueta">{TIPO_LOTE[l.tipo]}</span></>}</td>
                  <td><strong>{l.liga} {l.bitola}</strong><br /><span className="desc">{l.descricao ?? ""}{l.codigo_mega ? ` · Mega ${l.codigo_mega}` : ""}</span></td>
                  <td>{l.conteiner ?? "—"}</td>
                  <td><span className={`estoque-tag ${l.estoque}`}>{ESTOQUE_NOME[l.estoque]}</span></td>
                  <td className="num">{kg(l.saldo_kg)}</td>
                  <td className="num">{l.reservado_kg ? kg(l.reservado_kg) : "—"}</td>
                  <td className="num"><strong>{kg(l.disponivel_kg)}</strong></td>
                  <td>{l.origem ? <span className="desc">{l.origem.conteiner ?? "—"} · {l.origem.bitola}</span> : l.indicadores.origem_nao_identificada ? <span className="etiqueta atencao">não identificada</span> : "—"}</td>
                  <td>
                    {l.indicadores.destinacao && <span className="etiqueta atencao" title="Reserva ou restrição">reserva</span>}
                    {l.indicadores.nota && <span className="etiqueta info" title="Tem nota">nota</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className="estado-vazio"><strong>Nenhum lote com esses filtros</strong>Tire algum filtro ou desmarque "Só com saldo".</div>)}

      {visao === "item" && grupos && (grupos.itens.length ? (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead><tr><th>Liga</th><th>Bitola</th><th className="num">Lotes</th><th className="num">Estoque Mega</th><th className="num">RJ no Rio</th><th className="num">RJ em Itu</th><th className="num">Saldo</th><th className="num">Disponível</th></tr></thead>
            <tbody>
              {grupos.itens.map((g) => (
                <tr key={`${g.liga}-${g.formato}-${g.bitola}`}>
                  <td><strong>{g.liga}</strong></td><td>{g.bitola}{g.formato === "RETO" ? "" : ""}</td><td className="num">{g.lotes}</td>
                  <td className="num">{g.por_estoque.ESTOQUE_MEGA ? kg(g.por_estoque.ESTOQUE_MEGA) : "—"}</td>
                  <td className="num">{g.por_estoque.RJ_NO_RIO ? kg(g.por_estoque.RJ_NO_RIO) : "—"}</td>
                  <td className="num">{g.por_estoque.RJ_EM_ITU ? kg(g.por_estoque.RJ_EM_ITU) : "—"}</td>
                  <td className="num">{kg(g.saldo_kg)}</td><td className="num"><strong>{kg(g.disponivel_kg)}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className="estado-vazio"><strong>Nenhum item com esses filtros</strong></div>)}

      {atual && paginas > 1 && (
        <div className="paginacao">
          <button className="secundario" disabled={pag <= 1} onClick={() => setPag(pag - 1)}>Anterior</button>
          <span>Página {pag} de {paginas}</span>
          <button className="secundario" disabled={pag >= paginas} onClick={() => setPag(pag + 1)}>Próxima</button>
        </div>
      )}
    </>
  );
}
