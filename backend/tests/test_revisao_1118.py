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
