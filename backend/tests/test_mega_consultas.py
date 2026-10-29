"""Garante que as consultas do Mega usam bind variables e o esquema/filial mapeados."""
from app.integrations.mega import consultas


def test_consultas_usam_esquema_e_binds():
    for nome in ("SALDOS_MP", "MOVIMENTOS_DESDE", "ORDEM_PRODUCAO", "BAIXAS_DA_OP", "BUSCAR_SA"):
        sql = getattr(consultas, nome)
        assert "ACOKORTE." in sql, nome
        assert ":" in sql, f"{nome} sem bind variable"


def test_baixa_da_op_filtra_tipo_requisicao():
    # MVT_ST_NUMDOC também guarda NF; sem o filtro de tipo, uma venda com o mesmo número viria junto
    assert "TPM_IN_CODIGO = 13" in consultas.BAIXAS_DA_OP


def test_mega_falso():
    from app.integrations.mega.gateway import MegaFalso, OrdemProducao
    m = MegaFalso(ops=[OrdemProducao(100508, 68092, "PARTE/ACESSORIO", None, "AB", None, 128)])
    assert m.ordem_producao(100508).quantidade == 128
    assert m.ordem_producao(1) is None
