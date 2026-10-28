#!/usr/bin/env bash
set -euo pipefail
# Exige curl, unzip e GDAL/ogr2ogr. Acesso à rede APENAS nesta etapa de ingestão.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/data/raw" "$ROOT/data/gerados"
URL='https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2022/UFs/RS/RS_Municipios_2022.zip'
curl --fail --location --retry 3 "$URL" -o "$ROOT/data/raw/RS_Municipios_2022.zip"
sha256sum "$ROOT/data/raw/RS_Municipios_2022.zip" > "$ROOT/data/raw/RS_Municipios_2022.sha256"
mkdir -p "$ROOT/data/raw/malha"
unzip -oq "$ROOT/data/raw/RS_Municipios_2022.zip" -d "$ROOT/data/raw/malha"
SHP="$(find "$ROOT/data/raw/malha" -iname '*.shp' -print -quit)"
test -n "$SHP"
ogr2ogr -f GeoJSON -t_srs EPSG:4326 "$ROOT/data/gerados/municipios_rs_2022.geojson" "$SHP"
echo 'Malha gerada. Conferir 497 municipios (excluir eventuais areas operacionais, se houver).'
