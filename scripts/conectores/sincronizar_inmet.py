#!/usr/bin/env python3
"""Sincroniza somente INMET, recompila export público e episódios."""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

from conector_inmet import DEFAULT_DB_URL, coletar_avisos_inmet
from sincronizar_evidencias import sincronizar_todas_evidencias


def sincronizar_inmet(db_url=DEFAULT_DB_URL, acionamento="manual"):
    resultado = coletar_avisos_inmet(db_url, acionamento=acionamento)
    if resultado.get("erro") or resultado.get("conflito"):
        return resultado
    sincronizar_todas_evidencias(db_url, executar_coleta=False)
    return resultado


if __name__ == "__main__":
    db = next((arg for arg in sys.argv[1:] if not arg.startswith("--")), DEFAULT_DB_URL)
    resultado = sincronizar_inmet(db, "agendado" if "--scheduled" in sys.argv else "manual")
    sys.exit(1 if resultado.get("erro") else (2 if resultado.get("conflito") else 0))
