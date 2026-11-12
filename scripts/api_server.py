#!/usr/bin/env python3
"""Servidor web/API METIS. Leitura pública; sincronização INMET protegida."""

import hmac
import base64
import json
import os
import sys
import threading
from decimal import Decimal
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from cryptography.hazmat.primitives import serialization

import psycopg
from psycopg.rows import dict_row

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB_ROOT = os.path.join(REPO_ROOT, "web")
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
sys.path.insert(0, os.path.join(SCRIPTS_DIR, "conectores"))
from metis_mcp import MAX_INPUT_BYTES, MCPHTTPDispatcher, check_mcp_http_auth  # noqa: E402
from metis_ops import catalog as mcp_catalog  # noqa: E402
from sincronizar_inmet import sincronizar_inmet  # noqa: E402

DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")
ADMIN_TOKEN = os.environ.get("METIS_ADMIN_TOKEN", "")
MCP_TOKEN = os.environ.get("METIS_MCP_TOKEN", "")
MCP_ALLOW_WRITES = os.environ.get("METIS_MCP_ALLOW_WRITES", "0") == "1"
STALE_MINUTES = max(1, int(os.environ.get("METIS_INMET_STALE_MINUTES", "30")))
sync_lock = threading.Lock()
default_mcp_dispatcher = MCPHTTPDispatcher(DB_URL, allow_writes=MCP_ALLOW_WRITES)
IDENTITY_KEY_PATH = os.environ.get("METIS_IDENTITY_KEY_PATH", "")
IDENTITY_ENDPOINT = os.environ.get("METIS_IDENTITY_ENDPOINT", "http://10.163.80.176:8080/mapa.html")


def _is_mcp_path(path: str) -> bool:
    return path == "/mcp" or (path.startswith("/mcp/") and "/" not in path[5:])


