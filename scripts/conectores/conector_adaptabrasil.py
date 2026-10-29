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

def coletar_catalogo_adaptabrasil(db_url: str = DEFAULT_DB_URL, headers: dict = None, ctx = None):
    print("-> Sincronizando Catálogo Metodológico Oficial (/api/hierarquia/adaptabrasil)...")
    url = "https://sistema.adaptabrasil.mcti.gov.br/api/hierarquia/adaptabrasil"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                count = 0
                for item in data:
                    ind_id = item.get("id")
                    if ind_id is None:
                        continue
                    cur.execute("""
                        INSERT INTO catalogo_indicadores_adaptabrasil (
                            indicador_id, nome, titulo, descricao_simples, anos_disponiveis,
                            cenarios_json, legenda_json, direcao_interpretacao, atualizado_em
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (indicador_id) DO UPDATE SET
                            nome = EXCLUDED.nome,
                            titulo = EXCLUDED.titulo,
                            descricao_simples = EXCLUDED.descricao_simples,
                            anos_disponiveis = EXCLUDED.anos_disponiveis,
                            cenarios_json = EXCLUDED.cenarios_json,
                            legenda_json = EXCLUDED.legenda_json,
                            direcao_interpretacao = EXCLUDED.direcao_interpretacao,
                            atualizado_em = CURRENT_TIMESTAMP;
                    """, (
                        ind_id,
                        item.get("name") or f"Indicador {ind_id}",
                        item.get("title"),
                        item.get("simple_description"),
                        item.get("years") or [],
                        json.dumps(item.get("scenarios") or []),
                        json.dumps(item.get("legend") or {}),
                        "pessimista" if item.get("pessimist") == 1 else "otimista"
                    ))
                    count += 1
                conn.commit()
        print(f"   ✓ Catálogo atualizado com sucesso: {count} indicadores oficiais registrados.")
        return count
    except Exception as e:
        print(f"   ✗ Falha ao obter catálogo metodológico: {e}", file=sys.stderr)
        return 0

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

    print("=== Conector AdaptaBrasil MCTI: Iniciando Coleta ===")
    coletar_catalogo_adaptabrasil(db_url, headers=headers, ctx=ctx)

    dados_consolidados_rs = {} # geocod_ibge -> list of indicators
    total_registros_inseridos = 0
    arquivos_gerados = []
    status_msg = "Operacional"

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

    # Registrar status na tabela de auditoria de conectores
    if salvar_banco:
        try:
            with psycopg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO status_conectores (
                            fonte, ultima_tentativa, ultima_coleta_sucesso, status,
                            registros_processados, mensagem
                        ) VALUES (%s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s, %s)
                        ON CONFLICT (fonte) DO UPDATE SET
                            ultima_tentativa = CURRENT_TIMESTAMP,
                            ultima_coleta_sucesso = CURRENT_TIMESTAMP,
                            status = EXCLUDED.status,
                            registros_processados = EXCLUDED.registros_processados,
                            mensagem = EXCLUDED.mensagem;
                    """, ("adaptabrasil", "operacional", total_registros_inseridos, "Coleta e catálogo sincronizados com sucesso"))
                    conn.commit()
        except Exception as e_aud:
            print(f"   [AVISO] Falha ao registrar status_conectores: {e_aud}", file=sys.stderr)

    return {
        "municipios": dados_consolidados_rs,
        "arquivos": arquivos_gerados,
        "total_registros": total_registros_inseridos
    }

if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_URL
    coletar_indicadores_adaptabrasil(db)
