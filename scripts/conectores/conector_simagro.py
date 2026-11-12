#!/usr/bin/env python3
"""Conector SIMAGRO-RS (SEAPI/DDPA) para alertas agroclimáticos municipais."""

import hashlib
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import psycopg

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
OUTPUT_DIR = os.path.join(REPO_ROOT, "data/evidencias/simagro")
DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")
SIMAGRO_API_BASE = os.environ.get("SIMAGRO_API_BASE", "https://simagro.rs.gov.br/api").rstrip("/")
SIMAGRO_MUNICIPIOS_URL = os.environ.get(
    "SIMAGRO_MUNICIPIOS_URL",
    "https://simagro.rs.gov.br/static/assets/json/municipios.geojson",
)
SIMAGRO_ADVISORY_LOCK_ID = 0x4D4554495353494D
SIMAGRO_JANELAS = ("7d", "3d")
SIMAGRO_INDICES = (
    "PREC",
    "ESTIAGEM",
    "ESTIAGEM_AGRICOLA",
    "GEADA",
    "T_ACIMA",
    "T_ABAIXO",
    "ITU",
    "CI_OVINO",
)
USER_AGENT = "METIS-Epistemic-Lab/0.4 (+https://github.com/jpereiratrindade/METIS)"


def calcular_sha256_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _fetch_bytes(url: str, timeout: int = 20) -> tuple[bytes, int]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
        return resp.read(), getattr(resp, "status", 200)


def _normalizar_nivel(valor, campo: str) -> int:
    if valor is None:
        return 0
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError(f"Índice '{campo}' inválido: {valor!r}")
    nivel = int(round(float(valor)))
    if nivel < 0 or nivel > 3:
        raise ValueError(f"Índice '{campo}' fora da faixa 0..3: {valor!r}")
    return nivel


def parsear_mapa_municipios_geojson(dados: dict) -> list[dict]:
    """Extrai registros (id_ponto, codigo_ibge, nome_simagro, region_id) do GeoJSON oficial."""
    features = dados.get("features") if isinstance(dados, dict) else None
    if not isinstance(features, list) or not features:
        raise ValueError("GeoJSON SIMAGRO inválido: 'features' ausente ou vazio")

    registros = []
    for feat in features:
        props = feat.get("properties") if isinstance(feat, dict) else None
        if not isinstance(props, dict):
            continue
        id_ponto = props.get("id_ponto")
        city = props.get("City")
        if id_ponto is None or city is None:
            continue
        codigo_ibge = str(city).strip()
        if len(codigo_ibge) != 7 or not codigo_ibge.isdigit():
            continue
        registros.append({
            "id_ponto": int(id_ponto),
            "codigo_ibge": codigo_ibge,
            "nome_simagro": str(props.get("nome") or "")[:150] or None,
            "region_id": int(props["region_id"]) if props.get("region_id") is not None else None,
        })
    if not registros:
        raise ValueError("GeoJSON SIMAGRO sem municípios válidos")
    return registros


def parsear_alertas_simagro(payload: object, mapa_ibge: dict[int, str]) -> tuple[list[dict], int]:
    """Valida e normaliza o array JSON retornado por /api/alerta_agromet_{janela}/{YYYYMMDD}."""
    if not isinstance(payload, list) or not payload:
        raise ValueError("Payload SIMAGRO inválido: esperada lista JSON não vazia")

    validos = []
    for item in payload:
        if not isinstance(item, dict) or item.get("id_pto") is None:
            continue
        id_pto = int(item["id_pto"])
        codigo_ibge = mapa_ibge.get(id_pto)
        if not codigo_ibge:
            continue
        niveis = {campo.lower(): _normalizar_nivel(item.get(campo), campo) for campo in SIMAGRO_INDICES}
        validos.append({
            "codigo_ibge": codigo_ibge,
            "id_ponto": id_pto,
            **niveis,
        })

    if not validos:
        raise ValueError("Nenhum registro válido mapeado para códigos IBGE do RS")
    return validos, len(payload)


def garantir_mapa_municipios(conn, forcar: bool = False) -> dict[int, str]:
    """Carrega o de-para id_ponto -> codigo_ibge do banco ou do GeoJSON do SIMAGRO-RS."""
    with conn.cursor() as cur:
        cur.execute("SELECT id_ponto, codigo_ibge FROM simagro_municipios_mapa")
        mapa = {row[0]: row[1] for row in cur.fetchall()}

    if len(mapa) >= 497 and not forcar:
        return mapa

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    conteudo, _ = _fetch_bytes(SIMAGRO_MUNICIPIOS_URL, timeout=30)
    caminho_geojson = os.path.join(OUTPUT_DIR, "municipios.geojson")
    with open(caminho_geojson, "wb") as f:
        f.write(conteudo)

    registros = parsear_mapa_municipios_geojson(json.loads(conteudo.decode("utf-8")))
    with conn.cursor() as cur:
        cur.execute("SELECT codigo_ibge FROM municipios WHERE uf = 'RS'")
        ibges_validos = {row[0] for row in cur.fetchall()}

        for reg in registros:
            if reg["codigo_ibge"] not in ibges_validos:
                continue
            cur.execute(
                """
                INSERT INTO simagro_municipios_mapa (id_ponto, codigo_ibge, nome_simagro, region_id, atualizado_em)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (id_ponto) DO UPDATE SET
                    codigo_ibge = EXCLUDED.codigo_ibge,
                    nome_simagro = EXCLUDED.nome_simagro,
                    region_id = EXCLUDED.region_id,
                    atualizado_em = CURRENT_TIMESTAMP
                """,
                (reg["id_ponto"], reg["codigo_ibge"], reg["nome_simagro"], reg["region_id"]),
            )
        conn.commit()
        cur.execute("SELECT id_ponto, codigo_ibge FROM simagro_municipios_mapa")
        return {row[0]: row[1] for row in cur.fetchall()}


