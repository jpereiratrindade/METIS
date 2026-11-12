#!/usr/bin/env python3
"""
MÉTIS — Operações de Domínio Compartilhadas para MCP (stdio + Streamable HTTP)
Segue o padrão NOESE/CONTINUUM: leitura por padrão, escrita opt-in com propostas
candidatas isoladas, idempotência por request_id UUID e proveniência de cliente.
"""

import hashlib
import json
import math
import os
import queue
import statistics
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLIC_API_DIR = os.path.join(REPO_ROOT, "web", "api", "public")

MODELO_REF_001 = "EPS-REF-001"
MODELO_EXP_002 = "EPS-EXP-002"
MODELO_EXP_003 = "EPS-EXP-003"
MODELO_EXP_004 = "EPS-EXP-004"
MODELOS_VALIDOS = (MODELO_REF_001, MODELO_EXP_002, MODELO_EXP_003, MODELO_EXP_004)

DEFAULT_Q10 = 7.27298934926942
DEFAULT_Q90 = 8.93207610159435
DEFAULT_K_PRODUTIVA = 1500.0
DEFAULT_WE = 0.33
DEFAULT_WP = 0.33
DEFAULT_WS = 0.34
DEFAULT_LAMBDA = 0.5


class SchemaValidationError(ValueError):
    """Erro de contrato/esquema JSON-RPC (-32602)."""


