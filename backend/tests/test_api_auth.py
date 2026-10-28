import pytest

from tests.conftest import login, preparar_admin

pytest.importorskip("fastapi")


def test_saude(client):
    assert client.get("/api/saude").json() == {"status": "ok"}


def test_login_errado_mensagem_generica(client):
    r1 = login(client, "admin", "errada")
    r2 = login(client, "naoexiste", "errada")
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]


def test_bloqueio_apos_tentativas(client):
    for _ in range(3):
        assert login(client, "admin", "errada").status_code == 401
    r = login(client)  # senha certa, mas bloqueado
    assert r.status_code == 401
    assert "bloqueado" in r.json()["detail"]


def test_troca_senha_obrigatoria(client):
    r = login(client)
    h = {"X-CSRF-Token": r.json()["csrf"]}
    assert r.json()["usuario"]["trocar_senha"] is True
    assert client.get("/api/painel/resumo").status_code == 403
    fraca = client.post("/api/auth/trocar-senha", json={"senha_atual": "SenhaInicial123", "nova_senha": "curta"},
                        headers=h)
    assert fraca.status_code == 400
    ok = client.post("/api/auth/trocar-senha", json={"senha_atual": "SenhaInicial123", "nova_senha": "NovaSenha2026x"},
                     headers=h)
    assert ok.status_code == 204
    assert client.get("/api/painel/resumo").status_code == 200


def test_csrf_obrigatorio(client):
    login(client)
    r = client.post("/api/auth/trocar-senha", json={"senha_atual": "SenhaInicial123", "nova_senha": "NovaSenha2026x"})
    assert r.status_code == 403


def test_sem_sessao(client):
    assert client.get("/api/auth/eu").status_code == 401


def test_logout_invalida_sessao(client):
    h = preparar_admin(client)
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.get("/api/auth/eu").status_code == 401


def test_admin_cria_usuario_e_perfil_restringe(client):
    h = preparar_admin(client)
    r = client.post("/api/usuarios", json={"login": "fabiano.camargo", "nome": "Fabiano Camargo", "perfil": "ESTOQUE"},
                    headers=h)
    assert r.status_code == 201, r.text
    temp = r.json()["senha_temporaria"]
    client.post("/api/auth/logout", headers=h)

    r = login(client, "fabiano.camargo", temp)
    assert r.status_code == 200
    h2 = {"X-CSRF-Token": r.json()["csrf"]}
    client.post("/api/auth/trocar-senha", json={"senha_atual": temp, "nova_senha": "Fabiano2026ok"}, headers=h2)
    assert client.get("/api/usuarios").status_code == 403       # não é admin
    assert client.get("/api/painel/resumo").status_code == 200


def test_calculadora_e_regra_20(client):
    h = preparar_admin(client)
    r = client.post("/api/calculadora/peso", json={"formato": "RETANGULAR", "densidade": 7.85, "espessura": 47,
                                                   "largura": 130, "comprimento": 2110, "quantidade": 62}, headers=h)
    assert r.status_code == 200
    assert abs(r.json()["peso_total_kg"] - 6274.585) < 0.01
    r = client.post("/api/calculadora/validar-peso-real", json={"previsto_kg": 100, "real_kg": 130}, headers=h)
    assert r.json()["ocorrencias"][0]["codigo"] == "EXCESSO_TOLERANCIA"
