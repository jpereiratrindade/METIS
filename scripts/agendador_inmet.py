#!/usr/bin/env python3
"""Agendador simples INMET. Intervalo configurável; uma execução por ciclo."""

import os
import signal
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "conectores"))
from sincronizar_inmet import sincronizar_inmet

INTERVALO = max(60, int(os.environ.get("METIS_INMET_INTERVAL_SECONDS", "900")))
ativo = True


def parar(_sinal, _frame):
    global ativo
    ativo = False


signal.signal(signal.SIGTERM, parar)
signal.signal(signal.SIGINT, parar)

if __name__ == "__main__":
    while ativo:
        inicio = time.monotonic()
        resultado = sincronizar_inmet(acionamento="agendado")
        if resultado.get("erro"):
            print(f"INMET agendado falhou: {resultado['erro']}", file=sys.stderr, flush=True)
        restante = INTERVALO - (time.monotonic() - inicio)
        limite = time.monotonic() + max(0, restante)
        while ativo and time.monotonic() < limite:
            time.sleep(min(1, limite - time.monotonic()))