class DomainError(Exception):
    """Erro de domínio retornado em tools/call com isError=True."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def json_safe(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


def _ok_nonneg(val) -> bool:
    if val is None:
        return False
    f = float(val)
    return math.isfinite(f) and f >= 0.0


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _pontuar_municipio(obs: dict, modelo: str, params: dict) -> dict:
    """Replica fielmente resiliencia::pontuar de src/model.cpp."""
    k_prod = float(params.get("k_produtiva", DEFAULT_K_PRODUTIVA))
    if not math.isfinite(k_prod) or k_prod <= 0.0:
        raise SchemaValidationError("k_produtiva deve ser estritamente positivo")

    q10 = float(params.get("q10", DEFAULT_Q10))
    q90 = float(params.get("q90", DEFAULT_Q90))
    we = float(params.get("we", DEFAULT_WE))
    wp = float(params.get("wp", DEFAULT_WP))
    ws = float(params.get("ws", DEFAULT_WS))
    lam = float(params.get("lambda_interativo", DEFAULT_LAMBDA))

    base = {
        "codigo_ibge": obs["codigo_ibge"],
        "municipio": obs["municipio"],
        "ano_referencia": int(obs["ano_referencia"]),
        "modelo": modelo,
        "status": "dados_incompletos",
        "densidade_monetaria_ha": None,
        "ecologica_indice": None,
        "ecologica_multiplicador": None,
        "produtiva": None,
        "social": None,
        "resiliencia": None,
        "k_utilizado": k_prod,
    }

    area = obs.get("area_estabelecimentos_ha")
    past = obs.get("pastagem_natural_ha")
    mata = obs.get("mata_natural_ha")
    vp = obs.get("valor_producao_reais")
    estab = obs.get("estabelecimentos_total")
    orient = obs.get("estabelecimentos_orientacao_tecnica")
    assoc = obs.get("estabelecimentos_associados")

    if not (
        _ok_nonneg(area)
        and float(area) > 0.0
        and _ok_nonneg(past)
        and _ok_nonneg(mata)
        and _ok_nonneg(vp)
        and _ok_nonneg(estab)
        and float(estab) > 0.0
        and _ok_nonneg(orient)
        and _ok_nonneg(assoc)
    ):
        return base

    area_f = float(area)
    past_f = float(past)
    mata_f = float(mata)
    vp_f = float(vp)
    estab_f = float(estab)
    orient_f = float(orient)
    assoc_f = float(assoc)

    if past_f + mata_f > area_f + 1e-7 or orient_f > estab_f or assoc_f > estab_f:
        base["status"] = "inconsistencia"
        return base

    e0 = _clip((past_f + mata_f) / area_f, 0.0, 1.0)
    dm = vp_f / area_f
    soc_base = (orient_f + assoc_f) / estab_f

    if modelo == MODELO_REF_001:
        e_val = 0.5 + e0
        l_val = math.log1p(dm)
        p_val = 50.0 * _clip((l_val - q10) / (q90 - q10), 0.0, 1.0) if q90 > q10 else 0.0
        s_val = 25.0 * soc_base
        r_val = e_val * (p_val + s_val)
    elif modelo == MODELO_EXP_002:
        e_val = 100.0 * e0
        p_val = 100.0 * (dm / (dm + k_prod))
        s_val = 50.0 * soc_base
        r_val = we * e_val + wp * p_val + ws * s_val
    elif modelo == MODELO_EXP_003:
        e_val = 0.5 + e0
        p_val = 50.0 * (dm / (dm + k_prod))
        s_val = 25.0 * soc_base
        r_val = e_val * (p_val + s_val) + lam * (p_val * s_val / 50.0)
    else:
        e_val = 0.5 + e0
        p_val = 50.0 * (dm / (dm + k_prod))
        s_val = 25.0 * soc_base
        r_val = e_val * (p_val + s_val)

    base.update(
        {
            "status": "experimental",
            "densidade_monetaria_ha": round(dm, 6),
            "ecologica_indice": round(e0, 6),
            "ecologica_multiplicador": round(e_val, 6),
            "produtiva": round(p_val, 6),
            "social": round(s_val, 6),
            "resiliencia": round(r_val, 6),
        }
    )
    return base


def _confrontar_obs(obs: dict, params: dict) -> list[dict]:
    notas = [_pontuar_municipio(obs, mod, params) for mod in MODELOS_VALIDOS]
    ref_r = notas[0]["resiliencia"]
    for item in notas:
        if ref_r is not None and item["resiliencia"] is not None:
            item["delta_r_vs_ref"] = round(item["resiliencia"] - ref_r, 6)
        else:
            item["delta_r_vs_ref"] = None
    return notas


_POOL_LOCK = threading.Lock()
_POOLS: dict[str, queue.LifoQueue] = {}


def _get_pool(db_url: str) -> queue.LifoQueue:
    with _POOL_LOCK:
        pool = _POOLS.get(db_url)
        if pool is None:
            pool = queue.LifoQueue(maxsize=12)
            _POOLS[db_url] = pool
        return pool


@contextmanager
def _pooled_conn(db_url: str, autocommit: bool = True):
    pool = _get_pool(db_url)
    conn = None
    while True:
        try:
            candidate = pool.get_nowait()
        except queue.Empty:
            break
        if not candidate.closed:
            conn = candidate
            break
    if conn is None:
        conn = psycopg.connect(db_url, row_factory=dict_row, connect_timeout=5, autocommit=autocommit)
    else:
        if conn.autocommit != autocommit:
            conn.autocommit = autocommit
    try:
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if not conn.closed and not autocommit:
            try:
                conn.rollback()
            except Exception:
                pass
        if not conn.closed:
            try:
                conn.close()
            except Exception:
                pass
        conn = None
        raise
    finally:
        if conn is not None and not conn.closed:
            try:
                pool.put_nowait(conn)
            except queue.Full:
                conn.close()


def _query(db_url: str, sql: str, params=()) -> list[dict]:
    try:
        with _pooled_conn(db_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [json_safe(r) for r in cur.fetchall()]
    except psycopg.Error as exc:
        raise DomainError("DATABASE_UNAVAILABLE", f"Falha na consulta ao banco PostgreSQL: {exc}")


def _check_ibge(code: str) -> str:
    if not isinstance(code, str) or len(code) != 7 or not code.isdigit() or not code.startswith("43"):
        raise SchemaValidationError("codigo_ibge deve ser string numérica de 7 dígitos do RS (43xxxxx)")
    return code


def _check_uuid(value: str) -> str:
    if not isinstance(value, str):
        raise SchemaValidationError("request_id deve ser UUID string")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise SchemaValidationError("request_id inválido; forneça UUID v4 válido") from exc
    return str(parsed)


def _check_int(value, name: str, lo: int, hi: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaValidationError(f"{name} deve ser inteiro entre {lo} e {hi}")
    if value < lo or value > hi:
        raise SchemaValidationError(f"{name} fora do intervalo [{lo}, {hi}]")
    return value


def _check_num(value, name: str, gt: float | None = None, lo: float | None = None, hi: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaValidationError(f"{name} deve ser numérico")
    val = float(value)
    if not math.isfinite(val):
        raise SchemaValidationError(f"{name} deve ser número finito")
    if gt is not None and not (val > gt):
        raise SchemaValidationError(f"{name} deve ser > {gt}")
    if lo is not None and val < lo:
        raise SchemaValidationError(f"{name} deve ser >= {lo}")
    if hi is not None and val > hi:
        raise SchemaValidationError(f"{name} deve ser <= {hi}")
    return val


def _check_bool(value, name: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaValidationError(f"{name} deve ser booleano")
    return value


def _check_str(value, name: str, min_len: int = 0, max_len: int = 500) -> str:
    if not isinstance(value, str):
        raise SchemaValidationError(f"{name} deve ser string")
    if len(value) < min_len or len(value) > max_len:
        raise SchemaValidationError(f"{name} deve ter entre {min_len} e {max_len} caracteres")
    return value


def _validate_parametros(args: dict) -> dict:
    out = {}
    if "k_produtiva" in args:
        out["k_produtiva"] = _check_num(args["k_produtiva"], "k_produtiva", gt=0.0, hi=1_000_000.0)
    if "we" in args:
        out["we"] = _check_num(args["we"], "we", lo=0.0, hi=10.0)
    if "wp" in args:
        out["wp"] = _check_num(args["wp"], "wp", lo=0.0, hi=10.0)
    if "ws" in args:
        out["ws"] = _check_num(args["ws"], "ws", lo=0.0, hi=10.0)
    if "lambda_interativo" in args:
        out["lambda_interativo"] = _check_num(args["lambda_interativo"], "lambda_interativo", lo=-10.0, hi=10.0)
    return out


# ---------------------------------------------------------------------------
# Implementações das Operações
# ---------------------------------------------------------------------------

def op_capabilities(db_url: str, _args: dict, _ctx: dict) -> dict:
    stale_min = max(1, int(os.environ.get("METIS_INMET_STALE_MINUTES", "30")))
    muni_count = _query(db_url, "SELECT count(*) AS total FROM municipios WHERE uf='RS'")[0]["total"]
    anos = [
        r["ano_referencia"]
        for r in _query(db_url, "SELECT DISTINCT ano_referencia FROM observacoes_censitarias ORDER BY ano_referencia")
    ]
    adapta_inds = _query(db_url, "SELECT count(*) AS total FROM catalogo_indicadores_adaptabrasil")[0]["total"]
    coleta = _query(
        db_url,
        """
        SELECT id, iniciada_em, finalizada_em, status, avisos_validos,
               (finalizada_em < CURRENT_TIMESTAMP - (%s * interval '1 minute')) AS desatualizado
        FROM inmet_coletas ORDER BY iniciada_em DESC LIMIT 1
        """,
        (stale_min,),
    )
    avisos_ativos = _query(
        db_url,
        "SELECT count(DISTINCT aviso_codigo) AS total FROM vw_municipios_avisos_inmet WHERE estado_vigencia IN ('vigente','futuro')",
    )[0]["total"]
    return {
        "sistema": "MÉTIS — Laboratório Científico Aberto de Resiliência Agroterritorial",
        "versao": "0.3.0",
        "ecossistema": "SisTer",
        "municipios_rs": muni_count,
        "anos_censitarios": anos,
        "modelos_disponiveis": list(MODELOS_VALIDOS),
        "indicadores_adaptabrasil": adapta_inds,
        "inmet": {
            "avisos_ativos_ou_futuros": avisos_ativos,
            "ultima_coleta": coleta[0] if coleta else None,
            "limite_desatualizacao_minutos": stale_min,
        },
        "regras_epistemicas": {
            "ranking_competitivo_proibido": True,
            "natureza_indicadores": "exploratoria_nao_validada",
            "isolamento_epistemico": "R(t0) descreve capacidade intrínseca basal; AdaptaBrasil/INMET atuam como teste de estresse.",
            "universo_censitario": "estabelecimentos agropecuarios, nao todo o municipio",
        },
    }


def op_search_municipalities(db_url: str, args: dict, _ctx: dict) -> dict:
    q = args.get("query")
    inmet_only = args.get("inmet_active_only", False)
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)

    conds = ["m.uf = 'RS'"]
    params: list = []
    if q:
        q_clean = q.strip()
        if q_clean.isdigit():
            conds.append("m.codigo_ibge LIKE %s")
            params.append(f"{q_clean}%")
        else:
            conds.append("m.nome ILIKE %s")
            params.append(f"%{q_clean}%")
    if inmet_only:
        conds.append(
            "EXISTS (SELECT 1 FROM vw_municipios_avisos_inmet v WHERE v.codigo_ibge=m.codigo_ibge AND v.estado_vigencia IN ('vigente','futuro'))"
        )

    where = "WHERE " + " AND ".join(conds)
    params.extend([limit, offset])
    rows = _query(
        db_url,
        f"""
        SELECT COUNT(*) OVER() AS total, m.codigo_ibge, m.nome, m.uf, m.area_km2,
               (SELECT count(*) FROM vw_municipios_avisos_inmet v
                WHERE v.codigo_ibge = m.codigo_ibge AND v.estado_vigencia IN ('vigente','futuro')) AS avisos_inmet_ativos
        FROM municipios m
        {where}
        ORDER BY m.nome ASC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )
    total = rows[0]["total"] if rows else 0
    for r in rows:
        r.pop("total", None)
    next_offset = offset + len(rows) if (offset + len(rows)) < total else None
    return {"total": total, "limit": limit, "offset": offset, "next_offset": next_offset, "items": rows}


