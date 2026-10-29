#!/usr/bin/env python3
"""
MÉTIS — Sincronizador de Evidências Climáticas e Perturbações (AdaptaBrasil + INMET)
Coordena a execução dos conectores, valida os dados persistidos no PostgreSQL/PostGIS
e gera a camada estática auditada em web/api/public/evidencias_rs.json para consulta direta.
"""

import os
import sys
import json
from decimal import Decimal
from datetime import datetime, timezone
import psycopg

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
OUTPUT_JSON = os.path.join(REPO_ROOT, "web/api/public/evidencias_rs.json")
DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")

# Importar conectores
from conector_adaptabrasil import coletar_indicadores_adaptabrasil
from conector_inmet import coletar_avisos_inmet

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def sincronizar_todas_evidencias(db_url: str = DEFAULT_DB_URL, executar_coleta: bool = True):
    print("============================================================")
    print(" MÉTIS — Sincronização Epistêmica de Evidências e Perturbações")
    print("============================================================")

    res_adapta = None
    res_inmet = None

    if executar_coleta:
        res_adapta = coletar_indicadores_adaptabrasil(db_url, salvar_banco=True)
        res_inmet = coletar_avisos_inmet(db_url, salvar_banco=True)

    print("\n-> Compilando repositório de evidências a partir do PostgreSQL...")
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # 1. Carregar indicadores do AdaptaBrasil
            cur.execute("""
                SELECT 
                    codigo_ibge, indicador_id, nome_indicador, ano_referencia,
                    cenario, valor, classe_risco, cor_hex, sha256_origem
                FROM evidencias_adaptabrasil
                ORDER BY codigo_ibge, indicador_id, ano_referencia, cenario;
            """)
            dados_adapta = {}
            total_ind_linhas = 0
            for r in cur.fetchall():
                ibge = r[0]
                if ibge not in dados_adapta:
                    dados_adapta[ibge] = []
                dados_adapta[ibge].append({
                    "indicador_id": r[1],
                    "nome": r[2],
                    "ano": r[3],
                    "cenario": r[4],
                    "valor": float(r[5]) if r[5] is not None else None,
                    "classe": r[6],
                    "cor": r[7]
                })
                total_ind_linhas += 1

            # 2. Carregar avisos ativos e vinculados a municípios do RS
            cur.execute("""
                SELECT 
                    codigo_ibge, aviso_codigo, descricao, severidade, aviso_cor,
                    inicio, fim, riscos, instrucoes,
                    afetado_por_geocodigo, afetado_por_intersecao_espacial
                FROM vw_municipios_avisos_inmet
                WHERE uf = 'RS' AND encerrado = FALSE
                ORDER BY inicio DESC;
            """)
            dados_inmet_por_muni = {}
            avisos_unicos_rs = {}
            for r in cur.fetchall():
                ibge = r[0]
                cod_aviso = r[1]
                if ibge not in dados_inmet_por_muni:
                    dados_inmet_por_muni[ibge] = []

                aviso_item = {
                    "codigo": cod_aviso,
                    "descricao": r[2],
                    "severidade": r[3],
                    "cor": r[4],
                    "inicio": str(r[5]),
                    "fim": str(r[6]),
                    "riscos": r[7] or [],
                    "instrucoes": r[8] or [],
                    "via_geocodigo": r[9],
                    "via_espacial": r[10]
                }
                dados_inmet_por_muni[ibge].append(aviso_item)

                if cod_aviso not in avisos_unicos_rs:
                    avisos_unicos_rs[cod_aviso] = {
                        "codigo": cod_aviso,
                        "descricao": r[2],
                        "severidade": r[3],
                        "cor": r[4],
                        "inicio": str(r[5]),
                        "fim": str(r[6]),
                        "municipios_afetados": []
                    }
                avisos_unicos_rs[cod_aviso]["municipios_afetados"].append(ibge)

            # 3. Metadados e montagem do pacote consolidado
            cur.execute("SELECT COUNT(*) FROM municipios WHERE uf = 'RS';")
            total_muni_rs = cur.fetchone()[0]

    municipios_export = {}
    for ibge in dados_adapta.keys():
        municipios_export[ibge] = {
            "adaptabrasil": dados_adapta.get(ibge, []),
            "avisos_inmet": dados_inmet_por_muni.get(ibge, [])
        }

    payload_final = {
        "metadados": {
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "universo_territorial": "RS (497 municípios)",
            "finalidade": "Camada de Validação Epistêmica e Perturbações Agroterritoriais",
            "fontes": {
                "adaptabrasil": {
                    "instituicao": "MCTI / AdaptaBrasil",
                    "indicadores_cadastrados": len(dados_adapta),
                    "total_observacoes": total_ind_linhas
                },
                "inmet": {
                    "instituicao": "INMET / CPTEC / MAPA",
                    "avisos_ativos_rs": len(avisos_unicos_rs),
                    "municipios_sob_alerta": len(dados_inmet_por_muni)
                }
            }
        },
        "avisos_inmet_ativos": list(avisos_unicos_rs.values()),
        "municipios": municipios_export
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload_final, f, cls=DecimalEncoder, ensure_ascii=False, indent=2)

    tam_kb = os.path.getsize(OUTPUT_JSON) / 1024
    print(f"\n✓ Arquivo de evidências exportado: {OUTPUT_JSON} ({tam_kb:.1f} KB)")
    print(f"  • Municípios com AdaptaBrasil: {len(dados_adapta)}/{total_muni_rs}")
    print(f"  • Avisos ativos INMET no RS:   {len(avisos_unicos_rs)}")
    print(f"  • Municípios sob alerta agora: {len(dados_inmet_por_muni)}")
    print("============================================================\n")

if __name__ == "__main__":
    exec_coleta = "--export-only" not in sys.argv
    db = sys.argv[1] if (len(sys.argv) > 1 and not sys.argv[1].startswith("--")) else DEFAULT_DB_URL
    sincronizar_todas_evidencias(db, executar_coleta=exec_coleta)
