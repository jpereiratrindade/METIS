#!/usr/bin/env bash
# MÉTIS — Iniciar Banco de Dados PostgreSQL + PostGIS e Aplicar Migrações
set -euo pipefail

METIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$METIS_DIR"

DB_CONTAINER="metis-db"
DB_PORT="${METIS_DB_PORT:-5432}"
DB_USER="${METIS_DB_USER:-metis}"
DB_NAME="${METIS_DB_NAME:-metis}"

echo "=== MÉTIS: Inicializando persistência (PostgreSQL 17 + PostGIS 3.5) ==="

if podman container exists "$DB_CONTAINER" 2>/dev/null; then
    if [ "$(podman inspect -f '{{.State.Running}}' "$DB_CONTAINER")" = "true" ]; then
        echo "Contêiner '$DB_CONTAINER' já está em execução."
    else
        echo "Iniciando contêiner '$DB_CONTAINER' existente..."
        podman start "$DB_CONTAINER"
    fi
else
    echo "Criando e iniciando novo contêiner '$DB_CONTAINER'..."
    podman run -d \
        --name "$DB_CONTAINER" \
        -e POSTGRES_DB="$DB_NAME" \
        -e POSTGRES_USER="$DB_USER" \
        -e POSTGRES_PASSWORD="${METIS_DB_PASSWORD:-metis}" \
        -p "127.0.0.1:${DB_PORT}:5432" \
        -v "metis-pgdata:/var/lib/postgresql/data:Z" \
        docker.io/postgis/postgis:17-3.5
fi

echo "Aguardando prontidão do PostgreSQL..."
max_tentativas=30
tentativa=1
pronto=false

while [ $tentativa -le $max_tentativas ]; do
    if python3 -c "import psycopg; conn = psycopg.connect('postgresql://${DB_USER}:${METIS_DB_PASSWORD:-metis}@127.0.0.1:${DB_PORT}/${DB_NAME}', connect_timeout=2); conn.close()" 2>/dev/null; then
        pronto=true
        break
    fi
    sleep 1
    tentativa=$((tentativa + 1))
done

if [ "$pronto" = "false" ]; then
    echo "ERRO: O PostgreSQL não respondeu a tempo." >&2
    exit 1
fi

echo "PostgreSQL + PostGIS operacional na porta $DB_PORT!"
echo "Executando migrações pendentes..."
python3 scripts/db_migrate.py
