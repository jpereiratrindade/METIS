#!/usr/bin/env python3
"""Testes unitários do contrato temporal INMET, sem rede ou banco."""

import importlib.util
import os
import unittest

CAMINHO = os.path.join(os.path.dirname(__file__), "..", "scripts", "conectores", "conector_inmet.py")
SPEC = importlib.util.spec_from_file_location("conector_inmet", CAMINHO)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class TestInmetTemporal(unittest.TestCase):
    def test_fingerprint_independe_da_ordem_das_chaves(self):
        aviso_a = {"codigo": "X", "inicio": "2026-11-04T10:00:00Z",
                   "fim": "2026-11-04T12:00:00Z", "descricao": "Chuva", "severidade": "Perigo"}
        aviso_b = dict(reversed(list(aviso_a.items())))
        self.assertEqual(MOD._fingerprint(MOD._snapshot(aviso_a)),
                         MOD._fingerprint(MOD._snapshot(aviso_b)))

    def test_alteracao_cria_fingerprint_distinto(self):
        base = {"inicio": "2026-11-04T10:00:00Z", "fim": "2026-11-04T12:00:00Z",
                "descricao": "Chuva", "severidade": "Perigo"}
        alterado = dict(base, severidade="Grande Perigo")
        self.assertNotEqual(MOD._fingerprint(MOD._snapshot(base)),
                            MOD._fingerprint(MOD._snapshot(alterado)))

    def test_cancelamento_somente_quando_explicito(self):
        self.assertEqual(MOD._snapshot({})["situacao_origem"], "ativo")
        self.assertEqual(MOD._snapshot({"encerrado": False})["situacao_origem"], "ativo")
        self.assertEqual(MOD._snapshot({"encerrado": True})["situacao_origem"], "cancelado")

    def test_geocodes_normalizados(self):
        self.assertEqual(MOD._normalizar_geocodes(["4300001", "4300002"]), "4300001,4300002")
        self.assertEqual(MOD._normalizar_geocodes("4300001; 4300002"), "4300001,4300002")


if __name__ == "__main__":
    unittest.main()