def op_municipality_dossier(db_url: str, args: dict, _ctx: dict) -> dict:
    codigo = args["codigo_ibge"]
    muni = _query(db_url, "SELECT codigo_ibge, nome, uf, area_km2 FROM municipios WHERE codigo_ibge=%s", (codigo,))
    if not muni:
        raise DomainError("NOT_FOUND", f"Município {codigo} não encontrado")

    obs = _query(
        db_url,
        """
        SELECT o.ano_referencia, o.fonte_id, o.area_estabelecimentos_ha, o.pastagem_natural_ha,
               o.mata_natural_ha, o.valor_producao_reais, o.estabelecimentos_total,
               o.estabelecimentos_orientacao_tecnica, o.estabelecimentos_associados, o.status_observacao
        FROM observacoes_censitarias o
        WHERE o.codigo_ibge=%s
        ORDER BY o.ano_referencia DESC
        """,
        (codigo,),
    )
    adapta = _query(
        db_url,
        """
        SELECT indicador_id, nome_indicador AS nome, ano_referencia AS ano, cenario, valor, classe_risco AS classe
        FROM evidencias_adaptabrasil
        WHERE codigo_ibge=%s
        ORDER BY indicador_id, ano_referencia, cenario
        """,
        (codigo,),
    )
    avisos = _query(
        db_url,
        """
        SELECT aviso_codigo AS codigo, descricao, severidade, aviso_cor AS cor,
               inicio, fim, estado_vigencia, afetado_por_geocodigo AS via_geocodigo,
               afetado_por_intersecao_espacial AS via_espacial
        FROM vw_municipios_avisos_inmet
        WHERE codigo_ibge=%s AND estado_vigencia IN ('vigente','futuro')
        ORDER BY inicio DESC
        """,
        (codigo,),
    )
    episodios = _query(
        db_url,
        """
        SELECT id, aviso_codigo, tipo_ameaca, severidade, janela_inicio, janela_fim,
               estado_episodio, desfecho_cientifico, estado_metis_congelado, notas_cientificas
        FROM episodios_investigacao
        WHERE codigo_ibge=%s
        ORDER BY janela_inicio DESC
        LIMIT 20
        """,
        (codigo,),
    )
    propostas = _query(
        db_url,
        """
        SELECT id, episodio_id, tipo, modelo_id, texto, limitacoes, status, origem_cliente, criado_em
        FROM propostas_investigacao_mcp
        WHERE codigo_ibge=%s
        ORDER BY criado_em DESC
        LIMIT 20
        """,
        (codigo,),
    )
    simagro_alertas = _query(
        db_url,
        """
        SELECT data_referencia::text AS data_referencia, janela, prec, estiagem, estiagem_agricola,
               geada, t_acima, t_abaixo, itu, ci_ovino, nivel_maximo
        FROM vw_simagro_alertas_recentes
        WHERE codigo_ibge=%s
        ORDER BY janela DESC
        """,
        (codigo,),
    )
    return {
        "municipio": muni[0],
        "observacoes_censitarias": obs,
        "adaptabrasil": adapta,
        "avisos_inmet_ativos": avisos,
        "simagro_alertas": simagro_alertas,
        "episodios_investigacao": episodios,
        "propostas_mcp": propostas,
        "nota_epistemica": "Dados observados agregados (IBGE) separados das evidências de estresse (AdaptaBrasil/INMET/SIMAGRO-RS).",
    }


def _fetch_observations_by_year(db_url: str, ano: int, codigos: list[str] | None = None, inmet_only: bool = False) -> list[dict]:
    conds = ["o.ano_referencia = %s", "m.uf = 'RS'"]
    params: list = [ano]
    if codigos:
        conds.append("o.codigo_ibge = ANY(%s)")
        params.append(codigos)
    if inmet_only:
        conds.append(
            "EXISTS (SELECT 1 FROM vw_municipios_avisos_inmet v WHERE v.codigo_ibge=m.codigo_ibge AND v.estado_vigencia IN ('vigente','futuro'))"
        )
    where = "WHERE " + " AND ".join(conds)
    return _query(
        db_url,
        f"""
        SELECT o.codigo_ibge, m.nome AS municipio, o.ano_referencia,
               o.area_estabelecimentos_ha, o.pastagem_natural_ha, o.mata_natural_ha,
               o.valor_producao_reais, o.estabelecimentos_total,
               o.estabelecimentos_orientacao_tecnica, o.estabelecimentos_associados
        FROM observacoes_censitarias o
        JOIN municipios m ON m.codigo_ibge = o.codigo_ibge
        {where}
        ORDER BY o.codigo_ibge ASC
        """,
        tuple(params),
    )


