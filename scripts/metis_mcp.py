#!/usr/bin/env python3
"""
MÉTIS — Servidor MCP (Model Context Protocol 2025-11-25)
Suporta transporte stdio (clientes locais) e Streamable HTTP (/mcp para ChatGPT/túneis),
com modo somente leitura por padrão e escrita candidata opt-in.
"""

import argparse
import hmac
import json
import os
import sys
import threading
import uuid
from collections import OrderedDict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from metis_ops import (  # noqa: E402
    DomainError,
    SchemaValidationError,
    catalog,
    execute_operation,
    json_safe,
)

PROTOCOL = "2025-11-25"
SUPPORTED_PROTOCOLS = {"2025-11-25", "2025-06-18", "2025-03-26"}
MAX_INPUT_BYTES = 1_048_576
MAX_OUTPUT_BYTES = 8_388_608
MAX_DEPTH = 64
MAX_HTTP_SESSIONS = 128

SERVER_INSTRUCTIONS = (
    "MÉTIS é um laboratório científico aberto de resiliência agroterritorial (RS, 497 municípios). "
    "Os indicadores calculados (R, E, P, S) são hipóteses exploratórias não validadas empiricamente. "
    "Ranking competitivo entre municípios é estritamente proibido: realize confrontos intramunicipais "
    "ou análises de distribuição/sensibilidade paramétrica. R(t0) descreve capacidade basal; "
    "AdaptaBrasil e INMET atuam como evidências externas de estresse. Escritas exigem --allow-writes, "
    "request_id UUID estável e limitacoes declaradas, criando apenas propostas candidatas pendentes de revisão."
)


def _rpc_error(ident, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": message}}


def _tool_result(value: dict, failed: bool = False) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(json_safe(value), ensure_ascii=False)}],
        "isError": failed,
    }


