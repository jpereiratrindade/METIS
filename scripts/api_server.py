#!/usr/bin/env python3
"""Servidor web/API METIS. Leitura pública; sincronização INMET protegida."""

import hmac
import json
import os
import sys
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import psycopg
from psycopg.rows import dict_row

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB_ROOT = os.path.join(REPO_ROOT, "web")
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "conectores"))
from sincronizar_inmet import sincronizar_inmet

DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")
ADMIN_TOKEN = os.environ.get("METIS_ADMIN_TOKEN", "")
STALE_MINUTES = max(1, int(os.environ.get("METIS_INMET_STALE_MINUTES", "30")))
sync_lock = threading.Lock()


def json_default(valor):
    if isinstance(valor, datetime):
        return valor.isoformat()
    raise TypeError(type(valor).__name__)


class MetisHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_ROOT, **kwargs)

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, default=json_default).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _query(self, sql, params=()):
        with psycopg.connect(DB_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def do_GET(self):
        parsed = urlparse(self.path)
        try:
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
                limite = min(200, max(1, int(parse_qs(parsed.query).get("limite", ["50"])[0])))
                rows = self._query("SELECT * FROM inmet_coletas ORDER BY iniciada_em DESC LIMIT %s", (limite,))
                return self._json(200, {"coletas": rows})
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
        if urlparse(self.path).path != "/api/v1/admin/inmet/sincronizar":
            return self._json(404, {"erro": "rota não encontrada"})
        recebido = self.headers.get("Authorization", "")
        esperado = f"Bearer {ADMIN_TOKEN}"
        if not ADMIN_TOKEN or not hmac.compare_digest(recebido, esperado):
            return self._json(401, {"erro": "credencial administrativa inválida"})
        if not sync_lock.acquire(blocking=False):
            return self._json(409, {"erro": "sincronização já está em andamento"})
        try:
            resultado = sincronizar_inmet(DB_URL, acionamento="api")
            return self._json(502 if resultado.get("erro") else 200, resultado)
        finally:
            sync_lock.release()


if __name__ == "__main__":
    host = os.environ.get("METIS_HOST", "0.0.0.0")
    port = int(os.environ.get("METIS_PORT", "8080"))
    print(f"MÉTIS web/API em http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), MetisHandler).serve_forever()
