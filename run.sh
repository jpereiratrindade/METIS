#!/usr/bin/env bash
# Ecossistema SisTer — MÉTIS Launcher Script
# Copyright (C) 2026 José Pedro Trindade
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ -f .env ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi

# Compilar binário C++ nativo se necessário
if [[ ! -f "build/resiliencia-rs" ]]; then
  echo "==> Compilando núcleo C++26 (MÉTIS)..."
  cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
  cmake --build build --parallel
fi

HOST="${METIS_HOST:-${HOST:-0.0.0.0}}"
PORT="${METIS_PORT:-${PORT:-8080}}"

# Garantir links diretos da raiz para acesso sem referência /web/
ln -sf web/index.html index.html
ln -sf web/style.css style.css
ln -sf web/app.js app.js
ln -sf web/modelos.html modelos.html
ln -sf web/mapa.html mapa.html
ln -sf web/dashboard.html dashboard.html
ln -sf web/dashboard.js dashboard.js
ln -sf web/api api

# Detectar IPs da rede local
LAN_IPS=$(hostname -I 2>/dev/null || echo "127.0.0.1")
PRIMARY_IP=$(echo "$LAN_IPS" | awk '{print $1}')

echo "============================================================"
echo " MÉTIS — Inteligência Adaptativa & Laboratório Territorial"
echo " Ecossistema SisTer · Núcleo C++26 Nativo"
echo "============================================================"
echo " Servidor web disponível diretamente (sem /web/):"
echo "  • Loopback local:  http://localhost:${PORT}/"
if [[ -n "$PRIMARY_IP" && "$PRIMARY_IP" != "127.0.0.1" ]]; then
echo "  • Rede local (IP): http://${PRIMARY_IP}:${PORT}/"
fi
echo "  • Rede (0.0.0.0):  http://0.0.0.0:${PORT}/"
echo "============================================================"
echo " Pressione Ctrl+C para encerrar."
echo

exec python3 -m http.server "$PORT" --bind "$HOST" --directory .
