"""Ponta a ponta dos 5 caminhos (Parte C2, chat BANCO E TESTES) sobre uma CÓPIA do banco da homologação.

Executa pela API (dentro do processo, sem rede), com OPs reais abertas e o Mega real, os caminhos:
  A  corte no RJ → COP → SA → NF → envio → recebimento → Concluída
  B  peça inteira → COP → SA (previsto) → envio → recebimento (lote RJ em Itu) → corte em Itu → Concluída
  B2 corte em Itu de lote RJ em Itu → linha de SA → código + NF só fiscal
  C  corte em Itu de lote do Estoque Mega → instrução "Fazer no Mega"
  D  entrada por NF no RJ → lote novo (sem código do Mega, spec v3.7 §1.4)
e confere no fim: nenhum saldo negativo, em todo lote saldo = soma dos movimentos e nenhum lote do RJ (no Rio ou em
Itu) com código do Mega (v3.7: o código só existe no Estoque Mega; vale depois da recarga do zero).

Regras novas conferidas sem gravar nada a mais (só prévias, rodada de 2026-11-12):
  B   tolerância de 8 % no corte em Itu do lote RJ em Itu (P22(a)): 7 % passa, 9 % pede justificativa com "8 %"
  B2  corte em Itu marcado "consumo misto" (P26, opção A): a solicitação ao RJ marcada da mesma OP não avisa
      OP_DUPLICADA; a mesma solicitação sem a marca avisa

O Mega é só lido. A ÚNICA simulação é a confirmação do SA: um SA que o teste informou e que não teve carga real no
Mega é tratado como confirmado (no aceite real, o Fabiano faz a carga no Mega).

Uso no system-lab (o banco precisa terminar em "_e2e"; o script recusa qualquer outro):
    deploy/e2e/rodar_e2e.sh            # cria estoqueack_e2e a partir do banco da homologação e roda
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import sys
import time
from datetime import date
from typing import Any

JUST = "Teste ponta a ponta (E2E) do chat BANCO E TESTES"
SENHA = "E2e-Teste-2026"


# ---------------------------------------------------------------- cliente ASGI mínimo (sem httpx na imagem)

class Cliente:
    def __init__(self, app):
        self.app, self.cookies, self.csrf = app, {}, None

    def req(self, metodo: str, caminho: str, corpo: Any = None) -> tuple[int, Any]:
        qs = b""
        if "?" in caminho:
            caminho, q = caminho.split("?", 1)
            qs = q.encode()
        body = json.dumps(corpo).encode() if corpo is not None else b""
        h = [(b"host", b"e2e"), (b"content-type", b"application/json")]
        if self.cookies:
            h.append((b"cookie", "; ".join(f"{k}={v}" for k, v in self.cookies.items()).encode()))
        if self.csrf:
            h.append((b"x-csrf-token", self.csrf.encode()))
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": metodo,
                 "scheme": "https", "path": caminho, "raw_path": caminho.encode(), "query_string": qs, "headers": h,
                 "client": ("127.0.0.1", 1), "server": ("e2e", 443), "root_path": ""}
        resp: dict[str, Any] = {"status": None, "headers": [], "body": b""}
        enviado = False

        async def receive():
            nonlocal enviado
            if not enviado:
                enviado = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        async def send(m):
            if m["type"] == "http.response.start":
                resp["status"], resp["headers"] = m["status"], m["headers"]
            elif m["type"] == "http.response.body":
                resp["body"] += m.get("body", b"")

        asyncio.run(self.app(scope, receive, send))
        for k, v in resp["headers"]:
            if k.lower() == b"set-cookie":
                nome, val = v.decode().split(";")[0].split("=", 1)
                self.cookies[nome] = val
        try:
            dados = json.loads(resp["body"]) if resp["body"] else None
        except ValueError:
            dados = resp["body"].decode(errors="replace")
        return resp["status"], dados

    def entrar(self, login: str) -> None:
        self.cookies, self.csrf = {}, None
        st, d = self.req("POST", "/api/auth/login", {"login": login, "senha": SENHA})
        assert st == 200, f"login {login}: {st} {d}"
        self.csrf = d["csrf"]


class Falha(AssertionError):
    pass


def esperar(cond: bool, msg: str) -> None:
    if not cond:
        raise Falha(msg)


def gravar(c: Cliente, url_validar: str, url: str, corpo: dict, metodo: str = "POST") -> Any:
    """Prévia → confirma todos os 'estou ciente' com justificativa de teste → grava. ERRO = falha do caminho."""
    st, v = c.req("POST", url_validar, corpo)
    esperar(st == 200, f"{url_validar}: {st} {v}")
    erros = [o for o in v.get("ocorrencias", []) if o["nivel"] == "ERRO"]
    esperar(not erros, f"{url_validar}: bloqueado por {[(o['codigo'], o['mensagem']) for o in erros]}")
    corpo = {**corpo, "confirmacoes": {o["codigo"]: JUST for o in v.get("ocorrencias", []) if o["nivel"] == "CIENCIA"}}
    st, d = c.req(metodo, url, corpo)
    esperar(st in (200, 201), f"{url}: {st} {d}")
    return d


# ---------------------------------------------------------------- Mega: real, com a confirmação de SA simulada

class MegaE2E:
    def __init__(self, real):
        self.real = real
        self.simular: set[int] = set()
        self.simulados: list[int] = []

    def __getattr__(self, nome):
        return getattr(self.real, nome)

    def situacao_sa(self, codigo, desde):
        st = self.real.situacao_sa(codigo, desde)
        if codigo in self.simular and st.existe and st.qtd_entrada <= 0:
            self.simulados.append(codigo)
            return dataclasses.replace(st, qtd_entrada=1.0, nf_entrada=None)
        return st


# ---------------------------------------------------------------- dados

def preparar_usuarios(db) -> dict[str, str]:
    from app.core import seguranca
    from app.models import Usuario
    logins = {"itu": ("e2e.itu", "ESTOQUE", "ITU"), "rj": ("e2e.rj", "OPERACAO_RJ", "RJ"),
              "analise": ("e2e.analise", "ANALISE", "ITU")}
    for login, perfil, planta in logins.values():
        u = db.query(Usuario).filter_by(login=login).one_or_none() or Usuario(login=login)
        u.nome, u.email, u.perfil, u.planta = f"Teste {login}", None, perfil, planta
        u.senha_hash, u.trocar_senha, u.ativo, u.tentativas_falhas, u.bloqueado_ate = (
            seguranca.gerar_hash_senha(SENHA), False, True, 0, None)
        db.add(u)
    db.commit()
    return {k: v[0] for k, v in logins.items()}


def escolher_lote(db, pf: str, lf: str, minimo: float, exceto: set[int], *, retangular: bool = True,
                  codigo_mega: bool = False):
    from app.models import ItemMP, Lote
    q = (db.query(Lote).join(ItemMP, ItemMP.id == Lote.item_mp_id)
         .filter(Lote.planta_fiscal == pf, Lote.local_fisico == lf, Lote.status == "ATIVO", Lote.saldo_kg >= minimo,
                 ~Lote.id.in_(exceto or {-1})))
    if retangular:
        q = q.filter(ItemMP.formato == "RETANGULAR", ItemMP.espessura > 5, ItemMP.largura > 15)
    if codigo_mega:
        q = q.filter(ItemMP.codigo_mega.is_not(None))
    lote = q.order_by(Lote.saldo_kg.desc()).first()
    esperar(lote is not None, f"sem lote {pf}/{lf} com {minimo} kg para o teste")
    return lote


def escolher_ops(db, gateway, n: int, informadas: list[int]) -> list[int]:
    """OPs reais abertas (AB) para A, B, B2 (estrutura com SA = material RJ) e C (estrutura com MP = material Itu).
    Primeiro as informadas; senão, as mais recentes da carga. Ensaio de 04/11: a 1ª versão pegou para o B2 uma OP de
    material Itu (sem SA na estrutura nem no histórico) e o caminho parou no código do SA."""
    if informadas:
        return informadas[:n]
    com_sa: list[int] = []
    com_mp: list[int] = []
    for op in _candidatas(db):
        o = gateway.ordem_producao(op)
        if o is None or o.situacao != "AB" or not o.item_codigo:
            continue
        tipos = {c.tipo for c in gateway.estrutura_op(op)}
        if "SA" in tipos and len(com_sa) < n - 1:
            com_sa.append(op)
        elif "MP" in tipos and not com_mp:
            com_mp.append(op)
        if len(com_sa) == n - 1 and com_mp:
            return com_sa + com_mp
    raise Falha(f"OPs abertas insuficientes: {len(com_sa)} de material RJ e {len(com_mp)} de material Itu")


def _candidatas(db) -> list[int]:
    from sqlalchemy import select

    from app.models import CadastroSa, SolicitacaoCorte
    vistas: list[int] = []
    for (op,) in list(db.execute(select(SolicitacaoCorte.op).distinct().order_by(SolicitacaoCorte.op.desc())
                                 .limit(300))) + list(db.execute(select(CadastroSa.op).where(CadastroSa.op.is_not(None))
                                                                 .distinct().order_by(CadastroSa.op.desc()).limit(300))):
        if op not in vistas:
            vistas.append(op)
    return vistas


def medida_para(lote) -> dict:
    it = lote.item
    return {"formato": "RETANGULAR", "espessura": max(float(it.espessura) - 2, 1),
            "largura": max(float(it.largura) - 4, 1), "comprimento": 150}


# ---------------------------------------------------------------- caminhos

def caminho_a(c: Cliente, u: dict, lote, op: int, mega: MegaE2E, num_cop: int) -> dict:
    c.entrar(u["itu"])
    corpo = {"op": op, "liga": lote.item.liga.codigo, "medida": medida_para(lote),
             "itens": [{"lote_id": lote.id, "modo": "CORTAR_RJ", "quantidade": 2}], "enviar": True,
             "observacao": "TESTE E2E caminho A"}
    sol = gravar(c, "/api/solicitacoes/validar", "/api/solicitacoes", corpo)["solicitacoes"][0]
    esperar(sol["situacao"] == "ENVIADA", f"A: solicitação {sol['situacao']}")
    c.entrar(u["rj"])
    peso = float(sol["peso_previsto_kg"])
    gravar(c, f"/api/solicitacoes/{sol['id']}/corte/validar", f"/api/solicitacoes/{sol['id']}/corte",
           {"linhas": [{"lote_id": lote.id, "pecas": 2, "peso_real_kg": peso}]})
    cop = _cop_fechado(c, sol["id"], num_cop)
    _sa_confirmar(c, u, op, mega)
    c.entrar(u["rj"])
    st, d = c.req("POST", f"/api/cops/{cop}/nf", {"numero": f"E2E{num_cop}", "emitente": "OUTRO"})
    esperar(st == 200, f"A: NF {st} {d}")
    gravar(c, f"/api/cops/{cop}/enviar/validar", f"/api/cops/{cop}/enviar", {})
    _receber(c, u, cop)
    return {"solicitacao": sol["id"], "cop": cop, "situacao_final": _situacao(c, u, sol["id"])}


def caminho_b(c: Cliente, u: dict, lote, op: int, mega: MegaE2E, num_cop: int) -> dict:
    c.entrar(u["itu"])
    corpo = {"op": op, "liga": lote.item.liga.codigo, "medida": medida_para(lote),
             "itens": [{"lote_id": lote.id, "modo": "TRAZER_INTEIRA", "quantidade": 1}], "enviar": True,
             "observacao": "TESTE E2E caminho B"}
    sol = gravar(c, "/api/solicitacoes/validar", "/api/solicitacoes", corpo)["solicitacoes"][0]
    previsto = float(sol["peso_previsto_kg"])
    barra = round(min(previsto * 1.4, float(lote.saldo_kg)), 3)
    c.entrar(u["rj"])
    gravar(c, f"/api/solicitacoes/{sol['id']}/corte/validar", f"/api/solicitacoes/{sol['id']}/corte",
           {"linhas": [{"lote_id": lote.id, "pecas": 1, "peso_real_kg": barra}]})
    cop = _cop_fechado(c, sol["id"], num_cop)
    _sa_confirmar(c, u, op, mega)
    c.entrar(u["rj"])
    c.req("POST", f"/api/cops/{cop}/nf", {"numero": f"E2E{num_cop}", "emitente": "OUTRO"})
    gravar(c, f"/api/cops/{cop}/enviar/validar", f"/api/cops/{cop}/enviar", {})
    _receber(c, u, cop)
    esperar(_situacao(c, u, sol["id"]) == "AGUARDANDO_CORTE_ITU", "B: depois de receber deveria aguardar corte em Itu")
    c.entrar(u["itu"])
    st, sug = c.req("GET", f"/api/cortes-itu/sugestao?op={op}")
    esperar(st == 200 and sug.get("lote_id"), f"B: sem lote RJ em Itu sugerido ({st} {sug})")
    sobra = round(barra - previsto - 1, 3)
    base = {"op": op, "lote_id": sug["lote_id"], "sobra_kg": 0, "pecas": 1, "previsto_kg": previsto,
            "peso_usado_kg": barra}
    sete = _codigos(c, "/api/cortes-itu/validar", {**base, "consumo_kg": round(previsto * 1.07, 3)})
    esperar("EXCESSO_TOLERANCIA" not in sete, f"B: 7 % acima no RJ em Itu não deveria pedir justificativa ({sete})")
    st, v = c.req("POST", "/api/cortes-itu/validar", {**base, "consumo_kg": round(previsto * 1.09, 3)})
    exc = [o["mensagem"] for o in v.get("ocorrencias", []) if o["codigo"].startswith("EXCESSO_TOLERANCIA")]
    esperar(exc and "8 %" in exc[0], f"B: 9 % acima deveria pedir justificativa com o limite de 8 % ({exc})")
    corte = gravar(c, "/api/cortes-itu/validar", "/api/cortes-itu",
                   {"op": op, "lote_id": sug["lote_id"], "consumo_kg": previsto, "sobra_kg": max(sobra, 0.5),
                    "sobra_na_bitola": False, "pecas": 1, "observacao": "TESTE E2E caminho B"})
    return {"solicitacao": sol["id"], "cop": cop, "corte_itu": corte["id"],
            "lote_reto": (corte.get("lote_reto") or {}).get("codigo"), "situacao_final": _situacao(c, u, sol["id"])}


def caminho_b2(c: Cliente, u: dict, lote, op: int, mega: MegaE2E, lote_rj=None) -> dict:
    c.entrar(u["itu"])
    corte = gravar(c, "/api/cortes-itu/validar", "/api/cortes-itu",
                   {"op": op, "lote_id": lote.id, "consumo_kg": 10, "sobra_kg": 9.5, "sobra_na_bitola": True,
                    "peso_usado_kg": 20, "pecas": 1, "consumo_misto": True, "observacao": "TESTE E2E caminho B2"})
    esperar(corte.get("sa_id"), "B2: corte em lote fiscal RJ deveria gerar linha de SA")
    esperar(corte.get("consumo_misto") is True, "B2: o corte deveria voltar marcado como consumo misto")
    _sa_confirmar(c, u, op, mega, sa_id=corte["sa_id"])
    st, d = c.req("POST", "/api/sas/nf", {"ids": [corte["sa_id"]], "numero": "E2EB2", "emitente": "OUTRO"})
    esperar(st == 200, f"B2: NF só fiscal {st} {d}")
    out = {"corte_itu": corte["id"], "sa": corte["sa_id"]}
    if lote_rj is not None:      # P26 opção A: a parte do RJ da mesma OP (só prévia, nada gravado)
        c.entrar(u["itu"])
        corpo = {"op": op, "liga": lote_rj.item.liga.codigo, "medida": medida_para(lote_rj),
                 "itens": [{"lote_id": lote_rj.id, "modo": "CORTAR_RJ", "quantidade": 1}], "enviar": True}
        com = _codigos(c, "/api/solicitacoes/validar", {**corpo, "consumo_misto": True})
        sem = _codigos(c, "/api/solicitacoes/validar", corpo)
        esperar("OP_DUPLICADA" not in com, f"B2: consumo misto marcado ainda avisa OP_DUPLICADA ({com})")
        esperar("OP_DUPLICADA" in sem, f"B2: solicitação sem a marca deveria avisar OP_DUPLICADA ({sem})")
        out["consumo_misto"] = "OK: com a marca sem OP_DUPLICADA; sem a marca com OP_DUPLICADA"
    return out


def _codigos(c: Cliente, url: str, corpo: dict) -> list[str]:
    st, v = c.req("POST", url, corpo)
    esperar(st == 200, f"{url}: {st} {v}")
    return [o["codigo"].split("#")[0] for o in v.get("ocorrencias", [])]


def caminho_c(c: Cliente, u: dict, lote, op: int) -> dict:
    c.entrar(u["itu"])
    corte = gravar(c, "/api/cortes-itu/validar", "/api/cortes-itu",
                   {"op": op, "lote_id": lote.id, "consumo_kg": 10, "sobra_kg": 4, "sobra_na_bitola": False,
                    "peso_usado_kg": 15, "pecas": 1, "observacao": "TESTE E2E caminho C"})
    esperar(bool(corte.get("instrucao_mega")), "C: faltou a instrução 'Fazer no Mega'")
    esperar(not corte.get("sa_id"), "C: material Mega não gera SA")
    return {"corte_itu": corte["id"], "instrucao_mega": corte["instrucao_mega"]}


def caminho_d(c: Cliente, u: dict, liga: str) -> dict:
    c.entrar(u["rj"])
    numero = f"E2E{int(time.time()) % 100000}"
    d = gravar(c, "/api/entradas-nf/validar", "/api/entradas-nf",
               {"numero": numero, "data": date.today().isoformat(), "fornecedor": "TESTE E2E", "conteiner": "E2ETESTE",
                "itens": [{"liga": liga, "formato": "RETANGULAR", "espessura": 50, "largura": 610, "pecas": 1,
                           "peso_kg": 100, "descricao_nf": "TESTE E2E caminho D"}]})
    esperar(len(d["itens"]) == 1, "D: entrada deveria criar 1 lote")
    st, lote = c.req("GET", f"/api/lotes/{d['itens'][0]['lote_id']}")
    esperar(st == 200 and lote["estoque"] == "RJ_NO_RIO" and lote["codigo_mega"] is None,
            f"D: lote do RJ deveria ficar sem código do Mega ({st} {lote})")
    st, v = c.req("POST", "/api/entradas-nf/validar", {"numero": numero, "data": date.today().isoformat(),
                                                       "fornecedor": "TESTE E2E", "conteiner": "E2ETESTE",
                                                       "itens": [{"liga": liga, "formato": "RETANGULAR",
                                                                  "espessura": 50, "largura": 610, "peso_kg": 1}]})
    esperar("NF_DUPLICADA" in [o["codigo"] for o in v["ocorrencias"]], "D: NF repetida deveria ser bloqueada")
    return {"entrada": d["id"], "lote": d["itens"][0]["lote_id"]}


def _cop_fechado(c: Cliente, sol_id: int, numero: int) -> int:
    st, prontos = c.req("GET", "/api/cops/cortes-prontos")
    libs = [p["liberacao_id"] for p in prontos if p["solicitacao_id"] == sol_id]
    esperar(libs, f"corte da solicitação {sol_id} não apareceu em cortes prontos")
    st, cop = c.req("POST", "/api/cops", {"numero": numero, "observacao": "TESTE E2E"})
    esperar(st == 201, f"novo COP {st} {cop}")
    c.req("POST", f"/api/cops/{cop['id']}/itens", {"liberacao_ids": libs})
    st, d = c.req("POST", f"/api/cops/{cop['id']}/fechar")
    esperar(st == 200 and d["situacao"] == "FECHADO", f"fechar COP {st} {d}")
    return cop["id"]


def _sa_confirmar(c: Cliente, u: dict, op: int, mega: MegaE2E, sa_id: int | None = None) -> None:
    c.entrar(u["itu"])
    st, fila = c.req("GET", f"/api/sas?op={op}")
    linhas = [s for s in fila["itens"] if s["situacao"] != "CONFIRMADO" and (sa_id is None or s["id"] == sa_id)]
    esperar(linhas, f"SA da OP {op} não apareceu na fila")
    for s in linhas:
        codigo = s["sa_codigo"] or s["sa_codigo_sugerido"]
        esperar(codigo, f"OP {op}: sem código de SA sugerido (estrutura da OP nem histórico)")
        mega.simular.add(codigo)
        d = gravar(c, f"/api/sas/{s['id']}/codigo/validar", f"/api/sas/{s['id']}/codigo", {"sa_codigo": codigo})
        esperar(d["situacao"] == "CONFIRMADO", f"SA {codigo} não confirmou: {d['situacao']}")


def _receber(c: Cliente, u: dict, cop_id: int) -> None:
    c.entrar(u["itu"])
    st, cop = c.req("GET", f"/api/cops/{cop_id}")
    itens = [{"cop_item_id": i["id"], "peso_conferido_kg": i["peso_kg"]} for i in cop["itens"]]
    gravar(c, f"/api/cops/{cop_id}/receber/validar", f"/api/cops/{cop_id}/receber", {"itens": itens})


def _situacao(c: Cliente, u: dict, sol_id: int) -> str:
    c.entrar(u["itu"])
    return c.req("GET", f"/api/solicitacoes/{sol_id}")[1]["situacao"]


def conferir_saldos(db) -> dict:
    from sqlalchemy import text
    neg = db.execute(text("SELECT count(*) FROM lote WHERE saldo_kg < 0")).scalar()
    dif = db.execute(text("""
        SELECT l.codigo, l.saldo_kg, COALESCE(SUM(m.kg), 0) AS soma
          FROM lote l LEFT JOIN movimento m ON m.lote_id = l.id
         GROUP BY l.id, l.codigo, l.saldo_kg HAVING abs(l.saldo_kg - COALESCE(SUM(m.kg), 0)) > 0.001""")).all()
    # spec v3.7 §1.4: lote do RJ (no Rio ou em Itu) não tem código do Mega
    rj_cod = db.execute(text("SELECT count(*) FROM lote l JOIN item_mp i ON i.id = l.item_mp_id "
                             "WHERE l.planta_fiscal = 'RJ' AND i.codigo_mega IS NOT NULL")).scalar()
    return {"negativos": neg, "saldo_diferente_da_soma": [tuple(map(str, r)) for r in dif[:20]],
            "qtd_diferentes": len(dif), "lotes_rj_com_codigo_mega": rj_cod}


# ---------------------------------------------------------------- orquestração

def executar(app, sessao, gateway, ops_informadas: list[int] | None = None) -> dict:
    from app.integrations.mega import fabrica
    mega = MegaE2E(gateway)
    fabrica.definir(mega)
    rel: dict[str, Any] = {"inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "caminhos": {}}
    with sessao() as db:
        u = preparar_usuarios(db)
        la = escolher_lote(db, "RJ", "RJ", 300, set())
        lb = escolher_lote(db, "RJ", "RJ", 300, {la.id})
        lb2 = escolher_lote(db, "RJ", "ITU", 30, set(), retangular=False)
        lc = escolher_lote(db, "ITU", "ITU", 30, set(), retangular=False, codigo_mega=True)
        for lote in (la, lb):
            _ = lote.item.liga.codigo
        ops = escolher_ops(db, gateway, 4, ops_informadas or [])
        base_cop = 90000 + int(time.time()) % 9000
        rel["dados"] = {"ops": ops, "lotes": {"A": la.codigo, "B": lb.codigo, "B2": lb2.codigo, "C": lc.codigo}}
        db.expunge_all()
    c = Cliente(app)
    passos = [("A", lambda: caminho_a(c, u, la, ops[0], mega, base_cop)),
              ("B", lambda: caminho_b(c, u, lb, ops[1], mega, base_cop + 1)),
              ("B2", lambda: caminho_b2(c, u, lb2, ops[2], mega, la)),
              ("C", lambda: caminho_c(c, u, lc, ops[3])),
              ("D", lambda: caminho_d(c, u, la.item.liga.codigo))]
    for nome, f in passos:
        t = time.perf_counter()
        try:
            rel["caminhos"][nome] = {"ok": True, **f(), "segundos": round(time.perf_counter() - t, 2)}
        except Exception as e:  # noqa: BLE001 — registra e segue para o próximo caminho
            rel["caminhos"][nome] = {"ok": False, "erro": f"{type(e).__name__}: {e}"}
    for nome, esperado in (("A", "CONCLUIDA"), ("B", "CONCLUIDA")):
        r = rel["caminhos"][nome]
        if r.get("ok") and r.get("situacao_final") != esperado:
            r.update(ok=False, erro=f"situação final {r.get('situacao_final')} (esperado {esperado})")
    with sessao() as db:
        rel["conferencia"] = conferir_saldos(db)
    rel["sa_confirmacao_simulada"] = sorted(set(mega.simulados))
    rel["ok"] = all(r.get("ok") for r in rel["caminhos"].values()) and rel["conferencia"]["negativos"] == 0 \
        and rel["conferencia"]["qtd_diferentes"] == 0 and rel["conferencia"]["lotes_rj_com_codigo_mega"] == 0
    return rel


def main(argv: list[str]) -> int:
    url = os.environ.get("DATABASE_URL", "")
    if not url.split("?")[0].endswith("_e2e"):
        print("Recusado: o ponta a ponta só roda num banco cujo nome termina em _e2e (cópia da homologação).")
        return 2
    from app.core.db import SessionLocal
    from app.integrations.mega import fabrica
    from app.main import app
    ops = [int(a) for a in argv if a.isdigit()]
    rel = executar(app, SessionLocal, fabrica.obter(), ops)
    print(json.dumps(rel, ensure_ascii=False, indent=2, default=str))
    return 0 if rel["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