def op_confront_models(db_url: str, args: dict, _ctx: dict) -> dict:
    codigo = args["codigo_ibge"]
    ano = args.get("ano_referencia", 2017)
    include_traj = args.get("include_trajectory", True)
    params = _validate_parametros(args)

    rows = _fetch_observations_by_year(db_url, ano, [codigo])
    if not rows:
        raise DomainError("NOT_FOUND", f"Observação censitária não encontrada para {codigo} em {ano}")

    notas_atual = _confrontar_obs(rows[0], params)
    out = {
        "codigo_ibge": codigo,
        "municipio": rows[0]["municipio"],
        "ano_referencia": ano,
        "parametros_aplicados": {
            "k_produtiva": params.get("k_produtiva", DEFAULT_K_PRODUTIVA),
            "we": params.get("we", DEFAULT_WE),
            "wp": params.get("wp", DEFAULT_WP),
            "ws": params.get("ws", DEFAULT_WS),
            "lambda_interativo": params.get("lambda_interativo", DEFAULT_LAMBDA),
        },
        "confronto_intramunicipal": notas_atual,
        "aviso_epistemico": "Divergências entre modelos refletem hipóteses concorrentes sobre a mesma base empírica; não representam medida validada.",
    }

    if include_traj:
        outro_ano = 2006 if ano == 2017 else 2017
        rows_outro = _fetch_observations_by_year(db_url, outro_ano, [codigo])
        if rows_outro:
            notas_outro = {n["modelo"]: n for n in _confrontar_obs(rows_outro[0], params)}
            traj = []
            for n_cur in notas_atual:
                n_prev = notas_outro.get(n_cur["modelo"])
                if not n_prev:
                    continue
                n_2006, n_2017 = (n_prev, n_cur) if ano == 2017 else (n_cur, n_prev)
                def _delta(campo):
                    v0, v1 = n_2006.get(campo), n_2017.get(campo)
                    return round(v1 - v0, 6) if (v0 is not None and v1 is not None) else None
                traj.append({
                    "modelo": n_cur["modelo"],
                    "r_2006": n_2006["resiliencia"],
                    "r_2017": n_2017["resiliencia"],
                    "delta_r_2006_2017": _delta("resiliencia"),
                    "delta_e_2006_2017": _delta("ecologica_multiplicador"),
                    "delta_p_2006_2017": _delta("produtiva"),
                    "delta_s_2006_2017": _delta("social"),
                })
            out["trajetoria_2006_2017"] = traj
    return out


def op_simulate_scenario(db_url: str, args: dict, _ctx: dict) -> dict:
    modelo = args.get("modelo", MODELO_EXP_004)
    ano = args.get("ano_referencia", 2017)
    codigos = args.get("codigos_ibge")
    inmet_only = args.get("inmet_active_only", False)
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)
    params = _validate_parametros(args)

    rows = _fetch_observations_by_year(db_url, ano, codigos, inmet_only=inmet_only)
    calculados = [_pontuar_municipio(r, modelo, params) for r in rows]

    validos = [c for c in calculados if c["status"] == "experimental" and c["resiliencia"] is not None]
    incompletos = sum(1 for c in calculados if c["status"] == "dados_incompletos")
    inconsistentes = sum(1 for c in calculados if c["status"] == "inconsistencia")
    valores_r = sorted(c["resiliencia"] for c in validos)

    if modelo != MODELO_REF_001:
        refs = {r["codigo_ibge"]: _pontuar_municipio(r, MODELO_REF_001, params)["resiliencia"] for r in rows}
        deltas = []
        for c in calculados:
            rr = refs.get(c["codigo_ibge"])
            if rr is not None and c["resiliencia"] is not None:
                d = round(c["resiliencia"] - rr, 6)
                c["delta_r_vs_ref"] = d
                deltas.append(d)
            else:
                c["delta_r_vs_ref"] = None
    else:
        deltas = [0.0 for _ in validos]
        for c in calculados:
            c["delta_r_vs_ref"] = 0.0 if c["resiliencia"] is not None else None

    def _quantil(arr: list[float], p: float):
        if not arr:
            return None
        idx = (len(arr) - 1) * p
        lo, hi = math.floor(idx), math.ceil(idx)
        if lo == hi:
            return round(arr[lo], 6)
        return round(arr[lo] * (hi - idx) + arr[hi] * (idx - lo), 6)

    resumo = {
        "total_avaliados": len(calculados),
        "validos": len(validos),
        "dados_incompletos": incompletos,
        "inconsistencias": inconsistentes,
        "resiliencia_min": round(valores_r[0], 6) if valores_r else None,
        "resiliencia_q25": _quantil(valores_r, 0.25),
        "resiliencia_mediana": _quantil(valores_r, 0.5),
        "resiliencia_media": round(statistics.fmean(valores_r), 6) if valores_r else None,
        "resiliencia_q75": _quantil(valores_r, 0.75),
        "resiliencia_max": round(valores_r[-1], 6) if valores_r else None,
        "resiliencia_desvio_padrao": round(statistics.pstdev(valores_r), 6) if len(valores_r) > 1 else (0.0 if valores_r else None),
        "delta_medio_vs_ref": round(statistics.fmean(deltas), 6) if deltas else None,
    }

    page = calculados[offset : offset + limit]
    next_offset = offset + len(page) if (offset + len(page)) < len(calculados) else None
    return {
        "modelo": modelo,
        "ano_referencia": ano,
        "parametros_aplicados": {
            "k_produtiva": params.get("k_produtiva", DEFAULT_K_PRODUTIVA),
            "we": params.get("we", DEFAULT_WE),
            "wp": params.get("wp", DEFAULT_WP),
            "ws": params.get("ws", DEFAULT_WS),
            "lambda_interativo": params.get("lambda_interativo", DEFAULT_LAMBDA),
        },
        "ordenacao": "codigo_ibge ASC (sem ranqueamento competitivo entre municipios)",
        "sumario_estatistico": resumo,
        "limit": limit,
        "offset": offset,
        "next_offset": next_offset,
        "items": page,
    }


