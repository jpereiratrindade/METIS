#!/usr/bin/env python3
"""Testes unitários e de integração do conector SIMAGRO-RS."""

import os
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts/conectores"))

from conector_simagro import parsear_alertas_simagro, parsear_mapa_municipios_geojson  # noqa: E402
from metis_ops import op_municipality_dossier  # noqa: E402

DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")


class TestConectorSimagro(unittest.TestCase):
    def test_parsear_mapa_municipios_geojson(self):
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {"properties": {"id_ponto": 4604, "City": 4300034, "nome": "ACEGUA", "region_id": 10}},
                {"properties": {"id_ponto": 9999, "City": "INVALID", "nome": "X"}},
            ],
        }
        regs = parsear_mapa_municipios_geojson(geojson)
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs[0]["id_ponto"], 4604)
        self.assertEqual(regs[0]["codigo_ibge"], "4300034")
        self.assertEqual(regs[0]["region_id"], 10)

    def test_parsear_alertas_simagro_valido_e_filtro_ibge(self):
        mapa = {4604: "4300034"}
        payload = [
            {
                "id_pto": 4604,
                "PREC": 0.0,
                "ESTIAGEM": 1.0,
                "ESTIAGEM_AGRICOLA": 2.0,
                "GEADA": 0.0,
                "T_ACIMA": 3.0,
                "T_ABAIXO": 0.0,
                "ITU": 1.0,
                "CI_OVINO": 0.0,
            },
            {
                "id_pto": 999999,
                "PREC": 1.0,
            },
        ]
        validos, total = parsear_alertas_simagro(payload, mapa)
        self.assertEqual(total, 2)
        self.assertEqual(len(validos), 1)
        self.assertEqual(validos[0]["codigo_ibge"], "4300034")
        self.assertEqual(validos[0]["estiagem_agricola"], 2)
        self.assertEqual(validos[0]["t_acima"], 3)

    def test_parsear_alertas_simagro_rejeita_nivel_fora_faixa(self):
        mapa = {4604: "4300034"}
        with self.assertRaises(ValueError):
            parsear_alertas_simagro([{"id_pto": 4604, "PREC": 5.0}], mapa)

    def test_op_municipality_dossier_inclui_simagro(self):
        res = op_municipality_dossier(DEFAULT_DB_URL, {"codigo_ibge": "4300034"}, {})
        self.assertIn("simagro_alertas", res)
        self.assertGreaterEqual(len(res["simagro_alertas"]), 1)
        janelas = {item["janela"] for item in res["simagro_alertas"]}
        self.assertIn("7d", janelas)


if __name__ == "__main__":
    unittest.main()
