#!/usr/bin/env python3
"""Conector INMET temporal e auditavel (METIS-DIR-INMET-002)."""

import hashlib
import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime, timezone

import psycopg

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
OUTPUT_DIR = os.path.join(REPO_ROOT, "data/evidencias/inmet")
DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")
INMET_AVISOS_URL = os.environ.get("INMET_AVISOS_URL", "https://apiprevmet3.inmet.gov.br/avisos/ativos")
INMET_ADVISORY_LOCK_ID = 0x4D45544953494E4D


def calcular_sha256_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _normalizar_texto_lista(valor):
    if valor is None:
        return []
    if isinstance(valor, list):
        return [str(item) for item in valor]
    return [str(valor)]


def _normalizar_geocodes(valor) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, list):
        return ",".join(str(item).strip() for item in valor if str(item).strip())
    return str(valor).replace(";", ",").replace(" ", "")


def _normalizar_poligono(valor):
    if not valor:
        return None
    return json.dumps(valor, sort_keys=True) if isinstance(valor, (dict, list)) else str(valor)


def _snapshot(aviso: dict) -> dict:
    return {
        "descricao": aviso.get("descricao") or "Aviso Meteorológico",
        "severidade": aviso.get("severidade") or "Indefinida",
        "aviso_cor": aviso.get("aviso_cor") or "#FFA500",
        "inicio": aviso.get("inicio") or aviso.get("data_inicio"),
        "fim": aviso.get("fim") or aviso.get("data_fim"),
        "poligono": _normalizar_poligono(aviso.get("poligono")),
        "geocodes": _normalizar_geocodes(aviso.get("geocodes")),
        "municipios_texto": aviso.get("municipios"),
        "riscos": _normalizar_texto_lista(aviso.get("riscos")),
        "instrucoes": _normalizar_texto_lista(aviso.get("instrucoes")),
        "situacao_origem": "cancelado" if aviso.get("encerrado") is True else "ativo",
    }


def _fingerprint(snapshot: dict) -> str:
    bruto = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return calcular_sha256_bytes(bruto)


def _registrar_falha(db_url: str, coleta_id, status: str, mensagem: str):
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                if coleta_id is not None:
                    cur.execute(
                        "UPDATE inmet_coletas SET finalizada_em=CURRENT_TIMESTAMP, status=%s, mensagem=%s WHERE id=%s",
                        (status, mensagem[:4000], coleta_id),
                    )
                cur.execute("""
                    INSERT INTO status_conectores (fonte, ultima_tentativa, status, mensagem)
                    VALUES ('inmet_avisos', CURRENT_TIMESTAMP, %s, %s)
                    ON CONFLICT (fonte) DO UPDATE SET ultima_tentativa=CURRENT_TIMESTAMP,
                        status=EXCLUDED.status, mensagem=EXCLUDED.mensagem
                """, (status, mensagem[:4000]))
    except Exception:
        pass


