#!/usr/bin/env python3
"""
MÉTIS — Conector Oficial AdaptaBrasil MCTI
Coleta indicadores municipais de risco climático, vulnerabilidade e exposição.
Persiste os payloads originais em data/evidencias/adaptabrasil/ com SHA-256
e insere no banco PostgreSQL (tabela 'evidencias_adaptabrasil').
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
OUTPUT_DIR = os.path.join(REPO_ROOT, "data/evidencias/adaptabrasil")
DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")

# Indicadores de referência para o laboratório agroterritorial
INDICADORES_CONFIG = [
    {
        "id": 5001,
        "ano": 2017,
        "cenario_api": "null",
        "cenario_label": "baseline_2017",
        "nome": "Segurança Alimentar: Risco na Disponibilidade de Alimentos"
    },
    {
        "id": 5002,
        "ano": 2017,
        "cenario_api": "null",
        "cenario_label": "baseline_2017",
        "nome": "Vulnerabilidade à Seca Agropecuária"
    },
    {
        "id": 5003,
        "ano": 2017,
        "cenario_api": "null",
        "cenario_label": "baseline_2017",
        "nome": "Exposição à Seca Agropecuária"
    },
    {
        "id": 60041,
        "ano": 2015,
        "cenario_api": "null",
        "cenario_label": "baseline_2015",
        "nome": "Desastres Geo-hidrológicos: Risco de Inundações e Enxurradas"
    },
    {
        "id": 5001,
        "ano": 2030,
        "cenario_api": "53",
        "cenario_label": "projecao_2030_rcp45",
        "nome": "Segurança Alimentar: Projeção 2030 (Cenário Intermediário RCP4.5)"
    },
    {
        "id": 5001,
        "ano": 2050,
        "cenario_api": "53",
        "cenario_label": "projecao_2050_rcp45",
        "nome": "Segurança Alimentar: Projeção 2050 (Cenário Intermediário RCP4.5)"
    }
]

def calcular_sha256_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()

def coletar_indicadores_adaptabrasil(db_url: str = DEFAULT_DB_URL, salvar_banco: bool = True):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ctx = ssl.create_default_context()
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://adaptabrasil.mcti.gov.br",
        "Referer": "https://adaptabrasil.mcti.gov.br/"
    }

    dados_consolidados_rs = {} # geocod_ibge -> list of indicators
    total_registros_inseridos = 0
    arquivos_gerados = []

    print("=== Conector AdaptaBrasil MCTI: Iniciando Coleta ===")

    for cfg in INDICADORES_CONFIG:
        ind_id = cfg["id"]
        ano = cfg["ano"]
        cen_api = cfg["cenario_api"]
        cen_lbl = cfg["cenario_label"]
        nome_ind = cfg["nome"]

        url = f"https://sistema.adaptabrasil.mcti.gov.br/api/mapa-dados/BR/municipio/{ind_id}/{ano}/{cen_api}/adaptabrasil"
        print(f"-> Coletando Indicador {ind_id} ({ano}, {cen_lbl}): {url}")

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                conteudo = resp.read()
            
            sha256 = calcular_sha256_bytes(conteudo)
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"adaptabrasil_{ind_id}_{ano}_{cen_lbl}_{timestamp_str}.json"
            caminho_arquivo = os.path.join(OUTPUT_DIR, nome_arquivo)

            with open(caminho_arquivo, "wb") as f:
                f.write(conteudo)
            arquivos_gerados.append((nome_arquivo, sha256))

            dados_json = json.loads(conteudo.decode("utf-8"))
            registros_rs = [d for d in dados_json if str(d.get("geocod_ibge", "")).startswith("43")]
            print(f"   ✓ Payload baixado: {len(dados_json)} municípios BR, {len(registros_rs)} municípios RS (SHA: {sha256[:12]}...)")

            # Indexar na memória para exportação agregada
            for reg in registros_rs:
                ibge = str(reg.get("geocod_ibge"))
                if ibge not in dados_consolidados_rs:
                    dados_consolidados_rs[ibge] = []
                dados_consolidados_rs[ibge].append({
                    "indicador_id": ind_id,
                    "nome": nome_ind,
                    "ano": ano,
                    "cenario": cen_lbl,
                    "valor": reg.get("value"),
                    "classe": reg.get("rangelabel"),
                    "cor": reg.get("valuecolor")
                })

            # Persistência no PostgreSQL
            if salvar_banco and registros_rs:
                with psycopg.connect(db_url, autocommit=False) as conn:
                    with conn.cursor() as cur:
                        for reg in registros_rs:
                            ibge = str(reg.get("geocod_ibge"))
                            cur.execute("""
                                INSERT INTO evidencias_adaptabrasil (
                                    codigo_ibge, indicador_id, nome_indicador, ano_referencia,
                                    cenario, pessimist, valor, classe_risco, cor_hex, sha256_origem
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (codigo_ibge, indicador_id, ano_referencia, cenario)
                                DO UPDATE SET 
                                    valor = EXCLUDED.valor,
                                    classe_risco = EXCLUDED.classe_risco,
                                    cor_hex = EXCLUDED.cor_hex,
                                    sha256_origem = EXCLUDED.sha256_origem,
                                    criado_em = CURRENT_TIMESTAMP;
                            """, (
                                ibge,
                                ind_id,
                                nome_ind,
                                ano,
                                cen_lbl,
                                reg.get("pessimist", 0),
                                reg.get("value"),
                                reg.get("rangelabel"),
                                reg.get("valuecolor"),
                                sha256
                            ))
                            total_registros_inseridos += 1
                        conn.commit()

        except Exception as e:
            print(f"   ✗ Erro na coleta do indicador {ind_id}: {e}", file=sys.stderr)

    print(f"=== AdaptaBrasil: Coleta finalizada! Inserções no banco: {total_registros_inseridos} ===")
    return {
        "municipios": dados_consolidados_rs,
        "arquivos": arquivos_gerados,
        "total_registros": total_registros_inseridos
    }

if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_URL
    coletar_indicadores_adaptabrasil(db)
