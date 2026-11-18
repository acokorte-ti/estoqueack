"""Revisão de código de 2026-11-18: correções sem mudança de regra de negócio.

(A concorrência — lote travado antes de validar — está em tests/test_postgres.py, que só roda no PostgreSQL.)"""
from app.domain import regras


def test_disponivel_nunca_negativo_quando_a_reserva_antiga_passa_do_saldo():
    """Saldo 30 kg com reserva antiga de 50 kg (feita antes de um ajuste): o lote inteiro invade 30 kg, não 50."""
    r = regras.validar_saldo(30, 50, 35, peso_peca_kg=25, lote="L-TESTE")
    oc = {o.codigo: o for o in r.ocorrencias}
    assert "CONSUMO_LOTE_INTEIRO" in oc and "USA_SALDO_RESERVADO" in oc
    assert oc["USA_SALDO_RESERVADO"].dados["disponivel_kg"] == 0
    assert "invade 30,0 kg" in oc["USA_SALDO_RESERVADO"].mensagem


def test_disponivel_normal_nao_muda():
    """Saldo 100 kg, 40 reservados para outro destino: o livre continua 60 kg (comportamento de antes)."""
    r = regras.validar_saldo(100, 40, 110, peso_peca_kg=90)
    oc = {o.codigo: o for o in r.ocorrencias}
    assert oc["USA_SALDO_RESERVADO"].dados["disponivel_kg"] == 60


def test_senha_nao_pode_conter_o_login():
    """Eduardo, 2026-11-18: além do tamanho mínimo, a senha não pode conter o login (sem diferença de maiúscula)."""
    from app.core.seguranca import problemas_senha
    assert problemas_senha("joao.silva2026", "joao.silva", 6) == ["A senha não pode conter o login."]
    assert problemas_senha("XJOAO.SILVAx", "joao.silva", 6) == ["A senha não pode conter o login."]
    assert problemas_senha("joao.s", "joao.silva", 6) == []          # pedaço do login não basta para barrar
    assert problemas_senha("123456", "joao.silva", 6) == []          # continua podendo ser só números
    assert problemas_senha("123", "joao.silva", 6) == ["A senha deve ter pelo menos 6 caracteres."]


def test_trocar_senha_recusa_senha_com_o_login(client):
    import pytest as _pytest
    _pytest.importorskip("fastapi")
    from tests.conftest import login
    r = login(client)
    h = {"X-CSRF-Token": r.json()["csrf"]}
    login_admin = r.json()["usuario"]["login"]
    ruim = client.post("/api/auth/trocar-senha", headers=h,
                       json={"senha_atual": "SenhaInicial123", "nova_senha": f"{login_admin.upper()}2026"})
    assert ruim.status_code == 400 and "não pode conter o login" in ruim.json()["detail"]
    ok = client.post("/api/auth/trocar-senha", headers=h,
                     json={"senha_atual": "SenhaInicial123", "nova_senha": "NovaSenha2026x"})
    assert ok.status_code == 204