def op_inmet_alerts(db_url: str, args: dict, _ctx: dict) -> dict:
    modo = args.get("modo", "ativos")
    codigo = args.get("codigo_ibge")
    severidade = args.get("severidade")
    tipo_evento = args.get("tipo_evento")
    limit = args.get("limit", 25)
    offset = args.get("offset", 0)
    stale_min = max(1, int(os.environ.get("METIS_INMET_STALE_MINUTES", "30")))

    if modo == "status":
        coletas = _query(
            db_url,
            """
            SELECT id, iniciada_em, finalizada_em, status, acionamento, http_status,
                   avisos_recebidos, avisos_validos, versoes_criadas, mensagem,
                   (finalizada_em < CURRENT_TIMESTAMP - (%s * interval '1 minute')) AS desatualizado
            FROM inmet_coletas ORDER BY iniciada_em DESC LIMIT %s OFFSET %s
            """,
            (stale_min, limit, offset),
        )
        return {"modo": "status", "limite_desatualizacao_minutos": stale_min, "coletas": coletas}

    if modo == "ativos":
        conds = ["estado_vigencia IN ('vigente', 'futuro')"]
        params: list = []
        if codigo:
            conds.append("codigo_ibge = %s")
            params.append(codigo)
        if severidade:
            conds.append("severidade ILIKE %s")
            params.append(f"%{severidade}%")
        if tipo_evento:
            conds.append("descricao ILIKE %s")
            params.append(f"%{tipo_evento}%")
        where = "WHERE " + " AND ".join(conds)
        params.extend([limit, offset])
        rows = _query(
            db_url,
            f"""
            SELECT COUNT(*) OVER() AS total, codigo_ibge, municipio_nome AS municipio,
                   aviso_codigo AS codigo, descricao, severidade, aviso_cor AS cor,
                   inicio, fim, estado_vigencia, afetado_por_geocodigo AS via_geocodigo,
                   afetado_por_intersecao_espacial AS via_espacial
            FROM vw_municipios_avisos_inmet
            {where}
            ORDER BY inicio DESC, codigo_ibge ASC
            LIMIT %s OFFSET %s
            """,
            tuple(params),
        )
    else:
        conds = []
        params = []
        if codigo:
            conds.append("im.codigo_ibge = %s")
            params.append(codigo)
        if severidade:
            conds.append("v.severidade ILIKE %s")
            params.append(f"%{severidade}%")
        if tipo_evento:
            conds.append("v.descricao ILIKE %s")
            params.append(f"%{tipo_evento}%")
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        params.extend([limit, offset])
        rows = _query(
            db_url,
            f"""
            SELECT COUNT(*) OVER() AS total, im.codigo_ibge, m.nome AS municipio,
                   a.codigo, v.id AS versao_id, v.observado_em, v.descricao,
                   v.severidade, v.inicio, v.fim, v.situacao_origem,
                   im.via_geocodigo, im.via_intersecao_espacial
            FROM inmet_avisos_versoes v
            JOIN avisos_meteorologicos_inmet a ON a.id = v.aviso_id
            JOIN inmet_avisos_municipios im ON im.versao_id = v.id
            JOIN municipios m ON m.codigo_ibge = im.codigo_ibge
            {where}
            ORDER BY v.inicio DESC, im.codigo_ibge ASC
            LIMIT %s OFFSET %s
            """,
            tuple(params),
        )

    total = rows[0]["total"] if rows else 0
    for r in rows:
        r.pop("total", None)
    next_offset = offset + len(rows) if (offset + len(rows)) < total else None
    return {"modo": modo, "total": total, "limit": limit, "offset": offset, "next_offset": next_offset, "items": rows}


def op_investigation_episodes(db_url: str, args: dict, _ctx: dict) -> dict:
    conds = []
    params: list = []
    for col, key in (
        ("e.codigo_ibge", "codigo_ibge"),
        ("e.estado_episodio", "estado_episodio"),
        ("e.desfecho_cientifico", "desfecho_cientifico"),
    ):
        if args.get(key):
            conds.append(f"{col} = %s")
            params.append(args[key])
    if args.get("severidade"):
        conds.append("e.severidade ILIKE %s")
        params.append(f"%{args['severidade']}%")

    limit = args.get("limit", 20)
    offset = args.get("offset", 0)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    params.extend([limit, offset])
    rows = _query(
        db_url,
        f"""
        SELECT COUNT(*) OVER() AS total, e.id, e.codigo_ibge, m.nome AS municipio,
               e.aviso_codigo, e.tipo_ameaca, e.severidade, e.janela_inicio, e.janela_fim,
               e.estado_episodio, e.desfecho_cientifico, e.estado_metis_congelado,
               e.notas_cientificas, e.criado_em, e.atualizado_em
        FROM episodios_investigacao e
        JOIN municipios m ON m.codigo_ibge = e.codigo_ibge
        {where}
        ORDER BY e.janela_inicio DESC, e.codigo_ibge ASC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )
    total = rows[0]["total"] if rows else 0
    for r in rows:
        r.pop("total", None)
    next_offset = offset + len(rows) if (offset + len(rows)) < total else None
    return {"total": total, "limit": limit, "offset": offset, "next_offset": next_offset, "items": rows}


def op_scientific_catalog(_db_url: str, args: dict, _ctx: dict) -> dict:
    secao = args.get("secao", "modelos")
    categoria = args.get("categoria")
    file_map = {
        "modelos": "modelos.json",
        "achados": "achados.json",
        "resumos": "resumos.json",
        "noticias": "noticias.json",
    }
    path = os.path.join(PUBLIC_API_DIR, file_map[secao])
    if not os.path.isfile(path):
        raise DomainError("NOT_FOUND", f"Catálogo '{secao}' indisponível")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if secao == "achados" and categoria and isinstance(data.get("achados"), list):
        data = dict(data)
        data["achados"] = [a for a in data["achados"] if a.get("categoria") == categoria]
        data["total_filtrado"] = len(data["achados"])
    return {"secao": secao, "conteudo": data}


def op_proposals(db_url: str, args: dict, _ctx: dict) -> dict:
    conds = []
    params: list = []
    for col, key in (("codigo_ibge", "codigo_ibge"), ("episodio_id", "episodio_id"), ("status", "status")):
        if args.get(key):
            conds.append(f"{col} = %s")
            params.append(args[key])
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    params.extend([limit, offset])
    rows = _query(
        db_url,
        f"""
        SELECT COUNT(*) OVER() AS total, id, request_id, codigo_ibge, episodio_id,
               tipo, modelo_id, parametros, texto, limitacoes, status,
               origem_tipo, origem_cliente, criado_em
        FROM propostas_investigacao_mcp
        {where}
        ORDER BY criado_em DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )
    total = rows[0]["total"] if rows else 0
    for r in rows:
        r.pop("total", None)
    next_offset = offset + len(rows) if (offset + len(rows)) < total else None
    return {"total": total, "limit": limit, "offset": offset, "next_offset": next_offset, "items": rows}


