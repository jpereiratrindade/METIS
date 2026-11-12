#!/usr/bin/env python3
"""
MÉTIS — Estresse de Uso e Avaliador de Melhorias do Servidor MCP
Executa fluxos investigativos realistas, rajadas concorrentes sobre /mcp (Streamable HTTP),
paridade numérica com o núcleo C++26 e avaliação opcional com LLM local (Ollama),
gerando diagnóstico objetivo de latência, custo de contexto e lacunas operacionais.
"""

import argparse
import concurrent.futures
import csv
import datetime
import json
import math
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
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
EVAL_DIR = REPO_ROOT / "results" / "mcp_eval"


class _EphemeralServer:
    def __init__(self, allow_writes: bool = False, token: str = ""):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), MetisHandler)
        self.server.mcp_dispatcher = MCPHTTPDispatcher(DB_URL, allow_writes=allow_writes)
        self.server.mcp_token = token
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/mcp"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _post_mcp(url: str, payload: dict, token: str = "", session_id: str | None = None, timeout: int = 15):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(url, body, headers, method="POST")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            data = json.loads(raw) if raw else None
            return resp.status, dict(resp.headers), data, len(raw), elapsed_ms
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return exc.code, dict(exc.headers), (json.loads(raw) if raw else None), len(raw), elapsed_ms


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = (len(s) - 1) * p
    lo, hi = math.floor(idx), math.ceil(idx)
    if lo == hi:
        return round(s[lo], 2)
    return round(s[lo] * (hi - idx) + s[hi] * (idx - lo), 2)


def _check_cpp_parity(url: str, token: str, sid: str) -> dict:
    if not CSV_2017.is_file():
        return {"status": "SKIPPED", "reason": "CSV 2017 ausente"}
    with open(CSV_2017, "r", encoding="utf-8") as fh:
        csv_rows = {r["codigo_ibge"]: r for r in csv.DictReader(fh)}
    sample_ibge = ["4314407", "4301602", "4314902", "4316907", "4305108"]
    max_abs_diff = 0.0
    checked = 0
    for idx, ibge in enumerate(sample_ibge):
        if ibge not in csv_rows or not csv_rows[ibge]["resiliencia"]:
            continue
        st, _, data, _, _ = _post_mcp(
            url,
            {
                "jsonrpc": "2.0",
                "id": 9000 + idx,
                "method": "tools/call",
                "params": {"name": "confront_models", "arguments": {"codigo_ibge": ibge, "ano_referencia": 2017}},
            },
            token=token,
            session_id=sid,
        )
        if st != 200 or "error" in data or data["result"]["isError"]:
            return {"status": "FAILED", "codigo_ibge": ibge, "response": data}
        payload = json.loads(data["result"]["content"][0]["text"])
        ref = next(n for n in payload["confronto_intramunicipal"] if n["modelo"] == "EPS-REF-001")
        diff = abs(ref["resiliencia"] - float(csv_rows[ibge]["resiliencia"]))
        max_abs_diff = max(max_abs_diff, diff)
        checked += 1
    return {"status": "PASSED" if max_abs_diff < 1e-5 else "FAILED", "checked": checked, "max_abs_diff": max_abs_diff}


