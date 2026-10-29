import unittest

from app.domain import regras
from app.domain.formato import kg_br, numero_br, pct_br


class TestFormatoBR(unittest.TestCase):
    def test_numeros(self):
        self.assertEqual(kg_br(90), "90,0 kg")
        self.assertEqual(kg_br(1234.56), "1.234,6 kg")
        self.assertEqual(kg_br(0.503, 2), "0,50 kg")
        self.assertEqual(pct_br(8.123, 1), "8,1 %")
        self.assertEqual(pct_br(5), "5 %")
        self.assertEqual(numero_br(1234567.891, 3), "1.234.567,891")

    def test_mensagem_da_regra(self):
        m = regras.validar_peso_real(83.3, 90).ocorrencias[0].mensagem
        self.assertIn("90,0 kg", m)
        self.assertIn("8,0 %", m)
        self.assertIn("(83,3 kg)", m)
        self.assertIn("Limite: 5 %", m)
        self.assertNotRegex(m, r"\d\.\d")


if __name__ == "__main__":
    unittest.main()
