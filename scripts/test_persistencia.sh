#!/usr/bin/env bash
# MÉTIS — Executar Testes Automatizados de Persistência Científica Versionada
set -euo pipefail

METIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$METIS_DIR"

echo "=== MÉTIS: Executando Suíte de Testes de Persistência ==="
python3 -m unittest tests/test_persistencia.py -v