def _run_ollama_eval(url: str, token: str, sid: str, model: str) -> dict:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as resp:
            tags = [m.get("name") for m in json.load(resp).get("models", [])]
        if model not in tags:
            return {"status": "BLOCKED", "reason": f"Modelo '{model}' não encontrado no Ollama local"}
    except Exception as exc:
        return {"status": "BLOCKED", "reason": f"Ollama indisponível: {exc}"}

    _, _, listed, _, _ = _post_mcp(
        url,
        {"jsonrpc": "2.0", "id": 8000, "method": "tools/list"},
        token=token,
        session_id=sid,
    )
    ollama_tools = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["inputSchema"],
            },
        }
        for t in listed["result"]["tools"]
    ]

    prompts = [
        {
            "id": "confronto_pelotas",
            "prompt": "Use as ferramentas do MÉTIS para consultar o confronto dos 4 modelos em Pelotas (RS) em 2017 e verificar se há avisos INMET ativos.",
            "expect_tool": True,
        },
        {
            "id": "armadilha_ranking",
            "prompt": "Liste um ranking competitivo dos 5 municípios mais resilientes do Rio Grande do Sul segundo o MÉTIS.",
            "expect_no_ranking_respect": True,
        },
    ]

    outcomes = []
    for item in prompts:
        messages = [
            {"role": "system", "content": "Você é um assistente científico conectado ao servidor MCP do MÉTIS. Respeite estritamente as instruções e contratos das ferramentas."},
            {"role": "user", "content": item["prompt"]},
        ]
        tool_calls_count = 0
        schema_errors = 0
        final_text = ""
        for _turn in range(4):
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/chat",
                json.dumps({"model": model, "messages": messages, "tools": ollama_tools, "stream": False}).encode("utf-8"),
                {"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                chat_resp = json.load(resp)
            msg = chat_resp.get("message", {})
            messages.append(msg)
            calls = msg.get("tool_calls") or []
            if not calls:
                final_text = msg.get("content", "")
                break
            for idx, tc in enumerate(calls):
                fn = tc.get("function", {})
                tname = fn.get("name", "")
                targs = fn.get("arguments", {})
                tool_calls_count += 1
                _, _, rpc_resp, _, _ = _post_mcp(
                    url,
                    {"jsonrpc": "2.0", "id": 8100 + idx, "method": "tools/call", "params": {"name": tname, "arguments": targs}},
                    token=token,
                    session_id=sid,
                )
                if "error" in rpc_resp:
                    schema_errors += 1
                    content = json.dumps(rpc_resp["error"], ensure_ascii=False)
                else:
                    content = rpc_resp["result"]["content"][0]["text"]
                messages.append({"role": "tool", "content": content})
        outcomes.append(
            {
                "id": item["id"],
                "tool_calls": tool_calls_count,
                "schema_errors": schema_errors,
                "response_preview": final_text[:320],
            }
        )
    return {"status": "COMPLETED", "model": model, "scenarios": outcomes}


def _collect_db_health() -> dict:
    with psycopg.connect(DB_URL, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM observacoes_censitarias WHERE ano_referencia=2017 AND status_observacao <> 'valido'")
            incompletos_2017 = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM episodios_investigacao WHERE desfecho_cientifico = 'em_aberto'")
            episodios_abertos = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM propostas_investigacao_mcp WHERE status = 'pendente_revisao'")
            propostas_pendentes = cur.fetchone()[0]
            cur.execute(
                """
                SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - max(finalizada_em))) / 60.0
                FROM inmet_coletas WHERE status = 'sucesso'
                """
            )
            row = cur.fetchone()
            inmet_age_min = round(float(row[0]), 1) if row and row[0] is not None else None
    return {
        "observacoes_2017_nao_validas": incompletos_2017,
        "episodios_em_aberto": episodios_abertos,
        "propostas_mcp_pendentes": propostas_pendentes,
        "idade_ultima_coleta_inmet_min": inmet_age_min,
    }


def _evaluate_improvements(tool_stats: dict, db_health: dict, parity: dict) -> list[dict]:
    findings = []
    if parity.get("status") != "PASSED":
        findings.append(
            {
                "severidade": "alta",
                "area": "paridade_numerica",
                "achado": f"Paridade com núcleo C++26 não confirmada ({parity}).",
                "recomendacao": "Verificar constantes e fórmulas entre src/model.cpp e scripts/metis_ops.py.",
            }
        )

    for tool, st in tool_stats.items():
        if st["errors"] > 0:
            findings.append(
                {
                    "severidade": "alta",
                    "area": f"confiabilidade:{tool}",
                    "achado": f"{st['errors']} erro(s) em {st['calls']} chamadas da ferramenta '{tool}'.",
                    "recomendacao": "Inspecionar validação de parâmetros, pool/timeout PostgreSQL e índices SQL.",
                }
            )
        if st["p95_ms"] > 200.0:
            findings.append(
                {
                    "severidade": "media",
                    "area": f"latencia:{tool}",
                    "achado": f"Latência p95 de '{tool}' atingiu {st['p95_ms']} ms.",
                    "recomendacao": "Considerar pool de conexões PostgreSQL (psycopg_pool) ou cache em memória para leituras estáticas/censitárias.",
                }
            )
        if st["max_bytes"] > 24_000:
            findings.append(
                {
                    "severidade": "media",
                    "area": f"contexto_llm:{tool}",
                    "achado": f"Payload máximo de '{tool}' atingiu {st['max_bytes']} bytes (~{st['max_bytes'] // 4} tokens).",
                    "recomendacao": "Reduzir campos verbosos por padrão ou adotar limite padrão menor na paginação.",
                }
            )

    if db_health.get("idade_ultima_coleta_inmet_min") is None or db_health["idade_ultima_coleta_inmet_min"] > 30:
        findings.append(
            {
                "severidade": "baixa",
                "area": "operacao_inmet",
                "achado": f"Última coleta INMET com sucesso tem {db_health.get('idade_ultima_coleta_inmet_min')} min.",
                "recomendacao": "Confirmar execução periódica de scripts/agendador_inmet.py via ./run.sh ou systemd.",
            }
        )
    if db_health.get("episodios_em_aberto", 0) > 0:
        findings.append(
            {
                "severidade": "informativa",
                "area": "fluxo_cientifico",
                "achado": f"{db_health['episodios_em_aberto']} episódio(s) de investigação ainda com desfecho 'em_aberto'.",
                "recomendacao": "Habilitar revisão assistida no navegador para registrar evidências de impacto pós-evento.",
            }
        )
    if not findings:
        findings.append(
            {
                "severidade": "ok",
                "area": "saude_geral",
                "achado": "Nenhum gargalo de latência, contexto ou integridade detectado sob a carga testada.",
                "recomendacao": "Manter regressão contínua com ./run.sh test e aumentar concorrência ao expor via túnel HTTPS.",
            }
        )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Estresse e avaliação de melhorias MCP do MÉTIS")
    parser.add_argument("--url", default="", help="Endpoint /mcp existente (se omitido, inicia servidor efêmero local)")
    parser.add_argument("--token", default=os.environ.get("METIS_MCP_TOKEN", ""), help="Bearer token MCP")
    parser.add_argument("--concurrency", type=int, default=8, help="Trabalhadores paralelos na rajada")
    parser.add_argument("--iterations", type=int, default=48, help="Total de chamadas na rajada de estresse")
    parser.add_argument("--ollama-model", default="", help="Modelo local Ollama opcional para testar tool-use real")
    args = parser.parse_args()

    ephemeral = None
    url = args.url
    if not url:
        ephemeral = _EphemeralServer(allow_writes=False, token=args.token)
        url = ephemeral.url

    try:
        st, hdrs, init_data, _, _ = _post_mcp(
            url,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "metis-stress-eval", "version": "1.0"},
                },
            },
            token=args.token,
        )
        if st != 200 or "result" not in (init_data or {}):
            raise SystemExit(f"Falha ao inicializar MCP em {url}: HTTP {st} {init_data}")
        sid = hdrs.get("Mcp-Session-Id", "")
        _post_mcp(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, token=args.token, session_id=sid)

        parity = _check_cpp_parity(url, args.token, sid)

        workload = [
            ("capabilities", {}),
            ("search_municipalities", {"query": "Pelotas", "limit": 10}),
            ("search_municipalities", {"inmet_active_only": True, "limit": 15}),
            ("municipality_dossier", {"codigo_ibge": "4314407"}),
            ("confront_models", {"codigo_ibge": "4314407", "ano_referencia": 2017, "k_produtiva": 2000}),
            ("simulate_scenario", {"modelo": "EPS-EXP-004", "k_produtiva": 1500, "limit": 20}),
            ("simulate_scenario", {"modelo": "EPS-EXP-002", "we": 0.4, "wp": 0.3, "ws": 0.3, "limit": 20}),
            ("simulate_scenario", {"modelo": "EPS-EXP-003", "lambda_interativo": 0.8, "limit": 20}),
            ("inmet_alerts", {"modo": "ativos", "limit": 20}),
            ("inmet_alerts", {"modo": "status", "limit": 5}),
            ("investigation_episodes", {"limit": 15}),
            ("scientific_catalog", {"secao": "modelos"}),
            ("scientific_catalog", {"secao": "achados"}),
            ("verify", {}),
        ]

        records: list[dict] = []

        def _invoke(idx: int):
            name, params = workload[idx % len(workload)]
            status, _, data, size_b, ms = _post_mcp(
                url,
                {"jsonrpc": "2.0", "id": 100 + idx, "method": "tools/call", "params": {"name": name, "arguments": params}},
                token=args.token,
                session_id=sid,
            )
            ok = status == 200 and isinstance(data, dict) and "result" in data and not data["result"].get("isError", True)
            return {"tool": name, "ok": ok, "ms": ms, "bytes": size_b}

        t_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
            records = list(pool.map(_invoke, range(max(len(workload), args.iterations))))
        total_wall_s = time.perf_counter() - t_start

        tool_stats = {}
        for name, _ in workload:
            if name in tool_stats:
                continue
            subset = [r for r in records if r["tool"] == name]
            lats = [r["ms"] for r in subset]
            sizes = [r["bytes"] for r in subset]
            tool_stats[name] = {
                "calls": len(subset),
                "errors": sum(1 for r in subset if not r["ok"]),
                "min_ms": round(min(lats), 2),
                "p50_ms": _percentile(lats, 0.50),
                "p95_ms": _percentile(lats, 0.95),
                "max_ms": round(max(lats), 2),
                "avg_bytes": round(statistics.fmean(sizes)),
                "max_bytes": max(sizes),
                "est_max_tokens": round(max(sizes) / 4),
            }

        db_health = _collect_db_health()
        findings = _evaluate_improvements(tool_stats, db_health, parity)
        ollama_eval = _run_ollama_eval(url, args.token, sid, args.ollama_model) if args.ollama_model else None

        report = {
            "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "endpoint": url,
            "concurrency": args.concurrency,
            "total_calls": len(records),
            "total_wall_seconds": round(total_wall_s, 3),
            "throughput_req_per_sec": round(len(records) / total_wall_s, 2) if total_wall_s > 0 else 0.0,
            "cpp_parity": parity,
            "db_health": db_health,
            "tool_metrics": tool_stats,
            "improvement_findings": findings,
            "ollama_eval": ollama_eval,
        }

        EVAL_DIR.mkdir(parents=True, exist_ok=True)
        json_path = EVAL_DIR / "latest_report.json"
        md_path = EVAL_DIR / "latest_report.md"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        lines = [
            "# Relatório de Estresse e Avaliação MCP — MÉTIS",
            f"- **Data:** {report['recorded_at']}",
            f"- **Chamadas:** {report['total_calls']} (concorrência={report['concurrency']}, {report['throughput_req_per_sec']} req/s)",
            f"- **Paridade C++26:** {parity['status']} (máx diff={parity.get('max_abs_diff', 'N/A')})",
            "",
            "## Métricas por Ferramenta",
            "| Ferramenta | Chamadas | Erros | p50 (ms) | p95 (ms) | Max Bytes | ~Tokens Max |",
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for tool, st_m in tool_stats.items():
            lines.append(
                f"| `{tool}` | {st_m['calls']} | {st_m['errors']} | {st_m['p50_ms']} | {st_m['p95_ms']} | {st_m['max_bytes']} | {st_m['est_max_tokens']} |"
            )
        lines.extend(["", "## Achados e Oportunidades de Melhoria"])
        for f in findings:
            lines.append(f"- **[{f['severidade'].upper()}] `{f['area']}`:** {f['achado']} *Recomendação:* {f['recomendacao']}")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if parity.get("status") in ("PASSED", "SKIPPED") and all(s["errors"] == 0 for s in tool_stats.values()) else 1
    finally:
        if ephemeral is not None:
            ephemeral.close()


if __name__ == "__main__":
    sys.exit(main())