def signed_identity(nonce):
    if len(nonce) != 64 or any(c not in "0123456789abcdef" for c in nonce):
        raise ValueError("nonce inválido")
    if not IDENTITY_KEY_PATH:
        raise RuntimeError("identidade criptográfica não configurada")
    with open(IDENTITY_KEY_PATH, "rb") as stream:
        key = serialization.load_pem_private_key(stream.read(), password=None)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    statement = {
        "endpoint": IDENTITY_ENDPOINT,
        "expires_at": (now + __import__("datetime").timedelta(seconds=30)).isoformat().replace("+00:00", "Z"),
        "identity": "metis",
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "nonce": nonce,
        "version": "0.1.0",
    }
    canonical = json.dumps(statement, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return {"identity_statement": statement,
            "signature_base64": base64.b64encode(key.sign(canonical)).decode("ascii")}


def json_default(valor):
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    raise TypeError(type(valor).__name__)


class MetisHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_ROOT, **kwargs)

    def _json(self, status, payload, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False, default=json_default).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _mcp_config(self):
        dispatcher = getattr(self.server, "mcp_dispatcher", default_mcp_dispatcher)
        token = getattr(self.server, "mcp_token", MCP_TOKEN)
        return dispatcher, token

    def _query(self, sql, params=()):
        with psycopg.connect(DB_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def do_OPTIONS(self):
        path = urlparse(self.path).path
        if _is_mcp_path(path):
            self.send_response(204)
            self.send_header("Allow", "POST, DELETE, OPTIONS")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_DELETE(self):
        path = urlparse(self.path).path
        if not _is_mcp_path(path):
            return self._json(404, {"erro": "rota não encontrada"})
        dispatcher, token = self._mcp_config()
        if not check_mcp_http_auth(self.headers, path, token):
            return self._json(
                401,
                {"code": "AUTHORITY_REQUIRED", "message": "Token MCP inválido ou ausente"},
                extra_headers={"WWW-Authenticate": "Bearer"},
            )
        dispatcher.close_session(self.headers.get("Mcp-Session-Id"))
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if _is_mcp_path(parsed.path):
                return self._json(
                    405,
                    {"code": "METHOD_NOT_ALLOWED", "message": "Use POST /mcp para JSON-RPC MCP Streamable HTTP"},
                    extra_headers={"Allow": "POST, DELETE, OPTIONS"},
                )
            if parsed.path == "/api/v1/tools":
                dispatcher, token = self._mcp_config()
                return self._json(
                    200,
                    {
                        "tools": mcp_catalog(True),
                        "transport": "MCP stdio + Streamable HTTP",
                        "default_mode": "read_only",
                        "http_endpoint": "/mcp",
                        "http_writes": dispatcher.allow_writes,
                        "http_auth": bool(token),
                    },
                )
            if parsed.path == "/.well-known/sister-identity":
                try:
                    return self._json(200, signed_identity(query.get("nonce", [""])[0]))
                except ValueError as exc:
                    return self._json(400, {"erro": str(exc)})
                except (OSError, RuntimeError, ValueError):
                    return self._json(503, {"erro": "identidade criptográfica indisponível"})
            if parsed.path == "/api/v1/inmet/status":
                rows = self._query("""
                    SELECT id,iniciada_em,finalizada_em,status,acionamento,http_status,
                           sha256_payload,avisos_recebidos,avisos_validos,versoes_criadas,mensagem,
                           (finalizada_em < CURRENT_TIMESTAMP-(%s * interval '1 minute')) AS desatualizado
                    FROM inmet_coletas ORDER BY iniciada_em DESC LIMIT 1
                """, (STALE_MINUTES,))
                return self._json(200, {"limite_desatualizacao_minutos": STALE_MINUTES,
                                        "ultima_coleta": rows[0] if rows else None})
            if parsed.path == "/api/v1/inmet/avisos":
                rows = self._query("""
                    SELECT codigo,descricao,severidade,aviso_cor AS cor,inicio,fim,situacao_origem,
                           CASE WHEN situacao_origem='cancelado' THEN 'cancelado'
                                WHEN CURRENT_TIMESTAMP<inicio THEN 'futuro'
                                WHEN CURRENT_TIMESTAMP<=fim THEN 'vigente' ELSE 'expirado' END AS estado_vigencia,
                           ultima_observacao_em
                    FROM avisos_meteorologicos_inmet
                    WHERE situacao_origem<>'cancelado' AND fim>=CURRENT_TIMESTAMP
                    ORDER BY inicio DESC
                """)
                return self._json(200, {"avisos": rows})
            if parsed.path == "/api/v1/inmet/coletas":
                limite = min(200, max(1, int(query.get("limite", ["50"])[0])))
                rows = self._query("SELECT * FROM inmet_coletas ORDER BY iniciada_em DESC LIMIT %s", (limite,))
                return self._json(200, {"coletas": rows})
            if parsed.path == "/api/v1/simagro/status":
                coletas = self._query("""
                    SELECT id, iniciada_em, finalizada_em, janela, data_referencia, status,
                           acionamento, http_status, sha256_payload, registros_recebidos,
                           registros_validos, mensagem
                    FROM simagro_coletas ORDER BY iniciada_em DESC LIMIT 5
                """)
                conector = self._query(
                    "SELECT fonte, ultima_tentativa, ultima_coleta_sucesso, status, mensagem "
                    "FROM status_conectores WHERE fonte = 'simagro_alertas'"
                )
                return self._json(200, {
                    "fonte": "SEAPI/DDPA/SIMAGRO-RS",
                    "conector": conector[0] if conector else None,
                    "ultimas_coletas": coletas,
                })
            if parsed.path == "/api/v1/simagro/alertas":
                janela = (query.get("janela", ["7d"])[0] or "7d").strip()
                if janela not in ("3d", "7d"):
                    return self._json(400, {"erro": "janela inválida: use '3d' ou '7d'"})
                nivel_min = max(0, min(3, int(query.get("nivel_min", ["0"])[0])))
                codigo_ibge = (query.get("codigo_ibge", [""])[0] or "").strip()
                data_ref = (query.get("data", [""])[0] or "").strip()
                filtros = ["a.janela = %s", "a.nivel_maximo >= %s"]
                params: list = [janela, nivel_min]
                if codigo_ibge:
                    if len(codigo_ibge) != 7 or not codigo_ibge.isdigit():
                        return self._json(400, {"erro": "código IBGE inválido"})
                    filtros.append("a.codigo_ibge = %s")
                    params.append(codigo_ibge)
                if data_ref:
                    filtros.append("a.data_referencia = %s::date")
                    params.append(data_ref)
                    tabela = """
                        SELECT a.codigo_ibge, m.nome AS municipio_nome, m.uf, a.id_ponto,
                               a.data_referencia, a.janela, a.prec, a.estiagem,
                               a.estiagem_agricola, a.geada, a.t_acima, a.t_abaixo,
                               a.itu, a.ci_ovino, a.nivel_maximo, a.consultado_em
                        FROM evidencias_simagro_alertas a
                        JOIN municipios m ON m.codigo_ibge = a.codigo_ibge
                    """
                else:
                    tabela = "SELECT a.* FROM vw_simagro_alertas_recentes a"
                where = " AND ".join(filtros)
                rows = self._query(
                    f"{tabela} WHERE {where} ORDER BY a.nivel_maximo DESC, a.codigo_ibge ASC",
                    tuple(params),
                )
                return self._json(200, {
                    "fonte": "SEAPI/DDPA/SIMAGRO-RS",
                    "janela": janela,
                    "nivel_min": nivel_min,
                    "total": len(rows),
                    "alertas": rows,
                })
            if parsed.path == "/api/v1/evidencias/resumo":
                indicadores = self._query("""
                    SELECT codigo_ibge,indicador_id,nome_indicador AS nome,
                           ano_referencia AS ano,cenario,valor,classe_risco AS classe,cor_hex AS cor
                    FROM evidencias_adaptabrasil
                    WHERE indicador_id=5001 AND ano_referencia=2017
                    ORDER BY codigo_ibge
                """)
                alertas = self._query("""
                    SELECT codigo_ibge,aviso_codigo AS codigo,descricao,severidade,aviso_cor AS cor,
                           inicio,fim,estado_vigencia
                    FROM vw_municipios_avisos_inmet
                    WHERE estado_vigencia IN ('vigente','futuro')
                    ORDER BY codigo_ibge,inicio DESC
                """)
                coleta = self._query("""
                    SELECT id,iniciada_em,finalizada_em,status,acionamento,http_status,
                           sha256_payload,avisos_recebidos,avisos_validos,versoes_criadas,mensagem,
                           (finalizada_em < CURRENT_TIMESTAMP-(%s * interval '1 minute')) AS desatualizado
                    FROM inmet_coletas ORDER BY iniciada_em DESC LIMIT 1
                """, (STALE_MINUTES,))
                catalogo_avisos = self._query("""
                    SELECT aviso_codigo AS codigo, descricao, severidade, aviso_cor AS cor,
                           min(inicio) AS inicio, max(fim) AS fim, estado_vigencia,
                           count(distinct codigo_ibge) AS total_municipios
                    FROM vw_municipios_avisos_inmet
                    WHERE estado_vigencia IN ('vigente','futuro')
                    GROUP BY aviso_codigo, descricao, severidade, aviso_cor, estado_vigencia
                    ORDER BY CASE severidade WHEN 'Grande Perigo' THEN 1 WHEN 'Perigo' THEN 2 ELSE 3 END,
                             estado_vigencia DESC, inicio ASC
                """)
                simagro_rows = self._query("""
                    SELECT codigo_ibge, data_referencia, janela, prec, estiagem,
                           estiagem_agricola, geada, t_acima, t_abaixo, itu, ci_ovino, nivel_maximo
                    FROM vw_simagro_alertas_recentes
                    WHERE janela = '7d'
                    ORDER BY codigo_ibge
                """)
                simagro_coleta = self._query("""
                    SELECT id, iniciada_em, finalizada_em, janela, data_referencia, status,
                           sha256_payload, registros_recebidos, registros_validos
                    FROM simagro_coletas
                    ORDER BY iniciada_em DESC LIMIT 1
                """)
                municipios = {}
                for item in indicadores:
                    ibge = item.pop("codigo_ibge")
                    municipios.setdefault(ibge, {"adaptabrasil": [], "avisos_inmet": [], "simagro_alertas": None})["adaptabrasil"].append(item)
                for item in alertas:
                    ibge = item.pop("codigo_ibge")
                    municipios.setdefault(ibge, {"adaptabrasil": [], "avisos_inmet": [], "simagro_alertas": None})["avisos_inmet"].append(item)
                for item in simagro_rows:
                    ibge = item.pop("codigo_ibge")
                    municipios.setdefault(ibge, {"adaptabrasil": [], "avisos_inmet": [], "simagro_alertas": None})["simagro_alertas"] = item
                return self._json(200, {
                    "metadados": {
                        "modo": "resumo dinâmico",
                        "fontes": {
                            "inmet": {
                                "ultima_coleta_auditada": coleta[0] if coleta else None,
                                "validade_minutos": STALE_MINUTES,
                                "total_avisos_ativos_rs": len(catalogo_avisos),
                                "avisos_ativos": catalogo_avisos,
                            },
                            "simagro": {
                                "instituicao": "SEAPI/DDPA/SIMAGRO-RS",
                                "ultima_coleta_auditada": simagro_coleta[0] if simagro_coleta else None,
                                "total_municipios_7d": len(simagro_rows),
                                "municipios_alerta_alto_7d": sum(1 for r in simagro_rows if r["nivel_maximo"] >= 2),
                            },
                        }
                    },
                    "municipios": municipios
                })
            if parsed.path == "/api/v1/inmet/historico":
                pagina = max(1, int(query.get("pagina", ["1"])[0]))
                por_pagina = min(100, max(1, int(query.get("por_pagina", ["25"])[0])))
                filtros, params = [], []
                mapa_filtros = {
                    "codigo_ibge": "im.codigo_ibge = %s",
                    "tipo_evento": "v.descricao ILIKE %s",
                    "estado": "v.situacao_origem = %s",
                    "de": "v.inicio >= %s::timestamptz",
                    "ate": "v.inicio <= %s::timestamptz",
                }
                for chave, clausula in mapa_filtros.items():
                    if query.get(chave):
                        valor = query[chave][0]
                        filtros.append(clausula)
                        params.append(f"%{valor}%" if chave == "tipo_evento" else valor)
                where = "WHERE " + " AND ".join(filtros) if filtros else ""
                params.extend([por_pagina, (pagina - 1) * por_pagina])
                rows = self._query(f"""
                    SELECT COUNT(*) OVER() AS total, im.codigo_ibge, m.nome AS municipio,
                           a.codigo, v.id AS versao_id, v.observado_em, v.descricao,
                           v.severidade, v.inicio, v.fim, v.situacao_origem,
                           im.via_geocodigo, im.via_intersecao_espacial
                    FROM inmet_avisos_versoes v
                    JOIN avisos_meteorologicos_inmet a ON a.id=v.aviso_id
                    JOIN inmet_avisos_municipios im ON im.versao_id=v.id
                    JOIN municipios m ON m.codigo_ibge=im.codigo_ibge
                    {where}
                    ORDER BY v.inicio DESC, im.codigo_ibge
                    LIMIT %s OFFSET %s
                """, tuple(params))
                total = rows[0]["total"] if rows else 0
                return self._json(200, {"pagina": pagina, "por_pagina": por_pagina,
                                        "total": total, "resultados": rows})
            if parsed.path.startswith("/api/v1/municipios/") and parsed.path.endswith("/evidencias"):
                codigo = parsed.path.split("/")[-2]
                if len(codigo) != 7 or not codigo.isdigit():
                    return self._json(400, {"erro": "código IBGE inválido"})
                municipio = self._query("SELECT codigo_ibge,nome,uf FROM municipios WHERE codigo_ibge=%s", (codigo,))
                if not municipio:
                    return self._json(404, {"erro": "município não encontrado"})
                adapta = self._query("""
                    SELECT indicador_id,nome_indicador AS nome,ano_referencia AS ano,
                           cenario,valor,classe_risco AS classe,cor_hex AS cor
                    FROM evidencias_adaptabrasil WHERE codigo_ibge=%s
                    ORDER BY indicador_id,ano_referencia,cenario
                """, (codigo,))
                avisos = self._query("""
                    SELECT aviso_codigo AS codigo,descricao,severidade,aviso_cor AS cor,
                           inicio,fim,estado_vigencia,riscos,instrucoes,
                           afetado_por_geocodigo AS via_geocodigo,
                           afetado_por_intersecao_espacial AS via_espacial
                    FROM vw_municipios_avisos_inmet
                    WHERE codigo_ibge=%s AND estado_vigencia IN ('vigente','futuro')
                    ORDER BY inicio DESC
                """, (codigo,))
                episodios = self._query("""
                    SELECT id,aviso_codigo,tipo_ameaca,severidade,janela_inicio,janela_fim,
                           estado_episodio,desfecho_cientifico,condicoes_antecedentes,
                           estado_metis_congelado,evidencias_impacto,notas_cientificas AS notas,
                           criado_em,atualizado_em
                    FROM episodios_investigacao WHERE codigo_ibge=%s
                    ORDER BY janela_inicio DESC
                """, (codigo,))
                simagro_alertas = self._query("""
                    SELECT data_referencia, janela, prec, estiagem, estiagem_agricola,
                           geada, t_acima, t_abaixo, itu, ci_ovino, nivel_maximo, consultado_em
                    FROM vw_simagro_alertas_recentes
                    WHERE codigo_ibge = %s
                    ORDER BY janela DESC
                """, (codigo,))
                return self._json(200, {
                    "municipio": municipio[0],
                    "fontes": {
                        "avisos": "INMET",
                        "alertas_agroclimaticos": "SEAPI/DDPA/SIMAGRO-RS",
                        "risco_climatico": "MCTI/AdaptaBrasil",
                        "territorio": "IBGE",
                        "hipoteses": "Inferência determinística MÉTIS",
                    },
                    "adaptabrasil": adapta,
                    "avisos_inmet": avisos,
                    "simagro_alertas": simagro_alertas,
                    "episodios": episodios,
                })
            if parsed.path.startswith("/api/v1/inmet/avisos/") and parsed.path.endswith("/versoes"):
                codigo = parsed.path.split("/")[-2]
                rows = self._query("""
                    SELECT v.id,v.observado_em,v.fingerprint_sha256,v.descricao,v.severidade,
                           v.aviso_cor,v.inicio,v.fim,v.geocodes,v.riscos,v.instrucoes,
                           v.situacao_origem,v.coleta_id
                    FROM inmet_avisos_versoes v JOIN avisos_meteorologicos_inmet a ON a.id=v.aviso_id
                    WHERE a.codigo=%s ORDER BY v.observado_em DESC
                """, (codigo,))
                return self._json(200, {"codigo": codigo, "versoes": rows})
        except (psycopg.Error, ValueError) as exc:
            return self._json(503, {"erro": "API temporariamente indisponível", "detalhe": str(exc)})
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if _is_mcp_path(path):
            dispatcher, token = self._mcp_config()
            if not check_mcp_http_auth(self.headers, path, token):
                return self._json(
                    401,
                    {"code": "AUTHORITY_REQUIRED", "message": "Token MCP inválido ou ausente"},
                    extra_headers={"WWW-Authenticate": "Bearer"},
                )
            ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if ctype != "application/json":
                return self._json(400, {"code": "INVALID_INPUT", "message": "Envie application/json"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._json(400, {"code": "INVALID_INPUT", "message": "Content-Length inválido"})
            if length <= 0 or length > MAX_INPUT_BYTES:
                return self._json(400, {"code": "INVALID_INPUT", "message": "Corpo ausente ou excede limite de 1 MiB"})
            raw_body = self.rfile.read(length)
            response, sid = dispatcher.dispatch(raw_body, self.headers.get("Mcp-Session-Id"))
            extra = {"Mcp-Session-Id": sid} if sid else {}
            if response is None:
                self.send_response(202)
                if sid:
                    self.send_header("Mcp-Session-Id", sid)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            return self._json(200, response, extra_headers=extra)

        if path != "/api/v1/admin/inmet/sincronizar":
            return self._json(404, {"erro": "rota não encontrada"})
        recebido = self.headers.get("Authorization", "")
        esperado = f"Bearer {ADMIN_TOKEN}"
        if not ADMIN_TOKEN or not hmac.compare_digest(recebido, esperado):
            return self._json(401, {"erro": "credencial administrativa inválida"})
        if not sync_lock.acquire(blocking=False):
            return self._json(409, {"erro": "sincronização já está em andamento"})
        try:
            resultado = sincronizar_inmet(DB_URL, acionamento="api")
            status = 409 if resultado.get("conflito") else (502 if resultado.get("erro") else 200)
            return self._json(status, resultado)
        finally:
            sync_lock.release()


if __name__ == "__main__":
    host = os.environ.get("METIS_HOST", "0.0.0.0")
    port = int(os.environ.get("METIS_PORT", "8080"))
    print(f"MÉTIS web/API em http://{host}:{port}", flush=True)
    try:
        ThreadingHTTPServer((host, port), MetisHandler).serve_forever()
    except KeyboardInterrupt:
        print("\nMÉTIS web/API encerrado.", flush=True)