def _registrar_falha(db_url: str, coleta_id: int | None, status: str, mensagem: str, http_status: int | None = None):
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                if coleta_id is not None:
                    cur.execute(
                        """
                        UPDATE simagro_coletas
                        SET finalizada_em = CURRENT_TIMESTAMP, status = %s, http_status = COALESCE(%s, http_status),
                            mensagem = %s
                        WHERE id = %s
                        """,
                        (status, http_status, mensagem[:4000], coleta_id),
                    )
                cur.execute(
                    """
                    INSERT INTO status_conectores (fonte, ultima_tentativa, status, mensagem)
                    VALUES ('simagro_alertas', CURRENT_TIMESTAMP, %s, %s)
                    ON CONFLICT (fonte) DO UPDATE SET
                        ultima_tentativa = CURRENT_TIMESTAMP,
                        status = EXCLUDED.status,
                        mensagem = EXCLUDED.mensagem
                    """,
                    (status, mensagem[:4000]),
                )
    except Exception:
        pass


def _coletar_janela_simagro(
    db_url: str,
    mapa_ibge: dict[int, str],
    data_ref: date,
    janela: str,
    acionamento: str,
    salvar_banco: bool,
) -> dict:
    data_str = data_ref.strftime("%Y%m%d")
    url = f"{SIMAGRO_API_BASE}/alerta_agromet_{janela}/{data_str}"
    coleta_id = None

    if salvar_banco:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO simagro_coletas (origem_url, janela, data_referencia, acionamento)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (url, janela, data_ref, acionamento),
                )
                coleta_id = cur.fetchone()[0]

    try:
        conteudo, http_status = _fetch_bytes(url, timeout=20)
        sha256 = calcular_sha256_bytes(conteudo)
        nome_arquivo = f"simagro_alerta_{janela}_{data_str}_{sha256[:12]}.json"
        caminho_arquivo = os.path.join(OUTPUT_DIR, nome_arquivo)
        with open(caminho_arquivo, "wb") as f:
            f.write(conteudo)

        payload = json.loads(conteudo.decode("utf-8"))
        registros, total_recebidos = parsear_alertas_simagro(payload, mapa_ibge)

        if not salvar_banco:
            return {
                "janela": janela,
                "data_referencia": data_ref.isoformat(),
                "status": "sucesso",
                "recebidos": total_recebidos,
                "validos": len(registros),
                "sha256": sha256,
            }

        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                for reg in registros:
                    cur.execute(
                        """
                        INSERT INTO evidencias_simagro_alertas (
                            codigo_ibge, id_ponto, data_referencia, janela,
                            prec, estiagem, estiagem_agricola, geada,
                            t_acima, t_abaixo, itu, ci_ovino,
                            sha256_origem, coleta_id, consultado_em
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, CURRENT_TIMESTAMP
                        )
                        ON CONFLICT (codigo_ibge, data_referencia, janela) DO UPDATE SET
                            id_ponto = EXCLUDED.id_ponto,
                            prec = EXCLUDED.prec,
                            estiagem = EXCLUDED.estiagem,
                            estiagem_agricola = EXCLUDED.estiagem_agricola,
                            geada = EXCLUDED.geada,
                            t_acima = EXCLUDED.t_acima,
                            t_abaixo = EXCLUDED.t_abaixo,
                            itu = EXCLUDED.itu,
                            ci_ovino = EXCLUDED.ci_ovino,
                            sha256_origem = EXCLUDED.sha256_origem,
                            coleta_id = EXCLUDED.coleta_id,
                            consultado_em = CURRENT_TIMESTAMP
                        """,
                        (
                            reg["codigo_ibge"],
                            reg["id_ponto"],
                            data_ref,
                            janela,
                            reg["prec"],
                            reg["estiagem"],
                            reg["estiagem_agricola"],
                            reg["geada"],
                            reg["t_acima"],
                            reg["t_abaixo"],
                            reg["itu"],
                            reg["ci_ovino"],
                            sha256,
                            coleta_id,
                        ),
                    )
                cur.execute(
                    """
                    UPDATE simagro_coletas
                    SET finalizada_em = CURRENT_TIMESTAMP,
                        status = 'sucesso',
                        http_status = %s,
                        sha256_payload = %s,
                        arquivo_payload = %s,
                        registros_recebidos = %s,
                        registros_validos = %s,
                        mensagem = %s
                    WHERE id = %s
                    """,
                    (
                        http_status,
                        sha256,
                        os.path.relpath(caminho_arquivo, REPO_ROOT),
                        total_recebidos,
                        len(registros),
                        f"Coleta SIMAGRO ({janela}) concluída para {data_ref.isoformat()}",
                        coleta_id,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO status_conectores (fonte, ultima_tentativa, ultima_coleta_sucesso, status, mensagem)
                    VALUES ('simagro_alertas', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'sucesso', %s)
                    ON CONFLICT (fonte) DO UPDATE SET
                        ultima_tentativa = CURRENT_TIMESTAMP,
                        ultima_coleta_sucesso = CURRENT_TIMESTAMP,
                        status = 'sucesso',
                        mensagem = EXCLUDED.mensagem
                    """,
                    (f"{len(registros)} municípios sincronizados ({janela}, {data_ref.isoformat()})",),
                )
                conn.commit()

        return {
            "coleta_id": coleta_id,
            "janela": janela,
            "data_referencia": data_ref.isoformat(),
            "status": "sucesso",
            "recebidos": total_recebidos,
            "validos": len(registros),
            "sha256": sha256,
        }
    except urllib.error.HTTPError as exc:
        msg = f"HTTP {exc.code} ao consultar {url}: {exc.reason}"
        if salvar_banco:
            _registrar_falha(db_url, coleta_id, "falha_rede", msg, http_status=exc.code)
        raise RuntimeError(msg) from exc
    except urllib.error.URLError as exc:
        msg = f"Falha de rede SIMAGRO ({janela}): {exc}"
        if salvar_banco:
            _registrar_falha(db_url, coleta_id, "falha_rede", msg)
        raise RuntimeError(msg) from exc
    except (json.JSONDecodeError, ValueError) as exc:
        msg = f"Payload SIMAGRO inválido ({janela}): {exc}"
        if salvar_banco:
            _registrar_falha(db_url, coleta_id, "falha_validacao", msg)
        raise RuntimeError(msg) from exc
    except psycopg.Error as exc:
        msg = f"Erro ao persistir SIMAGRO ({janela}): {exc}"
        if salvar_banco:
            _registrar_falha(db_url, coleta_id, "falha_persistencia", msg)
        raise RuntimeError(msg) from exc


def coletar_alertas_simagro(
    db_url: str = DEFAULT_DB_URL,
    salvar_banco: bool = True,
    acionamento: str = "manual",
    data_referencia: date | None = None,
    janelas: tuple[str, ...] = SIMAGRO_JANELAS,
) -> dict:
    """Coleta alertas agroclimáticos do SIMAGRO-RS (janelas 7d e 3d) com lock de concorrência."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    data_ref = data_referencia or datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    print(f"=== SIMAGRO-RS: coleta {data_ref.isoformat()} ({', '.join(janelas)}) ===")

    if not salvar_banco:
        conteudo, _ = _fetch_bytes(SIMAGRO_MUNICIPIOS_URL, timeout=30)
        regs_mapa = parsear_mapa_municipios_geojson(json.loads(conteudo.decode("utf-8")))
        mapa_ibge = {r["id_ponto"]: r["codigo_ibge"] for r in regs_mapa}
        resultados = [
            _coletar_janela_simagro(db_url, mapa_ibge, data_ref, j, acionamento, salvar_banco=False)
            for j in janelas
        ]
        return {"data_referencia": data_ref.isoformat(), "janelas": resultados}

    with psycopg.connect(db_url) as lock_conn:
        with lock_conn.cursor() as lock_cur:
            lock_cur.execute("SELECT pg_try_advisory_lock(%s)", (SIMAGRO_ADVISORY_LOCK_ID,))
            if not lock_cur.fetchone()[0]:
                return {"status": "em_andamento", "mensagem": "Coleta SIMAGRO já em execução"}
        try:
            mapa_ibge = garantir_mapa_municipios(lock_conn)
            resultados = []
            for janela in janelas:
                if janela not in SIMAGRO_JANELAS:
                    raise ValueError(f"Janela SIMAGRO não suportada: {janela}")
                res = _coletar_janela_simagro(db_url, mapa_ibge, data_ref, janela, acionamento, salvar_banco=True)
                resultados.append(res)
                print(f"   ✓ Janela {janela}: {res['validos']}/{res['recebidos']} municípios (SHA-256: {res['sha256'][:12]})")
            return {"status": "sucesso", "data_referencia": data_ref.isoformat(), "janelas": resultados}
        finally:
            with lock_conn.cursor() as lock_cur:
                lock_cur.execute("SELECT pg_advisory_unlock(%s)", (SIMAGRO_ADVISORY_LOCK_ID,))


if __name__ == "__main__":
    data_arg = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        data_arg = date.fromisoformat(sys.argv[1])
    res = coletar_alertas_simagro(DEFAULT_DB_URL, salvar_banco=True, acionamento="manual", data_referencia=data_arg)
    print(json.dumps(res, ensure_ascii=False, indent=2))
