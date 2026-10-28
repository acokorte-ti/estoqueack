import unittest

from app.domain.peso import (Secao, densidade_da_liga, peso_anel, peso_redondo, peso_reto,
                             perda_corte_esperada)


class TestPeso(unittest.TestCase):
    def test_reto_bate_com_planilha_atual(self):
        # Planilha "calculo de peso": 2110 × 130 × 47 × 7,85 → 101,203 kg
        self.assertAlmostEqual(peso_reto(47, 130, 2110, 7.85), 101.203, places=3)

    def test_reto_quantidade(self):
        self.assertAlmostEqual(peso_reto(47, 130, 2110, 7.85, quantidade=62), 6274.585, places=2)

    def test_redondo(self):
        # Ø100 × 1000 mm, 7,85 → 61,654 kg
        self.assertAlmostEqual(peso_redondo(100, 1000, 7.85), 61.654, places=3)

    def test_anel_bate_com_planilha(self):
        # Planilha: DE 409, DI vazio, E 53 → 54,66 kg (com π=3,1416 na planilha)
        self.assertAlmostEqual(peso_anel(409, 0, 53, 7.85), 54.66, delta=0.01)

    def test_anel_interno_invalido(self):
        with self.assertRaises(ValueError):
            peso_anel(100, 120, 10)

    def test_medida_invalida(self):
        with self.assertRaises(ValueError):
            peso_reto(0, 10, 10)

    def test_perda_corte_exemplo_documentado(self):
        self.assertAlmostEqual(perda_corte_esperada(Secao(35, 610), 3, 7.85), 0.503, places=3)

    def test_densidade(self):
        self.assertEqual(densidade_da_liga("h13"), 7.80)
        self.assertEqual(densidade_da_liga("XPTO"), 7.85)
        self.assertEqual(densidade_da_liga("H13", {"H13": 7.81}), 7.81)
        self.assertEqual(densidade_da_liga(None), 7.85)


if __name__ == "__main__":
    unittest.main()
