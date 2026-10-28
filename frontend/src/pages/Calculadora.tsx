import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { api, kg, type Ocorrencia } from "../api/cliente";
import Ocorrencias from "../components/Ocorrencias";

type Formato = "RETANGULAR" | "REDONDO" | "ANEL";
interface Liga { codigo: string; nome: string; densidade: number; ativo: boolean }
interface Resultado { densidade: number; peso_unitario_kg: number; peso_total_kg: number }

const num = (s: string) => (s.trim() === "" ? undefined : Number(s.replace(",", ".")));

export default function Calculadora() {
  const [ligas, setLigas] = useState<Liga[]>([]);
  const [formato, setFormato] = useState<Formato>("RETANGULAR");
  const [liga, setLiga] = useState("H13");
  const [m, setM] = useState({ espessura: "", largura: "", diametro: "", diametro_interno: "", comprimento: "", quantidade: "1" });
  const [res, setRes] = useState<Resultado | null>(null);
  const [erro, setErro] = useState("");
  const [real, setReal] = useState("");
  const [ocorr, setOcorr] = useState<Ocorrencia[] | null>(null);

  useEffect(() => {
    api.get<Liga[]>("/ligas").then((l) => setLigas(l.filter((x) => x.ativo))).catch(() => setLigas([]));
  }, []);

  const campo = (k: keyof typeof m) => ({
    value: m[k],
    inputMode: "decimal" as const,
    onChange: (e: ChangeEvent<HTMLInputElement>) => setM({ ...m, [k]: e.target.value }),
  });

  async function calcular(e: FormEvent) {
    e.preventDefault();
    setErro("");
    setOcorr(null);
    try {
      const r = await api.post<Resultado>("/calculadora/peso", {
        formato,
        liga,
        espessura: num(m.espessura),
        largura: num(m.largura),
        diametro: num(m.diametro),
        diametro_interno: num(m.diametro_interno),
        comprimento: num(m.comprimento),
        quantidade: num(m.quantidade) ?? 1,
      });
      setRes(r);
    } catch (err) {
      setRes(null);
      setErro(err instanceof Error ? err.message : "Erro no cálculo.");
    }
  }

  async function conferir(e: FormEvent) {
    e.preventDefault();
    if (!res) return;
    const r = await api.post<{ ocorrencias: Ocorrencia[] }>("/calculadora/validar-peso-real", {
      previsto_kg: res.peso_total_kg,
      real_kg: num(real),
    });
    setOcorr(r.ocorrencias);
  }

  return (
    <>
      <header className="cabecalho">
        <h1>Calculadora de peso</h1>
        <p>Previsão de peso para NF de peça que ainda será cortada. O peso de balança sempre prevalece.</p>
      </header>

      <div className="duas-colunas">
        <form className="painel-form" onSubmit={calcular}>
          <fieldset className="formatos">
            <legend>Formato</legend>
            {(["RETANGULAR", "REDONDO", "ANEL"] as Formato[]).map((f) => (
              <label key={f} className={formato === f ? "opcao marcada" : "opcao"}>
                <input type="radio" name="formato" checked={formato === f} onChange={() => setFormato(f)} />
                {f === "RETANGULAR" ? "Chapa ou barra retangular" : f === "REDONDO" ? "Barra redonda" : "Anel"}
              </label>
            ))}
          </fieldset>

          <label>
            Liga
            <select value={liga} onChange={(e) => setLiga(e.target.value)}>
              {ligas.map((l) => (
                <option key={l.codigo} value={l.codigo}>
                  {l.codigo} ({l.densidade.toLocaleString("pt-BR")} g/cm³)
                </option>
              ))}
              {!ligas.length && <option value="H13">H13</option>}
            </select>
          </label>

          <div className="grade-medidas">
            {formato === "RETANGULAR" && (
              <>
                <label>Espessura (mm)<input {...campo("espessura")} required /></label>
                <label>Largura (mm)<input {...campo("largura")} required /></label>
              </>
            )}
            {formato !== "RETANGULAR" && (
              <label>{formato === "ANEL" ? "Diâmetro externo (mm)" : "Diâmetro (mm)"}<input {...campo("diametro")} required /></label>
            )}
            {formato === "ANEL" && <label>Diâmetro interno (mm)<input {...campo("diametro_interno")} /></label>}
            <label>{formato === "RETANGULAR" ? "Comprimento (mm)" : "Comprimento ou espessura (mm)"}<input {...campo("comprimento")} required /></label>
            <label>Quantidade<input {...campo("quantidade")} inputMode="numeric" /></label>
          </div>

          {erro && <p className="erro">{erro}</p>}
          <button className="primario">Calcular peso</button>
        </form>

        <section className="resultado" aria-live="polite">
          {res ? (
            <>
              <p className="resultado-rotulo">Peso previsto</p>
              <p className="resultado-valor numero">{kg(res.peso_total_kg)} kg</p>
              <p className="desc">
                {kg(res.peso_unitario_kg)} kg por peça, densidade {res.densidade.toLocaleString("pt-BR")} g/cm³
              </p>
              <form className="conferir" onSubmit={conferir}>
                <label>
                  Peso de balança (kg)
                  <input value={real} onChange={(e) => setReal(e.target.value)} inputMode="decimal" required />
                </label>
                <button className="secundario">Conferir tolerância</button>
              </form>
              {ocorr && <Ocorrencias itens={ocorr} />}
            </>
          ) : (
            <p className="desc">Preencha as medidas e calcule para ver o peso previsto.</p>
          )}
        </section>
      </div>
    </>
  );
}