def op_verify(db_url: str, _args: dict, _ctx: dict) -> dict:
    munis = _query(db_url, "SELECT count(*) AS total, count(*) FILTER (WHERE ST_IsValid(geometria)) AS geom_validas FROM municipios WHERE uf='RS'")[0]
    obs = _query(
        db_url,
        """
        SELECT ano_referencia, count(*) AS total,
               count(*) FILTER (WHERE status_observacao = 'valido') AS validas
        FROM observacoes_censitarias
        GROUP BY ano_referencia ORDER BY ano_referencia
        """,
    )
    execs = _query(
        db_url,
        "SELECT id, modelo_id, modelo_versao, ano_referencia, imutavel, sha256_saida FROM execucoes_experimentais ORDER BY executado_em DESC",
    )
    migs = _query(db_url, "SELECT count(*) AS total FROM registro_migracoes")[0]["total"]
    ok = munis["total"] == 497 and munis["geom_validas"] == 497 and len(execs) >= 1 and migs >= 6
    return {
        "integridade_tecnica": "VERIFIED" if ok else "DEGRADED",
        "municipios_rs": munis["total"],
        "geometrias_postgis_validas": munis["geom_validas"],
        "observacoes_por_ano": obs,
        "execucoes_experimentais_registradas": len(execs),
        "execucoes_imutaveis": sum(1 for e in execs if e["imutavel"]),
        "migracoes_aplicadas": migs,
    }


