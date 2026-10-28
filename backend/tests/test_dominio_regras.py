import unittest
from datetime import date

from app.domain import regras
from app.domain.validacao import Nivel


def codigos(r):
    return [o.codigo for o in r.ocorrencias]


class TestSaldo(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(codigos(regras.validar_saldo(100, 0, 50)), [])

    def test_insuficiente_bloqueia(self):
        r = regras.validar_saldo(100, 0, 100.5)
        self.assertEqual(r.erros[0].codigo, "SALDO_INSUFICIENTE")
        self.assertFalse(r.pode_gravar({"SALDO_INSUFICIENTE": "qualquer coisa"}))

    def test_invade_reserva_exige_ciencia(self):
        r = regras.validar_saldo(100, 60, 50)
        self.assertEqual(codigos(r), ["USA_SALDO_RESERVADO"])
        self.assertFalse(r.pode_gravar())
        self.assertTrue(r.pode_gravar({"USA_SALDO_RESERVADO": "OP urgente, autorizado"}))

    def test_peso_zero(self):
        self.assertEqual(regras.validar_saldo(100, 0, 0).erros[0].codigo, "PESO_INVALIDO")


class TestTolerancia20(unittest.TestCase):
    def test_exatamente_20_passa(self):
        self.assertEqual(codigos(regras.validar_peso_real(100, 120)), [])

    def test_acima_20_exige_ciencia(self):
        r = regras.validar_peso_real(100, 120.1)
        self.assertEqual(r.ocorrencias[0].nivel, Nivel.CIENCIA)
        self.assertFalse(r.pode_gravar())
        self.assertFalse(r.pode_gravar({"EXCESSO_TOLERANCIA": "  "}), "justificativa vazia não vale")
        self.assertTrue(r.pode_gravar({"EXCESSO_TOLERANCIA": "Só havia bitola 50x610, OP urgente"}))

    def test_abaixo_20_so_alerta(self):
        r = regras.validar_peso_real(100, 70)
        self.assertEqual(r.ocorrencias[0].nivel, Nivel.ALERTA)
        self.assertTrue(r.pode_gravar())

    def test_tolerancia_configuravel(self):
        self.assertEqual(codigos(regras.validar_peso_real(100, 115, tolerancia_excesso_pct=10)),
                         ["EXCESSO_TOLERANCIA"])

    def test_sobremetal(self):
        self.assertEqual(codigos(regras.validar_sobremetal(119, 100)), [])
        self.assertEqual(codigos(regras.validar_sobremetal(150, 100)), ["SOBREMETAL_ACIMA_TOLERANCIA"])


class TestBitola(unittest.TestCase):
    def test_bitola_comporta(self):
        # A8 14x123 para peça 12,7 x 122
        self.assertEqual(codigos(regras.validar_bitola(14, 123, None, 12.7, 122, None)), [])

    def test_bitola_menor(self):
        self.assertEqual(codigos(regras.validar_bitola(14, 102, None, 12, 120, None)), ["BITOLA_MENOR_QUE_PECA"])

    def test_orientacao_nao_importa(self):
        self.assertEqual(codigos(regras.validar_bitola(610, 35, None, 32, 300, None)), [])

    def test_redondo(self):
        self.assertEqual(codigos(regras.validar_bitola(None, None, 112, 110, 22.5, None)), [])
        self.assertEqual(codigos(regras.validar_bitola(None, None, 101, None, None, 105)), ["BITOLA_MENOR_QUE_PECA"])


class TestPerdaCorte(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(codigos(regras.validar_perda_corte(1000, 400, 599.5, 0.5)), [])

    def test_soma_maior_que_lote(self):
        self.assertEqual(codigos(regras.validar_perda_corte(1000, 600, 401, 0.5)), ["SOMA_MAIOR_QUE_LOTE"])

    def test_perda_alta(self):
        self.assertEqual(codigos(regras.validar_perda_corte(1000, 400, 300, 0.5)), ["PERDA_CORTE_ALTA"])


class TestDestinacaoEOP(unittest.TestCase):
    def test_destinacao_vigente_exige_ciencia(self):
        d = [regras.Destinacao("RESTRICAO", "Não usar para guilhotinas"),
             regras.Destinacao("RESERVA", "CPR", validade=date(2020, 1, 1))]
        r = regras.validar_destinacoes(d, hoje=date(2026, 10, 28))
        self.assertEqual(len(r.ciencias), 1)

    def test_op(self):
        self.assertEqual(codigos(regras.validar_op(False, False, False)), ["OP_INEXISTENTE"])
        self.assertEqual(codigos(regras.validar_op(True, False, False)), ["OP_ENCERRADA"])
        self.assertEqual(codigos(regras.validar_op(True, True, True)), ["OP_DUPLICADA"])


if __name__ == "__main__":
    unittest.main()
