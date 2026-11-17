"""Ferramenta de teste "Confirmar SA (teste)" (contrato §7.1): só com MODO_TESTE=true e APP_ENV diferente de prod."""
import pytest

from tests.fluxo_util import catalogo_e_lotes, corpo_solicitacao, criar_usuarios, entrar, mega_falso

pytest.importorskip("fastapi")


@pytest.fixture()
def amb(client):
    u = criar_usuarios(client)
    ids = catalogo_e_lotes()
    fab = mega_falso()
    yield client, u, ids, fab
    fab.definir(None)


@pytest.fixture()
def modo(monkeypatch):
    from app.core.config import get_config
    cfg = get_config()

    def ligar(valor: bool = True, ambiente: str | None = None):
        monkeypatch.setattr(cfg, "modo_teste", valor)
        if ambiente:     # APP_ENV=prod também deixa o cookie "secure": trocar só depois do login
            monkeypatch.setattr(cfg, "app_env", ambiente)
    return ligar


def _cop_fechado(client, u, ids):
    """Caminho A até o COP fechado: devolve (cop_id, solicitacao_id, linha do SA)."""
    h = entrar(client, u["itu"])
    s = client.post("/api/solicitacoes", json=corpo_solicitacao(ids["l33"]), headers=h).json()["solicitacoes"][0]
    h = entrar(client, u["rj"])
    r = client.post(f"/api/solicitacoes/{s['id']}/corte", headers=h,
                    json={"linhas": [{"lote_id": ids["l33"], "pecas": 12, "peso_real_kg": 85}],
                          "confirmacoes": {"EXCESSO_TOLERANCIA": "Desvio de serra na barra"}})
    assert r.status_code == 201, r.text
    lib = client.get("/api/cops/cortes-prontos").json()[0]["liberacao_id"]
    cop = client.post("/api/cops", json={"numero": 801}, headers=h).json()
    client.post(f"/api/cops/{cop['id']}/itens", json={"liberacao_ids": [lib]}, headers=h)
    client.post(f"/api/cops/{cop['id']}/fechar", headers=h)
    h = entrar(client, u["itu"])
    return cop["id"], s["id"], client.get("/api/sas").json()["itens"][0]


def test_modo_teste_desligado_rota_nao_existe(amb, modo):
    client, u, ids, _ = amb
    modo(False)
    _, _, sa = _cop_fechado(client, u, ids)
    assert client.get("/api/saude").json() == {"status": "ok", "modo_teste": False}
    h = entrar(client, u["admin"])
    assert client.get("/api/auth/eu").json()["modo_teste"] is False
    r = client.post(f"/api/sas/{sa['id']}/confirmar-teste", json={"sa_codigo": 50001}, headers=h)
    assert r.status_code == 404
    assert client.get(f"/api/sas/{sa['id']}").json()["situacao"] == "PENDENTE"
    client.post("/api/auth/logout", headers=h)
    client.cookies.clear()
    assert client.post(f"/api/sas/{sa['id']}/confirmar-teste", json={}).status_code == 404   # 404 antes do login
    assert "/api/sas/{sa_id}/confirmar-teste" not in client.get("/api/openapi.json").json()["paths"]


def test_modo_teste_nunca_liga_em_producao(amb, modo):
    client, u, ids, _ = amb
    modo(True)
    _, _, sa = _cop_fechado(client, u, ids)
    h = entrar(client, u["admin"])
    modo(True, "prod")
    assert client.get("/api/saude").json()["modo_teste"] is False
    assert client.get("/api/auth/eu").json()["modo_teste"] is False
    assert client.post(f"/api/sas/{sa['id']}/confirmar-teste", json={"sa_codigo": 50001},
                       headers=h).status_code == 404


def test_confirmar_sa_teste_libera_o_envio_do_cop(amb, modo):
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import Auditoria
    client, u, ids, _ = amb
    modo(True)
    cop_id, sid, sa = _cop_fechado(client, u, ids)
    assert client.get("/api/saude").json()["modo_teste"] is True

    # só ADMIN; outro perfil vê o modo de teste mas recebe 403
    h = entrar(client, u["itu"])
    assert client.get("/api/auth/eu").json()["modo_teste"] is True
    assert client.post(f"/api/sas/{sa['id']}/confirmar-teste", json={"sa_codigo": 50001},
                       headers=h).status_code == 403

    h = entrar(client, u["admin"])
    r = client.post(f"/api/sas/{sa['id']}/confirmar-teste", json={}, headers=h)
    assert r.status_code == 400 and "código do SA" in r.json()["detail"]      # linha nova ainda sem código
    r = client.post(f"/api/sas/{sa['id']}/confirmar-teste", json={"sa_codigo": 50001}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["situacao"] == "CONFIRMADO" and r.json()["sa_codigo"] == 50001
    assert r.json()["confirmacao_teste"] is True
    assert client.post(f"/api/sas/{sa['id']}/confirmar-teste", json={}, headers=h).status_code == 400
    assert client.get(f"/api/solicitacoes/{sid}").json()["situacao"] == "SA_PRONTO"
    with SessionLocal() as db:
        aud = db.scalar(select(Auditoria).where(Auditoria.acao == "SA_CONFIRMADO_TESTE"))
        assert aud.entidade_id == str(sa["id"]) and aud.usuario_id is not None
        assert aud.depois["confirmacao"] == "confirmação de teste" and aud.depois["usuario"] == "admin"
        assert aud.antes["situacao"] == "PENDENTE"

    # RJ segue o fluxo normal: aviso, NF e envio
    h = entrar(client, u["rj"])
    assert "COP_SA_PRONTO" in [n["tipo"] for n in client.get("/api/notificacoes").json()["itens"]]
    client.post(f"/api/cops/{cop_id}/nf", json={"numero": "556", "emitente": "FIO_CERTO"}, headers=h)
    r = client.post(f"/api/cops/{cop_id}/enviar", headers=h)
    assert r.status_code == 200 and r.json()["situacao"] == "ENVIADO"


def test_confirmar_sa_teste_aguardando_mega_usa_o_codigo_informado(amb, modo):
    client, u, ids, _ = amb
    modo(True)
    _, _, sa = _cop_fechado(client, u, ids)
    h = entrar(client, u["itu"])
    r = client.post(f"/api/sas/{sa['id']}/codigo", json={"sa_codigo": 50007}, headers=h)
    assert r.json()["situacao"] == "AGUARDANDO_MEGA"                          # Mega falso sem a carga do SA
    h = entrar(client, u["admin"])
    r = client.post(f"/api/sas/{sa['id']}/confirmar-teste", headers=h)       # sem corpo
    assert r.status_code == 200, r.text
    assert r.json()["situacao"] == "CONFIRMADO" and r.json()["sa_codigo"] == 50007
