#!/usr/bin/env python3
"""
MÉTIS — Suíte de Testes MCP (stdio + Streamable HTTP)
Segue o padrão NOESE/tests/mcp.py: ciclo de vida, contratos estritos, modo somente leitura,
idempotência de propostas, paridade numérica com C++26 e concorrência HTTP/stdio.
"""

import concurrent.futures
import csv
import json
import math
import os
import select
import socket
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

import psycopg

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.api_server import MetisHandler  # noqa: E402
from scripts.metis_mcp import MCPHTTPDispatcher  # noqa: E402

DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")
CSV_2017 = REPO_ROOT / "results" / "RS_497_RESULTADOS.csv"
MCP_SCRIPT = REPO_ROOT / "scripts" / "mcp.sh"


def _db_available() -> bool:
    try:
        with psycopg.connect(DB_URL, connect_timeout=2):
            return True
    except Exception:
        return False


DB_OK = _db_available()


class StdioMCPClient:
    def __init__(self, allow_writes: bool = False, name: str = "test-client", initialize: bool = True):
        cmd = [str(MCP_SCRIPT)]
        if allow_writes:
            cmd.append("--allow-writes")
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(REPO_ROOT),
        )
        self.ident = 0
        if initialize:
            resp = self.rpc(
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": name, "version": "1.0"},
                },
            )
            assert resp["result"]["protocolVersion"] == "2025-11-25", resp
            self.notify("notifications/initialized")

    def send(self, message):
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n")
        self.proc.stdin.flush()

    def receive(self):
        if not select.select([self.proc.stdout], [], [], 10)[0]:
            raise AssertionError("Sem resposta MCP em 10s")
        line = self.proc.stdout.readline()
        if not line:
            raise AssertionError("MCP encerrou: " + self.proc.stderr.read().decode("utf-8", errors="replace"))
        return json.loads(line)

    def rpc(self, method: str, params=None):
        self.ident += 1
        self.send({"jsonrpc": "2.0", "id": self.ident, "method": method, "params": params if params is not None else {}})
        resp = self.receive()
        assert resp["id"] == self.ident, resp
        return resp

    def notify(self, method: str):
        self.send({"jsonrpc": "2.0", "method": method})

    def call(self, name: str, args=None):
        return self.rpc("tools/call", {"name": name, "arguments": args if args is not None else {}})

    def value(self, name: str, args=None):
        resp = self.call(name, args)
        assert "error" not in resp, resp
        res = resp["result"]
        assert not res["isError"], res
        return json.loads(res["content"][0]["text"])

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=8)
        stderr = self.proc.stderr.read()
        self.proc.stdout.close()
        self.proc.stderr.close()
        assert self.proc.returncode == 0, stderr

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class _TestHTTPServer:
    def __init__(self, allow_writes: bool = False, mcp_token: str = ""):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), MetisHandler)
        self.server.mcp_dispatcher = MCPHTTPDispatcher(DB_URL, allow_writes=allow_writes)
        self.server.mcp_token = mcp_token
        port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def request(self, path: str, payload=None, method: str = "POST", headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        req_headers = {"Content-Type": "application/json"} if payload is not None else {}
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(self.url + path, body, req_headers, method=method)
        try:
            resp = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as exc:
            resp = exc
        with resp:
            raw = resp.read()
            return resp.status, dict(resp.headers), (json.loads(raw) if raw else None)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


@unittest.skipUnless(DB_OK, "PostgreSQL MÉTIS indisponível para testes MCP")
class TestMetisMCP(unittest.TestCase):
    def setUp(self):
        self.created_request_ids: list[str] = []

    def tearDown(self):
        if self.created_request_ids:
            with psycopg.connect(DB_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM propostas_investigacao_mcp WHERE request_id = ANY(%s::uuid[])",
                        (self.created_request_ids,),
                    )
                conn.commit()

    def test_lifecycle_and_notifications(self):
        with StdioMCPClient(initialize=False) as c:
            self.assertEqual(c.rpc("tools/list")["error"]["code"], -32000)
            self.assertEqual(c.rpc("ping")["result"], {})
            self.assertEqual(c.rpc("initialize")["error"]["code"], -32602)
            init = c.rpc(
                "initialize",
                {
                    "protocolVersion": "unsupported-version",
                    "capabilities": {},
                    "clientInfo": {"name": "metis-test", "version": "1.0"},
                },
            )
            self.assertEqual(init["result"]["protocolVersion"], "2025-11-25")
            self.assertEqual(c.rpc("tools/list")["error"]["code"], -32000)
            c.notify("notifications/initialized")
            c.notify("unknown-notification")
            self.assertIn("tools", c.rpc("tools/list")["result"])
            self.assertEqual(c.rpc("initialize")["error"]["code"], -32600)
            self.assertEqual(c.rpc("unknown-method")["error"]["code"], -32601)

    def test_readonly_catalog_and_write_denial(self):
        with StdioMCPClient(allow_writes=False) as c:
            tools = c.rpc("tools/list")["result"]["tools"]
            self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in tools))
            self.assertNotIn("propose_investigation_note", [t["name"] for t in tools])
            resp = c.call(
                "propose_investigation_note",
                {
                    "codigo_ibge": "4314407",
                    "texto": "Tentativa sem permissão",
                    "limitacoes": "Teste de fronteira de autoridade.",
                    "request_id": str(uuid.uuid4()),
                },
            )
            self.assertTrue(resp["result"]["isError"])
            self.assertEqual(json.loads(resp["result"]["content"][0]["text"])["code"], "AUTHORITY_REQUIRED")

    def test_contracts_and_bad_protocol_input(self):
        with StdioMCPClient() as c:
            bad_calls = [
                ("search_municipalities", {"limit": True}),
                ("search_municipalities", {"limit": 0}),
                ("search_municipalities", {"unknown": 1}),
                ("municipality_dossier", {"codigo_ibge": "123"}),
                ("confront_models", {"codigo_ibge": "4314407", "k_produtiva": -10}),
                ("confront_models", {"codigo_ibge": "4314407", "ano_referencia": 2020}),
                ("missing_tool", {}),
            ]
            for name, args in bad_calls:
                with self.subTest(name=name, args=args):
                    self.assertEqual(c.call(name, args)["error"]["code"], -32602)

            c.send([])
            self.assertEqual(c.receive()["error"]["code"], -32600)
            c.send({"jsonrpc": "2.0", "id": True, "method": "ping"})
            self.assertEqual(c.receive()["error"]["code"], -32600)
            c.proc.stdin.write(b"{broken\n")
            c.proc.stdin.flush()
            self.assertEqual(c.receive()["error"]["code"], -32700)
            c.proc.stdin.write(("[" * 70 + "0" + "]" * 70 + "\n").encode("utf-8"))
            c.proc.stdin.flush()
            self.assertEqual(c.receive()["error"]["code"], -32700)
            self.assertEqual(c.rpc("ping")["result"], {})

    def test_bounded_input_stdio_rejects_over_1mib(self):
        res = subprocess.run(
            [str(MCP_SCRIPT)],
            input=b"x" * (1024 * 1024 + 1) + b"\n",
            capture_output=True,
            timeout=8,
            cwd=str(REPO_ROOT),
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertEqual(res.stdout, b"")
        self.assertIn(b"1 MiB", res.stderr)

    def test_numeric_parity_with_cpp_results_and_dossier(self):
        with open(CSV_2017, "r", encoding="utf-8") as fh:
            csv_rows = {row["codigo_ibge"]: row for row in csv.DictReader(fh)}

        with StdioMCPClient() as c:
            caps = c.value("capabilities")
            self.assertEqual(caps["municipios_rs"], 497)
            self.assertTrue(caps["regras_epistemicas"]["ranking_competitivo_proibido"])

            verified = c.value("verify")
            self.assertEqual(verified["integridade_tecnica"], "VERIFIED")
            self.assertEqual(verified["municipios_rs"], 497)

            # Confronto intramunicipal de Pelotas (4314407) e Bagé (4301602)
            for ibge in ("4314407", "4301602"):
                confronto = c.value("confront_models", {"codigo_ibge": ibge, "ano_referencia": 2017})
                ref_nota = next(n for n in confronto["confronto_intramunicipal"] if n["modelo"] == "EPS-REF-001")
                expected_r = float(csv_rows[ibge]["resiliencia"])
                self.assertTrue(math.isclose(ref_nota["resiliencia"], expected_r, abs_tol=1e-5))
                self.assertIn("trajetoria_2006_2017", confronto)

            sim = c.value("simulate_scenario", {"modelo": "EPS-EXP-004", "k_produtiva": 2000.0, "limit": 10})
            self.assertEqual(sim["sumario_estatistico"]["total_avaliados"], 497)
            self.assertEqual(len(sim["items"]), 10)
            self.assertEqual(sim["items"], sorted(sim["items"], key=lambda x: x["codigo_ibge"]))

            dossier = c.value("municipality_dossier", {"codigo_ibge": "4314407"})
            self.assertEqual(dossier["municipio"]["codigo_ibge"], "4314407")
            self.assertGreaterEqual(len(dossier["observacoes_censitarias"]), 2)

    def test_streamable_http_auth_idempotency_and_concurrency(self):
        secret = "metis-mcp-test-secret"
        srv = _TestHTTPServer(allow_writes=True, mcp_token=secret)
        try:
            st, _, err = srv.request("/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            self.assertEqual(st, 401)
            self.assertEqual(err["code"], "AUTHORITY_REQUIRED")

            st, hdrs, _ = srv.request("/mcp", method="OPTIONS")
            self.assertEqual(st, 204)
            self.assertIn("POST", hdrs.get("Allow", ""))

            st, _, _ = srv.request("/mcp", method="GET")
            self.assertEqual(st, 405)

            st, _, tools_meta = srv.request("/api/v1/tools", method="GET")
            self.assertEqual(st, 200)
            self.assertTrue(tools_meta["http_writes"])
            self.assertTrue(tools_meta["http_auth"])

            auth = {"Authorization": f"Bearer {secret}", "Host": "tunnel.example.com"}
            st, hdrs, init = srv.request(
                "/mcp",
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "chatgpt-tunnel", "version": "1.0"},
                    },
                },
                headers=auth,
            )
            self.assertEqual(st, 200)
            self.assertEqual(init["result"]["protocolVersion"], "2025-06-18")
            sid = hdrs.get("Mcp-Session-Id")
            self.assertTrue(sid)

            st, _, empty = srv.request(
                "/mcp",
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers={**auth, "Mcp-Session-Id": sid},
            )
            self.assertEqual(st, 202)
            self.assertIsNone(empty)

            # Idempotência + origem mcp:chatgpt-tunnel + conflito
            rid = str(uuid.uuid4())
            self.created_request_ids.append(rid)
            note_args = {
                "codigo_ibge": "4314407",
                "tipo": "hipotese_parametro",
                "modelo_id": "EPS-EXP-004",
                "parametros": {"k_produtiva": 2000},
                "texto": "Sensibilidade paramétrica observada em Pelotas.",
                "limitacoes": "Ensaio sintético automatizado sem validação de campo.",
                "request_id": rid,
            }
            st, _, created = srv.request(
                "/mcp",
                {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "propose_investigation_note", "arguments": note_args}},
                headers={**auth, "Mcp-Session-Id": sid},
            )
            self.assertEqual(st, 200)
            prop = json.loads(created["result"]["content"][0]["text"])
            self.assertEqual(prop["origem_cliente"], "mcp:chatgpt-tunnel")
            self.assertEqual(prop["status"], "pendente_revisao")

            # Replay via path-token sem header Authorization
            st, _, replay = srv.request(
                f"/mcp/{secret}",
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "propose_investigation_note", "arguments": note_args}},
                headers={"Host": "tunnel.example.com"},
            )
            self.assertEqual(st, 200)
            self.assertEqual(json.loads(replay["result"]["content"][0]["text"]), prop)

            # Conflito ao alterar texto mantendo o mesmo request_id
            st, _, conflict = srv.request(
                "/mcp",
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "propose_investigation_note", "arguments": {**note_args, "texto": "Texto alterado"}},
                },
                headers={**auth, "Mcp-Session-Id": sid},
            )
            self.assertEqual(st, 200)
            self.assertTrue(conflict["result"]["isError"])
            self.assertEqual(json.loads(conflict["result"]["content"][0]["text"])["code"], "CONFLICT")

            # Rajada concorrente sobre /mcp
            def _worker(idx: int):
                tool = "confront_models" if idx % 2 == 0 else "simulate_scenario"
                args = {"codigo_ibge": "4314407"} if tool == "confront_models" else {"modelo": "EPS-EXP-004", "limit": 5}
                s, _, r = srv.request(
                    "/mcp",
                    {"jsonrpc": "2.0", "id": 100 + idx, "method": "tools/call", "params": {"name": tool, "arguments": args}},
                    headers={**auth, "Mcp-Session-Id": sid},
                )
                return s, r["result"]["isError"]

            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(_worker, range(18)))
            self.assertTrue(all(s == 200 and not err for s, err in results))

            st, _, _ = srv.request("/mcp", method="DELETE", headers={**auth, "Mcp-Session-Id": sid})
            self.assertEqual(st, 204)
        finally:
            srv.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
