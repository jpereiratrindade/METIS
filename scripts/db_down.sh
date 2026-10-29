#!/usr/bin/env bash
# MÉTIS — Parar Banco de Dados PostgreSQL + PostGIS
set -euo pipefail

DB_CONTAINER="metis-db"

if podman container exists "$DB_CONTAINER" 2>/dev/null; then
    echo "Parando contêiner '$DB_CONTAINER'..."
    podman stop "$DB_CONTAINER"
    echo "Contêiner parado com sucesso."
else
    echo "Contêiner '$DB_CONTAINER' não encontrado."
fi
