import unittest

from app.domain.lotes import LoteInfo, cadeia_origem, reto_por_origem, saldo
from app.domain.medidas import interpretar, normalizar_liga


class TestMedidas(unittest.TestCase):
    CASOS = {
        "IMP-H13 50X610MM": ("H13", "RETANGULAR", "50X610"),
        "H13 Ø66": ("H13", "REDONDO", "Ø66"),
        "CR8  13X510": ("CR8", "RETANGULAR", "13X510"),
        "IMP-Cr12MoV RED 54MM": ("CR12MOV", "REDONDO", "Ø54"),
        "CR12 MOV REDØ101": ("CR12MOV", "REDONDO", "Ø101"),
        "A8 MOD 21x204x1110 Múltiplo": ("A8MOD", "RETANGULAR", "21X204"),
        "D2 FLAT BAR 4,8X600 (MÚLTIPLO DE 2020MM)": ("D2", "RETANGULAR", "4.8X600"),
        "IMP-H13 RETO": ("H13", "RETO", "RETO"),
        "IMP-DIN 1.2746 66X133MM": ("1.2746", "RETANGULAR", "66X133"),
        "1.2746 154x64": ("1.2746", "RETANGULAR", "64X154"),
        "12360 21,5X212": ("1.2360", "RETANGULAR", "21.5X212"),
        "DC53-C 46X610": ("DC53", "RETANGULAR", "46X610"),
        "4140 Ø205": ("4140", "REDONDO", "Ø205"),
        "IMP-A8 5,50X315X4600MM": ("A8", "RETANGULAR", "5.5X315"),
    }

    def test_casos_reais(self):
        for desc, (liga, formato, bitola) in self.CASOS.items():
            with self.subTest(desc=desc):
                m = interpretar(desc)
                self.assertEqual((m.liga, m.formato, m.bitola), (liga, formato, bitola))

    def test_comprimento(self):
        self.assertEqual(interpretar("IMP-A8 5,50X315X4600MM").comprimento, 4600)

    def test_liga_nao_catalogada_vira_sugestao(self):
        # Ligas fora do catálogo viram sugestão para revisão na migração
        self.assertEqual(normalizar_liga("IMP-OH255 RED 322MM"), "OH255")
        self.assertEqual(normalizar_liga("45 C 1,2767 STEEL BARS 74X188"), "1.2767")
        self.assertIsNone(normalizar_liga(""))
        self.assertIsNone(normalizar_liga("50X610"))


class TestLotes(unittest.TestCase):
    def setUp(self):
        self.lotes = {
            1: LoteInfo(1, "CH11EA", "H13", "50X610", "ORIGINAL", None, 1948),
            2: LoteInfo(2, "CH11EA", "H13", "50X610", "SOBRA", 1, 300),
            3: LoteInfo(3, "CH11EA", "H13", "RETO", "RETO", 2, 177),
            4: LoteInfo(4, "CH30K", "H13", "35X610", "ORIGINAL", None, 0),
            5: LoteInfo(5, "CH30K", "H13", "RETO", "RETO", 4, 1500),
            6: LoteInfo(6, "CH31K", "D2", "RETO", "RETO", None, 80),
        }

    def test_saldo(self):
        self.assertEqual(saldo([5004, -2046, -1010]), 1948)

    def test_cadeia(self):
        self.assertEqual([l.id for l in cadeia_origem(3, self.lotes)], [3, 2, 1])

    def test_reto_por_origem(self):
        r = reto_por_origem(self.lotes, liga="H13")
        self.assertEqual(r, {("H13", "50X610", "CH11EA"): 177, ("H13", "35X610", "CH30K"): 1500})

    def test_ciclo(self):
        lotes = {1: LoteInfo(1, "X", "H13", "RETO", "RETO", 2, 1), 2: LoteInfo(2, "X", "H13", "RETO", "RETO", 1, 1)}
        with self.assertRaises(ValueError):
            cadeia_origem(1, lotes)


if __name__ == "__main__":
    unittest.main()
