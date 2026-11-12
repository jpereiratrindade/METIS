#!/usr/bin/env python3
"""
MÉTIS — Sincronizador de Evidências Climáticas e Perturbações (AdaptaBrasil + INMET)
Coordena conectores e valida dados persistidos no PostgreSQL/PostGIS.
Exportação JSON é opcional; API dinâmica é o caminho operacional padrão.
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
INMET_STALE_MINUTES = max(1, int(os.environ.get("METIS_INMET_STALE_MINUTES", "30")))
EXPORTAR_JSON_ESTATICO = os.environ.get("METIS_EXPORT_STATIC_JSON", "0") == "1"

# Garantir importações locais
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))

# Importar conectores
from conector_adaptabrasil import coletar_indicadores_adaptabrasil
from conector_inmet import coletar_avisos_inmet
from conector_simagro import coletar_alertas_simagro

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
        try:
            coletar_alertas_simagro(db_url, salvar_banco=True, acionamento="manual")
        except Exception as e_simagro:
            print(f"[AVISO] Falha ao coletar alertas SIMAGRO-RS: {e_simagro}", file=sys.stderr)

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

            # 2. Carregar avisos estritamente vigentes ou futuros (não encerrados e dentro da janela)
            cur.execute("""
                SELECT 
                    codigo_ibge, aviso_codigo, descricao, severidade, aviso_cor,
                    inicio, fim, estado_vigencia, riscos, instrucoes,
                    afetado_por_geocodigo, afetado_por_intersecao_espacial
                FROM vw_municipios_avisos_inmet
                WHERE uf = 'RS' AND encerrado = FALSE AND estado_vigencia IN ('vigente', 'futuro')
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
                    "estado_vigencia": r[7],
                    "riscos": r[8] or [],
                    "instrucoes": r[9] or [],
                    "via_geocodigo": r[10],
                    "via_espacial": r[11]
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
                        "estado_vigencia": r[7],
                        "municipios_afetados": []
                    }
                avisos_unicos_rs[cod_aviso]["municipios_afetados"].append(ibge)

            # 3. Metadados e montagem do pacote consolidado
            cur.execute("SELECT COUNT(*) FROM municipios WHERE uf = 'RS';")
            total_muni_rs = cur.fetchone()[0]

            cur.execute("SELECT COUNT(DISTINCT (indicador_id, cenario)) FROM evidencias_adaptabrasil;")
            total_ind_config = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM catalogo_indicadores_adaptabrasil;")
            total_catalogo = cur.fetchone()[0]

            cur.execute("SELECT fonte, status, ultima_coleta_sucesso, mensagem FROM status_conectores;")
            status_con = {row[0]: {"status": row[1], "ultima_coleta": row[2].isoformat() if row[2] else None, "mensagem": row[3]} for row in cur.fetchall()}

            cur.execute("""
                SELECT id, iniciada_em, finalizada_em, status, sha256_payload,
                       avisos_recebidos, avisos_validos, versoes_criadas,
                       (finalizada_em < CURRENT_TIMESTAMP - (%s * interval '1 minute')) AS desatualizado
                FROM inmet_coletas
                ORDER BY iniciada_em DESC LIMIT 1;
            """, (INMET_STALE_MINUTES,))
            coleta_row = cur.fetchone()
            ultima_coleta_inmet = None
            if coleta_row:
                ultima_coleta_inmet = {
                    "id": coleta_row[0],
                    "iniciada_em": coleta_row[1].isoformat() if coleta_row[1] else None,
                    "finalizada_em": coleta_row[2].isoformat() if coleta_row[2] else None,
                    "status": coleta_row[3],
                    "sha256_payload": coleta_row[4],
                    "avisos_recebidos": coleta_row[5],
                    "avisos_validos": coleta_row[6],
                    "versoes_criadas": coleta_row[7],
                    "desatualizado": coleta_row[8],
                }

            # 3b. Alertas agroclimáticos recentes SIMAGRO-RS (janela 7d)
            cur.execute("""
                SELECT codigo_ibge, data_referencia, janela, prec, estiagem,
                       estiagem_agricola, geada, t_acima, t_abaixo, itu, ci_ovino, nivel_maximo
                FROM vw_simagro_alertas_recentes
                WHERE janela = '7d'
                ORDER BY codigo_ibge;
            """)
            dados_simagro = {}
            simagro_em_alerta = 0
            for r in cur.fetchall():
                dados_simagro[r[0]] = {
                    "data_referencia": r[1].isoformat(),
                    "janela": r[2],
                    "prec": r[3],
                    "estiagem": r[4],
                    "estiagem_agricola": r[5],
                    "geada": r[6],
                    "t_acima": r[7],
                    "t_abaixo": r[8],
                    "itu": r[9],
                    "ci_ovino": r[10],
                    "nivel_maximo": r[11],
                }
                if r[11] >= 2:
                    simagro_em_alerta += 1

    municipios_export = {}
    for ibge in dados_adapta.keys():
        municipios_export[ibge] = {
            "adaptabrasil": dados_adapta.get(ibge, []),
            "avisos_inmet": dados_inmet_por_muni.get(ibge, []),
            "simagro_alertas": dados_simagro.get(ibge),
        }

    payload_final = {
        "metadados": {
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "universo_territorial": "RS (497 municípios)",
            "diretriz": "METIS-DIR-EVID-001 (Monitoramento de Perturbações e Investigação da Resiliência)",
            "fontes": {
                "adaptabrasil": {
                    "instituicao": "MCTI / AdaptaBrasil",
                    "catalogo_oficial_total": total_catalogo,
                    "indicadores_selecionados": total_ind_config,
                    "municipios_cobertos": len(dados_adapta),
                    "total_observacoes": total_ind_linhas,
                    "status_conector": status_con.get("adaptabrasil", {})
                },
                "inmet": {
                    "instituicao": "INMET / CPTEC / MAPA",
                    "avisos_ativos_rs": len(avisos_unicos_rs),
                    "municipios_sob_alerta": len(dados_inmet_por_muni),
                    "validade_minutos": INMET_STALE_MINUTES,
                    "ultima_coleta_auditada": ultima_coleta_inmet,
                    "status_conector": status_con.get("inmet_avisos", {})
                },
                "simagro": {
                    "instituicao": "SEAPI / DDPA / SIMAGRO-RS",
                    "municipios_cobertos": len(dados_simagro),
                    "municipios_alerta_alto_7d": simagro_em_alerta,
                    "status_conector": status_con.get("simagro_alertas", {})
                }
            }
        },
        "avisos_inmet_ativos": list(avisos_unicos_rs.values()),
        "municipios": municipios_export
    }

    if EXPORTAR_JSON_ESTATICO:
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(payload_final, f, cls=DecimalEncoder, ensure_ascii=False, indent=2)
        tam_kb = os.path.getsize(OUTPUT_JSON) / 1024
        print(f"\n✓ Exportação JSON opcional: {OUTPUT_JSON} ({tam_kb:.1f} KB)")
    else:
        print("\n✓ Evidências disponíveis pela API/PostgreSQL (exportação JSON desativada)")
    print(f"  • Municípios com AdaptaBrasil: {len(dados_adapta)}/{total_muni_rs} (Catálogo oficial: {total_catalogo})")
    print(f"  • Avisos ativos INMET no RS:   {len(avisos_unicos_rs)}")
    print(f"  • Municípios sob alerta agora: {len(dados_inmet_por_muni)}")
    print("============================================================\n")

    # 4. Executar motor de episódios investigativos
    try:
        from motor_episodios import processar_episodios_investigacao
        processar_episodios_investigacao(db_url)
    except Exception as e_ep:
        print(f"[AVISO] Falha ao processar motor de episódios: {e_ep}", file=sys.stderr)

if __name__ == "__main__":
    exec_coleta = "--export-only" not in sys.argv
    db = sys.argv[1] if (len(sys.argv) > 1 and not sys.argv[1].startswith("--")) else DEFAULT_DB_URL
    sincronizar_todas_evidencias(db, executar_coleta=exec_coleta)