def _check_depth(obj, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise ValueError("MCP nesting exceeds 64")
    if isinstance(obj, dict):
        for v in obj.values():
            _check_depth(v, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _check_depth(item, depth + 1)


def parse_mcp_json(raw: str) -> dict | list:
    data = json.loads(raw)
    _check_depth(data)
    return data


def _cap_response(response: dict | None) -> dict | None:
    if response is None:
        return None
    serialized = json.dumps(response, ensure_ascii=False).encode("utf-8")
    if len(serialized) > MAX_OUTPUT_BYTES:
        return {
            "jsonrpc": "2.0",
            "id": response.get("id"),
            "result": _tool_result(
                {
                    "code": "RESULT_TOO_LARGE",
                    "message": "Resultado excede 8 MiB; use filtros ou paginação menor.",
                },
                failed=True,
            ),
        }
    return response


def constant_time_equals(a: str, b: str) -> bool:
    return bool(a) and bool(b) and hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def check_mcp_http_auth(headers, path: str, expected_token: str) -> bool:
    if not expected_token:
        return True
    path_token = ""
    if path.startswith("/mcp/"):
        candidate = path[5:]
        if "/" not in candidate:
            path_token = candidate
    auth = headers.get("Authorization", "") if headers else ""
    bearer = auth[7:] if len(auth) > 7 and auth[:7].lower() == "bearer " else ""
    return constant_time_equals(bearer, expected_token) or constant_time_equals(path_token, expected_token)


class MCPSession:
    def __init__(self, db_url: str, allow_writes: bool = False, auto_ready: bool = False):
        self.db_url = db_url
        self.allow_writes = allow_writes
        self.auto_ready = auto_ready
        self.initialized = False
        self.ready = auto_ready
        self.client_name = "unknown"
        self.lock = threading.Lock()

    def set_default_client_name(self, name: str) -> None:
        with self.lock:
            if name and name != "unknown":
                self.client_name = name

    def handle(self, message) -> dict | None:
        ident = message.get("id") if isinstance(message, dict) else None
        if (
            not isinstance(message, dict)
            or message.get("jsonrpc") != "2.0"
            or not isinstance(message.get("method"), str)
            or ("id" in message and (isinstance(ident, bool) or not isinstance(ident, (str, int))))
        ):
            return _rpc_error(None, -32600, "Invalid Request")

        notification = "id" not in message
        method = message["method"]
        params = message.get("params", {})
        if not isinstance(params, dict):
            return None if notification else _rpc_error(ident, -32602, "Params must be an object")

        if notification:
            if method == "notifications/initialized":
                with self.lock:
                    if self.initialized:
                        self.ready = True
            return None

        if method == "initialize":
            with self.lock:
                if self.initialized and not self.auto_ready:
                    return _rpc_error(ident, -32600, "Session already initialized")
                proto = params.get("protocolVersion")
                caps = params.get("capabilities")
                cinfo = params.get("clientInfo")
                if not isinstance(proto, str) or not isinstance(caps, dict) or not isinstance(cinfo, dict):
                    return _rpc_error(ident, -32602, "Expected protocolVersion, capabilities and clientInfo")
                cname = cinfo.get("name")
                cver = cinfo.get("version")
                if not isinstance(cname, str) or not (1 <= len(cname.encode("utf-8")) <= 100):
                    return _rpc_error(ident, -32602, "Client name must be 1..100 UTF-8 bytes")
                if any(ord(c) < 32 or ord(c) == 127 for c in cname):
                    return _rpc_error(ident, -32602, "Invalid client name")
                if not self.auto_ready and not isinstance(cver, str):
                    return _rpc_error(ident, -32602, "Expected clientInfo.version")

                self.client_name = cname
                negotiated = proto if (self.auto_ready and proto in SUPPORTED_PROTOCOLS) else PROTOCOL
                self.initialized = True
                self.ready = self.auto_ready
            return {
                "jsonrpc": "2.0",
                "id": ident,
                "result": {
                    "protocolVersion": negotiated,
                    "serverInfo": {"name": "metis", "version": "0.3.0"},
                    "capabilities": {"tools": {}},
                    "instructions": SERVER_INSTRUCTIONS,
                },
            }

        if method == "ping":
            return {"jsonrpc": "2.0", "id": ident, "result": {}}

        with self.lock:
            is_ready = self.ready
            cname_snap = self.client_name
            writes_snap = self.allow_writes

        if not is_ready:
            return _rpc_error(ident, -32000, "Initialize session first")

        if method == "tools/list":
            for key in params:
                if key != "_meta":
                    return _rpc_error(ident, -32602, "This catalogue is a single page; no cursor")
            return {"jsonrpc": "2.0", "id": ident, "result": {"tools": catalog(writes_snap)}}

        if method == "tools/call":
            for key in params:
                if key not in ("name", "arguments", "_meta"):
                    return _rpc_error(ident, -32602, "Unknown tools/call parameter")
            name = params.get("name")
            if not isinstance(name, str) or not name:
                return _rpc_error(ident, -32602, "Tool name required")
            args = params.get("arguments")
            try:
                value = execute_operation(
                    self.db_url,
                    name,
                    args,
                    {"allow_writes": writes_snap, "client_name": cname_snap},
                )
                return {"jsonrpc": "2.0", "id": ident, "result": _tool_result(value, failed=False)}
            except SchemaValidationError as exc:
                return _rpc_error(ident, -32602, str(exc))
            except DomainError as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": ident,
                    "result": _tool_result({"code": exc.code, "message": exc.message}, failed=True),
                }
            except Exception as exc:
                print(f"MCP internal error: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                return _rpc_error(ident, -32603, "Internal error")

        return _rpc_error(ident, -32601, "Method not found")


class MCPHTTPDispatcher:
    """Dispatcher Streamable HTTP compatível com ChatGPT (com sessão e fallback stateless)."""

    def __init__(self, db_url: str, allow_writes: bool = False):
        self.db_url = db_url
        self.allow_writes = allow_writes
        self._lock = threading.Lock()
        self._sessions: OrderedDict[str, MCPSession] = OrderedDict()
        self._fallback = MCPSession(db_url, allow_writes=allow_writes, auto_ready=True)

    def close_session(self, session_id: str | None) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)

    def dispatch(self, raw_body: bytes, session_id: str | None = None) -> tuple[dict | None, str | None]:
        if len(raw_body) > MAX_INPUT_BYTES:
            return _rpc_error(None, -32600, "MCP message exceeds 1 MiB"), session_id
        try:
            message = parse_mcp_json(raw_body.decode("utf-8"))
        except Exception:
            return _rpc_error(None, -32700, "Parse error"), session_id

        is_init = isinstance(message, dict) and message.get("method") == "initialize"
        active_sid = session_id or ""
        with self._lock:
            if is_init:
                if not active_sid:
                    active_sid = uuid.uuid4().hex
                if active_sid in self._sessions:
                    self._sessions.move_to_end(active_sid)
                elif len(self._sessions) >= MAX_HTTP_SESSIONS:
                    self._sessions.popitem(last=False)
                session = MCPSession(self.db_url, allow_writes=self.allow_writes, auto_ready=True)
                self._sessions[active_sid] = session
            else:
                session = self._sessions.get(active_sid) if active_sid else None
                if session is None:
                    session = self._fallback
                else:
                    self._sessions.move_to_end(active_sid)

        response = session.handle(message)
        cname = session.client_name if is_init else ""
        if is_init and cname:
            self._fallback.set_default_client_name(cname)
        return _cap_response(response), (active_sid or None)


def serve_stdio(db_url: str, allow_writes: bool = False) -> int:
    session = MCPSession(db_url, allow_writes=allow_writes, auto_ready=False)
    while True:
        raw_line = sys.stdin.buffer.readline(MAX_INPUT_BYTES + 2)
        if not raw_line:
            break
        if len(raw_line) > MAX_INPUT_BYTES + 1 or (len(raw_line) == MAX_INPUT_BYTES + 1 and not raw_line.endswith(b"\n")):
            print("MCP input exceeds 1 MiB limit", file=sys.stderr, flush=True)
            return 1
        line = raw_line.rstrip(b"\r\n")
        try:
            message = parse_mcp_json(line.decode("utf-8"))
            response = session.handle(message)
        except Exception:
            response = _rpc_error(None, -32700, "Parse error")
        capped = _cap_response(response)
        if capped is not None:
            sys.stdout.write(json.dumps(capped, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MÉTIS MCP stdio server")
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis"),
        help="URL PostgreSQL/PostGIS do MÉTIS",
    )
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        default=os.environ.get("METIS_MCP_ALLOW_WRITES", "0") == "1",
        help="Habilita escrita candidata (propose_investigation_note)",
    )
    args = parser.parse_args()
    return serve_stdio(args.db_url, allow_writes=args.allow_writes)


if __name__ == "__main__":
    sys.exit(main())