def _coletar_avisos_inmet(db_url: str = DEFAULT_DB_URL, salvar_banco: bool = True,
                          acionamento: str = "manual"):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    coleta_id = None
    if salvar_banco:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO inmet_coletas (origem_url, acionamento) VALUES (%s, %s) RETURNING id",
                    (INMET_AVISOS_URL, acionamento),
                )
                coleta_id = cur.fetchone()[0]

    print(f"=== INMET: coleta {coleta_id or 'sem banco'} ({acionamento}) ===")
    try:
        req = urllib.request.Request(INMET_AVISOS_URL, headers={
            "User-Agent": "METIS-Epistemic-Lab/0.4 (+https://github.com/jpereiratrindade/METIS)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as resp:
            conteudo = resp.read()
            http_status = getattr(resp, "status", 200)

        sha256 = calcular_sha256_bytes(conteudo)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        nome_arquivo = f"inmet_avisos_{timestamp}_{sha256[:12]}.json"
        caminho_arquivo = os.path.join(OUTPUT_DIR, nome_arquivo)
        with open(caminho_arquivo, "wb") as arquivo:
            arquivo.write(conteudo)

        dados = json.loads(conteudo.decode())
        if not isinstance(dados, dict) or not isinstance(dados.get("hoje", []), list) or not isinstance(dados.get("futuro", []), list):
            raise ValueError("payload INMET inválido: esperadas listas 'hoje' e 'futuro'")
        avisos = dados.get("hoje", []) + dados.get("futuro", [])
        validos = [av for av in avisos if av.get("codigo")
                   and (av.get("inicio") or av.get("data_inicio"))
                   and (av.get("fim") or av.get("data_fim"))]
        versoes_criadas = 0

        if salvar_banco:
            with psycopg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    for av in validos:
                        snap = _snapshot(av)
                        fingerprint = _fingerprint(snap)
                        cur.execute("""
                            INSERT INTO avisos_meteorologicos_inmet (
                                id_aviso_inmet, codigo, descricao, severidade, aviso_cor, inicio, fim,
                                poligono, geocodes, municipios_texto, riscos, instrucoes, encerrado,
                                situacao_origem, sha256_origem, consultado_em, primeira_observacao_em,
                                ultima_observacao_em, ultima_coleta_id
                            ) VALUES (
                                %s,%s,%s,%s,%s,%s::timestamptz,%s::timestamptz,
                                CASE WHEN %s::text IS NULL THEN NULL ELSE ST_SetSRID(ST_GeomFromGeoJSON(%s::text),4326) END,
                                %s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,%s
                            ) ON CONFLICT (codigo) DO UPDATE SET
                                id_aviso_inmet=EXCLUDED.id_aviso_inmet, descricao=EXCLUDED.descricao,
                                severidade=EXCLUDED.severidade, aviso_cor=EXCLUDED.aviso_cor,
                                inicio=EXCLUDED.inicio, fim=EXCLUDED.fim, poligono=EXCLUDED.poligono,
                                geocodes=EXCLUDED.geocodes, municipios_texto=EXCLUDED.municipios_texto,
                                riscos=EXCLUDED.riscos, instrucoes=EXCLUDED.instrucoes,
                                encerrado=EXCLUDED.encerrado, situacao_origem=EXCLUDED.situacao_origem,
                                sha256_origem=EXCLUDED.sha256_origem, consultado_em=CURRENT_TIMESTAMP,
                                ultima_observacao_em=CURRENT_TIMESTAMP, ultima_coleta_id=EXCLUDED.ultima_coleta_id
                            RETURNING id
                        """, (
                            int(av.get("id_aviso") or 0), str(av["codigo"]), snap["descricao"], snap["severidade"],
                            snap["aviso_cor"], snap["inicio"], snap["fim"], snap["poligono"], snap["poligono"],
                            snap["geocodes"], snap["municipios_texto"], snap["riscos"], snap["instrucoes"],
                            snap["situacao_origem"] == "cancelado", snap["situacao_origem"], sha256, coleta_id,
                        ))
                        aviso_id = cur.fetchone()[0]
                        cur.execute("""
                            INSERT INTO inmet_avisos_versoes (
                                aviso_id, coleta_id, fingerprint_sha256, descricao, severidade, aviso_cor,
                                inicio, fim, poligono, geocodes, municipios_texto, riscos, instrucoes, situacao_origem
                            ) SELECT
                                %s,%s,%s,%s,%s,%s,%s::timestamptz,%s::timestamptz,
                                CASE WHEN %s::text IS NULL THEN NULL ELSE ST_SetSRID(ST_GeomFromGeoJSON(%s::text),4326) END,
                                %s,%s,%s,%s,%s
                            WHERE (SELECT fingerprint_sha256 FROM inmet_avisos_versoes
                                   WHERE aviso_id=%s ORDER BY observado_em DESC,id DESC LIMIT 1)
                                  IS DISTINCT FROM %s
                            ON CONFLICT (aviso_id, coleta_id) DO NOTHING RETURNING id
                        """, (
                            aviso_id, coleta_id, fingerprint, snap["descricao"], snap["severidade"], snap["aviso_cor"],
                            snap["inicio"], snap["fim"], snap["poligono"], snap["poligono"], snap["geocodes"],
                            snap["municipios_texto"], snap["riscos"], snap["instrucoes"], snap["situacao_origem"],
                            aviso_id, fingerprint,
                        ))
                        row = cur.fetchone()
                        if row:
                            versao_id = row[0]
                            versoes_criadas += 1
                            cur.execute("""
                                INSERT INTO inmet_avisos_municipios
                                    (versao_id,codigo_ibge,via_geocodigo,via_intersecao_espacial)
                                SELECT %s,m.codigo_ibge,
                                    m.codigo_ibge=ANY(string_to_array(%s,',')),
                                    CASE WHEN %s::text IS NULL THEN FALSE ELSE ST_Intersects(
                                        m.geometria,ST_SetSRID(ST_GeomFromGeoJSON(%s::text),4326)) END
                                FROM municipios m
                                WHERE m.codigo_ibge=ANY(string_to_array(%s,','))
                                   OR (%s::text IS NOT NULL AND ST_Intersects(
                                        m.geometria,ST_SetSRID(ST_GeomFromGeoJSON(%s::text),4326)))
                                ON CONFLICT DO NOTHING
                            """, (versao_id, snap["geocodes"], snap["poligono"], snap["poligono"],
                                  snap["geocodes"], snap["poligono"], snap["poligono"]))

                    cur.execute("""
                        UPDATE inmet_coletas SET finalizada_em=CURRENT_TIMESTAMP,status='sucesso',
                            http_status=%s,sha256_payload=%s,arquivo_payload=%s,
                            avisos_recebidos=%s,avisos_validos=%s,versoes_criadas=%s,mensagem=%s WHERE id=%s
                    """, (http_status, sha256, os.path.relpath(caminho_arquivo, REPO_ROOT), len(avisos),
                          len(validos), versoes_criadas, "Feed processado sem inferir cancelamento por ausência", coleta_id))
                    cur.execute("""
                        INSERT INTO status_conectores (fonte,ultima_tentativa,ultima_coleta_sucesso,status,registros_processados,mensagem)
                        VALUES ('inmet_avisos',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'operacional',%s,%s)
                        ON CONFLICT (fonte) DO UPDATE SET ultima_tentativa=CURRENT_TIMESTAMP,
                            ultima_coleta_sucesso=CURRENT_TIMESTAMP,status=EXCLUDED.status,
                            registros_processados=EXCLUDED.registros_processados,mensagem=EXCLUDED.mensagem
                    """, (len(validos), f"Coleta {coleta_id}: {versoes_criadas} novas versões"))

        print(f"✓ {len(validos)}/{len(avisos)} avisos válidos; {versoes_criadas} novas versões")
        return {"coleta_id": coleta_id, "avisos_total": len(avisos), "avisos_validos": len(validos),
                "versoes_criadas": versoes_criadas, "arquivo": nome_arquivo, "sha256": sha256}
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        _registrar_falha(db_url, coleta_id, "falha_validacao", str(exc))
        return {"coleta_id": coleta_id, "erro": str(exc), "status": "falha_validacao"}
    except Exception as exc:
        status = "falha_rede" if isinstance(exc, OSError) else "falha_persistencia"
        _registrar_falha(db_url, coleta_id, status, str(exc))
        return {"coleta_id": coleta_id, "erro": str(exc), "status": status}


def coletar_avisos_inmet(db_url: str = DEFAULT_DB_URL, salvar_banco: bool = True,
                         acionamento: str = "manual"):
    """Executa uma coleta sob lock compartilhado entre API, scheduler e CLI."""
    if not salvar_banco:
        return _coletar_avisos_inmet(db_url, salvar_banco=False, acionamento=acionamento)
    with psycopg.connect(db_url, autocommit=True) as lock_conn:
        with lock_conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (INMET_ADVISORY_LOCK_ID,))
            adquirido = cur.fetchone()[0]
        if not adquirido:
            return {
                "status": "sincronizacao_em_andamento",
                "conflito": True,
                "mensagem": "Outra sincronização INMET já possui o lock PostgreSQL",
            }
        try:
            return _coletar_avisos_inmet(db_url, salvar_banco=True, acionamento=acionamento)
        finally:
            with lock_conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (INMET_ADVISORY_LOCK_ID,))


if __name__ == "__main__":
    db = next((arg for arg in sys.argv[1:] if not arg.startswith("--")), DEFAULT_DB_URL)
    resultado = coletar_avisos_inmet(db, acionamento="agendado" if "--scheduled" in sys.argv else "manual")
    sys.exit(1 if resultado.get("erro") else (2 if resultado.get("conflito") else 0))
