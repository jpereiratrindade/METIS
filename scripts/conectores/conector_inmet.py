#!/usr/bin/env python3
"""
MÉTIS — Conector Oficial INMET (Avisos Meteorológicos)
Coleta alertas meteorológicos operacionais em tempo real (CAP/JSON).
Persiste os payloads originais em data/evidencias/inmet/ com SHA-256
e insere as geometrias PostGIS e metadados no banco PostgreSQL (tabela 'avisos_meteorologicos_inmet').
"""

import os
import sys
import json
import ssl
import hashlib
from datetime import datetime, timezone
import urllib.request
import psycopg

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
OUTPUT_DIR = os.path.join(REPO_ROOT, "data/evidencias/inmet")
DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")
INMET_AVISOS_URL = "https://apiprevmet3.inmet.gov.br/avisos/ativos"

def calcular_sha256_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()

def coletar_avisos_inmet(db_url: str = DEFAULT_DB_URL, salvar_banco: bool = True):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ctx = ssl.create_default_context()
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) METIS-Epistemic-Lab/1.0",
        "Accept": "application/json"
    }

    print("=== Conector INMET: Iniciando Coleta de Avisos Meteorológicos ===")
    print(f"-> Endpoint: {INMET_AVISOS_URL}")

    try:
        req = urllib.request.Request(INMET_AVISOS_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            conteudo = resp.read()

        sha256 = calcular_sha256_bytes(conteudo)
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"inmet_avisos_ativos_{timestamp_str}.json"
        caminho_arquivo = os.path.join(OUTPUT_DIR, nome_arquivo)

        with open(caminho_arquivo, "wb") as f:
            f.write(conteudo)

        dados_json = json.loads(conteudo.decode("utf-8"))
        avisos_hoje = dados_json.get("hoje", [])
        avisos_futuro = dados_json.get("futuro", [])
        todos_avisos = avisos_hoje + avisos_futuro
        print(f"   ✓ Payload baixado: {len(todos_avisos)} avisos ativos no Brasil (SHA: {sha256[:12]}...)")

        avisos_inseridos = 0
        avisos_rs = []

        if salvar_banco and todos_avisos:
            with psycopg.connect(db_url, autocommit=False) as conn:
                with conn.cursor() as cur:
                    for av in todos_avisos:
                        cod = av.get("codigo")
                        if not cod:
                            continue

                        poly = av.get("poligono")
                        inicio_str = av.get("inicio") or av.get("data_inicio")
                        fim_str = av.get("fim") or av.get("data_fim")
                        riscos = av.get("riscos") or []
                        instrucoes = av.get("instrucoes") or []

                        cur.execute("""
                            INSERT INTO avisos_meteorologicos_inmet (
                                id_aviso_inmet, codigo, descricao, severidade, aviso_cor,
                                inicio, fim, poligono, geocodes, municipios_texto,
                                riscos, instrucoes, encerrado, sha256_origem, consultado_em
                            ) VALUES (
                                %s, %s, %s, %s, %s,
                                %s::timestamptz, %s::timestamptz,
                                CASE WHEN %s::text IS NOT NULL THEN ST_SetSRID(ST_GeomFromGeoJSON(%s::text), 4326) ELSE NULL END,
                                %s, %s,
                                %s, %s, %s, %s, CURRENT_TIMESTAMP
                            )
                            ON CONFLICT (codigo) DO UPDATE SET
                                descricao = EXCLUDED.descricao,
                                severidade = EXCLUDED.severidade,
                                aviso_cor = EXCLUDED.aviso_cor,
                                inicio = EXCLUDED.inicio,
                                fim = EXCLUDED.fim,
                                poligono = EXCLUDED.poligono,
                                geocodes = EXCLUDED.geocodes,
                                municipios_texto = EXCLUDED.municipios_texto,
                                riscos = EXCLUDED.riscos,
                                instrucoes = EXCLUDED.instrucoes,
                                encerrado = EXCLUDED.encerrado,
                                sha256_origem = EXCLUDED.sha256_origem,
                                consultado_em = CURRENT_TIMESTAMP;
                        """, (
                            av.get("id_aviso", 0),
                            cod,
                            av.get("descricao", "Aviso Meteorológico"),
                            av.get("severidade", "Indefinida"),
                            av.get("aviso_cor", "#FFA500"),
                            inicio_str,
                            fim_str,
                            poly if poly else None,
                            poly if poly else None,
                            av.get("geocodes"),
                            av.get("municipios"),
                            riscos,
                            instrucoes,
                            av.get("encerrado", False),
                            sha256
                        ))
                        avisos_inseridos += 1

                    # Identificar cruzamento com municípios do RS
                    cur.execute("""
                        SELECT 
                            aviso_codigo, descricao, severidade, aviso_cor,
                            inicio, fim, COUNT(DISTINCT codigo_ibge) AS total_municipios_rs,
                            array_agg(DISTINCT codigo_ibge) AS lista_ibge,
                            riscos, instrucoes
                        FROM vw_municipios_avisos_inmet
                        WHERE uf = 'RS'
                        GROUP BY aviso_codigo, descricao, severidade, aviso_cor, inicio, fim, riscos, instrucoes
                        ORDER BY inicio DESC;
                    """)
                    for row in cur.fetchall():
                        avisos_rs.append({
                            "codigo": row[0],
                            "descricao": row[1],
                            "severidade": row[2],
                            "cor": row[3],
                            "inicio": str(row[4]),
                            "fim": str(row[5]),
                            "total_municipios_rs": row[6],
                            "municipios_rs": row[7],
                            "riscos": row[8],
                            "instrucoes": row[9]
                        })

                    conn.commit()

        print(f"=== INMET: Coleta finalizada! Avisos no banco: {avisos_inseridos} | Afetam RS: {len(avisos_rs)} ===")
        for a in avisos_rs:
            print(f"   -> [{a['severidade']}] {a['descricao']} ({a['inicio']} a {a['fim']}): {a['total_municipios_rs']} municípios do RS afetados")

        return {
            "avisos_total": len(todos_avisos),
            "avisos_rs": avisos_rs,
            "arquivo": nome_arquivo,
            "sha256": sha256
        }

    except Exception as e:
        print(f"   ✗ Erro na coleta de avisos INMET: {e}", file=sys.stderr)
        return {"avisos_total": 0, "avisos_rs": [], "erro": str(e)}

if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_URL
    coletar_avisos_inmet(db)
