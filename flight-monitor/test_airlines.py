from __future__ import annotations

import unittest

from airlines import parse_azul, parse_gol, parse_latam


class AirlineParserTests(unittest.TestCase):
    def test_gol_offer(self):
        html = """
        <div>Origem FOR - Fortaleza Destino CGH - São Paulo - Congonhas
        trechos a partir de taxas de embarque inclusas R$ 583,47 Comprar passagem</div>
        """
        rows = parse_gol(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["origin"], "FOR")
        self.assertEqual(rows[0]["destination"], "CGH")
        self.assertEqual(rows[0]["price"], 583.47)

    def test_azul_round_trip(self):
        html = """
        <div>Campinas (VCP) Para Orlando (MCO) 26/02/2027 - 17/03/2027
        Ida e volta / Econômica A partir de R$4.628,63* Visto: 18 minutos atrás</div>
        """
        rows = parse_azul(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["origin"], "VCP")
        self.assertEqual(rows[0]["destination"], "MCO")
        self.assertEqual(rows[0]["return_date"], "2027-03-17")
        self.assertEqual(rows[0]["trip_mode"], "round_trip")

    def test_latam_offer(self):
        html = """
        <div>Origem: São Paulo - Todos os aeroportos Destinos Todos os destinos</div>
        <div>Voo direto Viaja em Out Uberlândia (UDI) Somente ida 07/10/26 Economy
        Preço a partir de BRL 220,65 Taxas incluídas</div>
        """
        rows = parse_latam(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["origin"], "SAO")
        self.assertEqual(rows[0]["origin_candidates"], ["GRU", "CGH"])
        self.assertEqual(rows[0]["destination"], "UDI")
        self.assertEqual(rows[0]["price"], 220.65)


if __name__ == "__main__":
    unittest.main()