def op_propose_investigation_note(db_url: str, args: dict, ctx: dict) -> dict:
    if not ctx.get("allow_writes"):
        raise DomainError("AUTHORITY_REQUIRED", "Escrita MCP desabilitada; inicie com --allow-writes ou METIS_MCP_ALLOW_WRITES=1")

    req_id = args["request_id"]
    codigo = args["codigo_ibge"]
    episodio_id = args.get("episodio_id")
    tipo = args.get("tipo", "nota_candidata")
    modelo_id = args.get("modelo_id")
    parametros = args.get("parametros") or {}
    texto = args["texto"].strip()
    limitacoes = args["limitacoes"].strip()
    client_name = ctx.get("client_name") or "unknown"
    origem_cliente = f"mcp:{client_name}"

    if not texto or not limitacoes:
        raise SchemaValidationError("texto e limitacoes não podem ser vazios")

    sig_payload = {
        "op": "propose_investigation_note",
        "origem_cliente": origem_cliente,
        "codigo_ibge": codigo,
        "episodio_id": episodio_id,
        "tipo": tipo,
        "modelo_id": modelo_id,
        "parametros": parametros,
        "texto": texto,
        "limitacoes": limitacoes,
    }
    assinatura = hashlib.sha256(
        json.dumps(sig_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    try:
        with psycopg.connect(db_url, row_factory=dict_row, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT assinatura_sha256, resultado_json FROM propostas_investigacao_mcp WHERE request_id = %s::uuid",
                    (req_id,),
                )
                existing = cur.fetchone()
                if existing:
                    if existing["assinatura_sha256"] != assinatura:
                        raise DomainError(
                            "CONFLICT",
                            "request_id já utilizado com argumentos ou cliente distintos",
                        )
                    return json_safe(existing["resultado_json"])

                cur.execute("SELECT codigo_ibge FROM municipios WHERE codigo_ibge = %s", (codigo,))
                if not cur.fetchone():
                    raise DomainError("NOT_FOUND", f"Município {codigo} não encontrado")

                if episodio_id:
                    cur.execute(
                        "SELECT codigo_ibge FROM episodios_investigacao WHERE id = %s",
                        (episodio_id,),
                    )
                    ep = cur.fetchone()
                    if not ep:
                        raise DomainError("NOT_FOUND", f"Episódio {episodio_id} não encontrado")
                    if ep["codigo_ibge"] != codigo:
                        raise DomainError(
                            "CONFLICT",
                            f"Episódio {episodio_id} pertence ao município {ep['codigo_ibge']}, não a {codigo}",
                        )

                prop_id = "PROP-" + uuid.uuid4().hex[:12]
                resultado = {
                    "id": prop_id,
                    "request_id": req_id,
                    "codigo_ibge": codigo,
                    "episodio_id": episodio_id,
                    "tipo": tipo,
                    "modelo_id": modelo_id,
                    "parametros": parametros,
                    "texto": texto,
                    "limitacoes": limitacoes,
                    "status": "pendente_revisao",
                    "origem_tipo": "mcp_client",
                    "origem_cliente": origem_cliente,
                }
                cur.execute(
                    """
                    INSERT INTO propostas_investigacao_mcp (
                        id, request_id, assinatura_sha256, codigo_ibge, episodio_id,
                        tipo, modelo_id, parametros, texto, limitacoes,
                        status, origem_tipo, origem_cliente, resultado_json
                    ) VALUES (
                        %s, %s::uuid, %s, %s, %s,
                        %s, %s, %s::jsonb, %s, %s,
                        'pendente_revisao', 'mcp_client', %s, %s::jsonb
                    )
                    """,
                    (
                        prop_id,
                        req_id,
                        assinatura,
                        codigo,
                        episodio_id,
                        tipo,
                        modelo_id,
                        json.dumps(parametros, ensure_ascii=False),
                        texto,
                        limitacoes,
                        origem_cliente,
                        json.dumps(resultado, ensure_ascii=False),
                    ),
                )
                conn.commit()
                return resultado
    except DomainError:
        raise
    except psycopg.Error as exc:
        raise DomainError("DATABASE_UNAVAILABLE", f"Falha ao persistir proposta MCP: {exc}")


# ---------------------------------------------------------------------------
# Catálogo e Validação de Contrato MCP
# ---------------------------------------------------------------------------

def _prop_schema_parametros():
    return {
        "k_produtiva": {"type": "number", "description": "Parâmetro de escala produtiva k em R$/ha (>0, padrão 1500)."},
        "we": {"type": "number", "description": "Peso ecológico em EPS-EXP-002 (0..10, padrão 0.33)."},
        "wp": {"type": "number", "description": "Peso produtivo em EPS-EXP-002 (0..10, padrão 0.33)."},
        "ws": {"type": "number", "description": "Peso social em EPS-EXP-002 (0..10, padrão 0.34)."},
        "lambda_interativo": {"type": "number", "description": "Acoplamento interativo em EPS-EXP-003 (-10..10, padrão 0.5)."},
    }


OPERATIONS = {
    "capabilities": {
        "description": "Inspeciona versão, modelos disponíveis, anos censitários, frescor do INMET e regras epistêmicas do MÉTIS.",
        "read_only": True,
        "idempotent": True,
        "required": [],
        "properties": {},
        "handler": op_capabilities,
    },
    "search_municipalities": {
        "description": "Busca municípios do RS por nome parcial ou prefixo IBGE, com filtro opcional de alertas INMET ativos e paginação.",
        "read_only": True,
        "idempotent": True,
        "required": [],
        "properties": {
            "query": {"type": "string", "description": "Nome parcial do município ou prefixo do código IBGE."},
            "inmet_active_only": {"type": "boolean", "description": "Se true, lista apenas municípios com aviso INMET vigente ou futuro."},
            "limit": {"type": "integer", "description": "Máximo de itens por página (1..100, padrão 20)."},
            "offset": {"type": "integer", "description": "Deslocamento inicial (>=0, padrão 0)."},
        },
        "handler": op_search_municipalities,
    },
    "municipality_dossier": {
        "description": "Dossiê territorial completo de um município do RS: variáveis censitárias (2006/2017), AdaptaBrasil, avisos INMET e episódios.",
        "read_only": True,
        "idempotent": True,
        "required": ["codigo_ibge"],
        "properties": {
            "codigo_ibge": {"type": "string", "description": "Código IBGE de 7 dígitos do município gaúcho (ex: 4314407)."},
        },
        "handler": op_municipality_dossier,
    },
    "confront_models": {
        "description": "Confronto intramunicipal dos 4 modelos (EPS-REF-001, EPS-EXP-002, EPS-EXP-003, EPS-EXP-004) e trajetória 2006-2017.",
        "read_only": True,
        "idempotent": True,
        "required": ["codigo_ibge"],
        "properties": {
            "codigo_ibge": {"type": "string", "description": "Código IBGE de 7 dígitos do município gaúcho."},
            "ano_referencia": {"type": "integer", "enum": [2006, 2017], "description": "Ano censitário base (2006 ou 2017, padrão 2017)."},
            "include_trajectory": {"type": "boolean", "description": "Incluir comparação decenal 2006->2017 (padrão true)."},
            **_prop_schema_parametros(),
        },
        "handler": op_confront_models,
    },
    "simulate_scenario": {
        "description": "Simulação paramétrica sobre o RS (ou subconjunto), retornando distribuição estatística e lista paginada ordenada por código IBGE (sem ranking competitivo).",
        "read_only": True,
        "idempotent": True,
        "required": [],
        "properties": {
            "modelo": {"type": "string", "enum": list(MODELOS_VALIDOS), "description": "Modelo teórico (padrão EPS-EXP-004)."},
            "ano_referencia": {"type": "integer", "enum": [2006, 2017], "description": "Ano censitário (2006 ou 2017, padrão 2017)."},
            "codigos_ibge": {"type": "array", "items": {"type": "string"}, "description": "Lista opcional de até 50 códigos IBGE para simulação focada."},
            "inmet_active_only": {"type": "boolean", "description": "Se true, restringe aos municípios com aviso INMET vigente/futuro."},
            "limit": {"type": "integer", "description": "Itens retornados na página (1..100, padrão 20)."},
            "offset": {"type": "integer", "description": "Deslocamento inicial (>=0, padrão 0)."},
            **_prop_schema_parametros(),
        },
        "handler": op_simulate_scenario,
    },
    "inmet_alerts": {
        "description": "Consulta avisos INMET ativos/futuros, histórico temporal de versões por município ou auditoria das coletas.",
        "read_only": True,
        "idempotent": True,
        "required": [],
        "properties": {
            "modo": {"type": "string", "enum": ["ativos", "historico", "status"], "description": "Escopo da consulta INMET (padrão ativos)."},
            "codigo_ibge": {"type": "string", "description": "Filtro opcional por código IBGE de 7 dígitos."},
            "severidade": {"type": "string", "description": "Filtro parcial por severidade (ex: Perigo, Grande Perigo)."},
            "tipo_evento": {"type": "string", "description": "Filtro parcial por descrição do evento meteorológico."},
            "limit": {"type": "integer", "description": "Máximo de registros (1..100, padrão 25)."},
            "offset": {"type": "integer", "description": "Deslocamento inicial (>=0, padrão 0)."},
        },
        "handler": op_inmet_alerts,
    },
    "investigation_episodes": {
        "description": "Lista episódios de investigação científica (METIS-DIR-EVID-001) com condições antecedentes congeladas e estado epistêmico.",
        "read_only": True,
        "idempotent": True,
        "required": [],
        "properties": {
            "codigo_ibge": {"type": "string", "description": "Filtro opcional por código IBGE."},
            "estado_episodio": {
                "type": "string",
                "enum": ["ameaca_anunciada", "em_verificacao", "impactos_respostas", "avaliacao_concluida"],
                "description": "Filtro por fase do episódio.",
            },
            "desfecho_cientifico": {
                "type": "string",
                "enum": ["em_aberto", "corroborado", "contraditado", "inconclusivo", "reconfiguracao_documentada"],
                "description": "Filtro por desfecho científico.",
            },
            "severidade": {"type": "string", "description": "Filtro parcial por severidade."},
            "limit": {"type": "integer", "description": "Máximo de episódios (1..100, padrão 20)."},
            "offset": {"type": "integer", "description": "Deslocamento inicial (>=0, padrão 0)."},
        },
        "handler": op_investigation_episodes,
    },
    "scientific_catalog": {
        "description": "Consulta catálogo público estático do MÉTIS: modelos matemáticos, achados científicos, resumos ou notícias.",
        "read_only": True,
        "idempotent": True,
        "required": [],
        "properties": {
            "secao": {"type": "string", "enum": ["modelos", "achados", "resumos", "noticias"], "description": "Seção do catálogo (padrão modelos)."},
            "categoria": {"type": "string", "description": "Filtro opcional por categoria quando secao='achados'."},
        },
        "handler": op_scientific_catalog,
    },
    "proposals": {
        "description": "Lista propostas candidatas registradas via MCP para revisão humana no laboratório.",
        "read_only": True,
        "idempotent": True,
        "required": [],
        "properties": {
            "codigo_ibge": {"type": "string", "description": "Filtro opcional por município."},
            "episodio_id": {"type": "string", "description": "Filtro opcional por ID de episódio."},
            "status": {"type": "string", "enum": ["pendente_revisao", "incorporada", "descartada"], "description": "Filtro por situação."},
            "limit": {"type": "integer", "description": "Máximo de propostas (1..100, padrão 20)."},
            "offset": {"type": "integer", "description": "Deslocamento inicial (>=0, padrão 0)."},
        },
        "handler": op_proposals,
    },
    "verify": {
        "description": "Verificação técnica de integridade: 497 municípios, geometrias PostGIS válidas, séries censitárias, imutabilidade e migrações.",
        "read_only": True,
        "idempotent": True,
        "required": [],
        "properties": {},
        "handler": op_verify,
    },
    "propose_investigation_note": {
        "description": "Registra nota/hipótese candidata isolada (pendente_revisao) para revisão humana, sem alterar execuções imutáveis. Requer --allow-writes e request_id UUID.",
        "read_only": False,
        "idempotent": True,
        "required": ["codigo_ibge", "texto", "limitacoes", "request_id"],
        "properties": {
            "codigo_ibge": {"type": "string", "description": "Código IBGE de 7 dígitos do município."},
            "episodio_id": {"type": "string", "description": "ID opcional do episódio de investigação associado."},
            "tipo": {"type": "string", "enum": ["nota_candidata", "hipotese_parametro", "observacao_impacto"], "description": "Tipo da contribuição candidata (padrão nota_candidata)."},
            "modelo_id": {"type": "string", "enum": list(MODELOS_VALIDOS), "description": "Modelo opcional relacionado à hipótese."},
            "parametros": {"type": "object", "description": "Parâmetros experimentais opcionais associados."},
            "texto": {"type": "string", "description": "Texto analítico da proposta candidata (1..4000 caracteres)."},
            "limitacoes": {"type": "string", "description": "Declaração obrigatória de limitações metodológicas (5..1000 caracteres)."},
            "request_id": {"type": "string", "description": "UUID estável para repetição idempotente segura."},
        },
        "handler": op_propose_investigation_note,
    },
}


def catalog(allow_writes: bool = False) -> list[dict]:
    tools = []
    for name, spec in OPERATIONS.items():
        if not spec["read_only"] and not allow_writes:
            continue
        tools.append(
            {
                "name": name,
                "description": spec["description"],
                "inputSchema": {
                    "type": "object",
                    "properties": spec["properties"],
                    "required": spec["required"],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": spec["read_only"],
                    "destructiveHint": False,
                    "idempotentHint": spec["idempotent"],
                },
            }
        )
    return tools


def validate_args(name: str, raw_args) -> dict:
    if name not in OPERATIONS:
        raise SchemaValidationError(f"Ferramenta desconhecida: {name}")
    spec = OPERATIONS[name]
    if raw_args is None:
        args = {}
    elif isinstance(raw_args, dict):
        args = {k: v for k, v in raw_args.items() if not (v is None and k not in spec["required"])}
    else:
        raise SchemaValidationError("arguments deve ser um objeto JSON")

    allowed = set(spec["properties"].keys())
    unknown = set(args.keys()) - allowed
    if unknown:
        raise SchemaValidationError(f"Argumentos desconhecidos: {', '.join(sorted(unknown))}")

    for req in spec["required"]:
        if req not in args or args[req] is None:
            raise SchemaValidationError(f"Argumento obrigatório ausente: {req}")

    clean = {}
    for k, v in args.items():
        prop = spec["properties"][k]
        if k == "codigo_ibge":
            clean[k] = _check_ibge(v)
        elif k == "request_id":
            clean[k] = _check_uuid(v)
        elif k == "codigos_ibge":
            if not isinstance(v, list) or len(v) == 0 or len(v) > 50:
                raise SchemaValidationError("codigos_ibge deve ser lista de 1..50 códigos IBGE")
            clean[k] = [_check_ibge(item) for item in v]
        elif prop["type"] == "integer":
            if k == "limit":
                clean[k] = _check_int(v, k, 1, 100)
            elif k == "offset":
                clean[k] = _check_int(v, k, 0, 100_000)
            else:
                clean[k] = _check_int(v, k, -10_000, 10_000)
        elif prop["type"] == "number":
            clean[k] = _check_num(v, k)
        elif prop["type"] == "boolean":
            clean[k] = _check_bool(v, k)
        elif prop["type"] == "object":
            if not isinstance(v, dict):
                raise SchemaValidationError(f"{k} deve ser objeto JSON")
            clean[k] = v
        elif prop["type"] == "string":
            min_len = 5 if k == "limitacoes" else (1 if k in spec["required"] else 0)
            max_len = 4000 if k == "texto" else (1000 if k == "limitacoes" else 200)
            clean[k] = _check_str(v, k, min_len=min_len, max_len=max_len)

        if "enum" in prop and clean[k] not in prop["enum"]:
            raise SchemaValidationError(f"{k} inválido; esperado um de {prop['enum']}")

    _validate_parametros(clean)
    return clean


def execute_operation(db_url: str, name: str, raw_args, ctx: dict) -> dict:
    clean = validate_args(name, raw_args)
    return OPERATIONS[name]["handler"](db_url, clean, ctx)
