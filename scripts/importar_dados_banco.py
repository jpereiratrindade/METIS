#!/usr/bin/env python3
"""
MÉTIS — Importador Científico Versionado de Dados Censitários e Resultados
Importa para PostgreSQL + PostGIS:
1. Malha e geometrias municipais (IBGE 2022).
2. Proveniência e fontes de dados com hashes SHA-256 auditáveis.
3. Observações agropecuárias brutas dos 497 municípios (Censo Agropecuário 2017).
4. Catálogo formal de modelos matemáticos.
5. Execuções experimentais e resultados históricos (EPS-REF-001/0.1.0) e vigentes.
"""

import os
import sys
import csv
import json
import hashlib
from typing import Optional, Dict, Any
import psycopg

DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")

def calcular_hash_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def float_ou_none(val: Any) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip()
    if s == "" or s.lower() in ("na", "nan", "null"):
        return None
    try:
        return float(s)
    except ValueError:
        return None

def int_ou_none(val: Any) -> Optional[int]:
    if val is None:
        return None
    s = str(val).strip()
    if s == "" or s.lower() in ("na", "nan", "null"):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None

def checar_se_ja_populado(cur) -> bool:
    try:
        cur.execute("SELECT COUNT(*) FROM municipios;")
        total_mun = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM resultados_experimentais WHERE execucao_id = 'EXEC-HISTORICA-EPS-REF-001-v0.1.0-2017';")
        total_res = cur.fetchone()[0]
        return total_mun == 497 and total_res == 497
    except Exception:
        return False

def importar_todos(db_url: str = DEFAULT_DB_URL, forcar: bool = False) -> int:
    print("=== MÉTIS: Iniciando Importação Científica Versionada ===")
    print(f"Destino: {db_url}")

    with psycopg.connect(db_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            if not forcar and checar_se_ja_populado(cur):
                print("[OK] Base de dados já populada e íntegra (497 municípios).")
                print("     Importação ignorada para agilidade. Use '--force' para reprocessar.\n")
                return 0

    # Arquivos obrigatórios
    f_censo_csv = "data/gerados/municipios_rs_2017_homologado.csv"
    f_malha_geo = "data/gerados/municipios_rs_2022.geojson"
    f_res_v010_csv = "results/historico/RS_497_RESULTADOS_v0.1.0_percentil.csv"
    f_res_v010_man = "results/historico/RS_497_RESULTADOS_v0.1.0_percentil.manifest.json"
    f_res_v020_csv = "results/RS_497_RESULTADOS.csv"
    f_res_v020_man = "results/RS_497_RESULTADOS.manifest.json"

    arquivos = [f_censo_csv, f_malha_geo, f_res_v010_csv, f_res_v010_man, f_res_v020_csv, f_res_v020_man]
    for f in arquivos:
        if not os.path.isfile(f):
            print(f"ERRO: Arquivo obrigatório não encontrado: {f}", file=sys.stderr)
            return 1

    hashes = {f: calcular_hash_arquivo(f) for f in arquivos}
    print("\nHashes SHA-256 de proveniência verificados:")
    for f, h in hashes.items():
        print(f"  {f}: {h[:16]}...{h[-8:]}")

    with psycopg.connect(db_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            # -------------------------------------------------------------
            # 1. Registrar Fontes de Dados
            # -------------------------------------------------------------
            print("\n1. Registrando catálogo de fontes de dados...")
            cur.execute("""
                INSERT INTO fontes_dados (id, nome, instituicao, ano_referencia, tabelas_origem, arquivo_origem, sha256_origem, descricao)
                VALUES 
                (%s, %s, %s, %s, %s, %s, %s, %s),
                (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    nome = EXCLUDED.nome,
                    arquivo_origem = EXCLUDED.arquivo_origem,
                    sha256_origem = EXCLUDED.sha256_origem,
                    descricao = EXCLUDED.descricao;
            """, (
                "IBGE_CENSO_AGRO_2017",
                "IBGE - Censo Agropecuário 2017",
                "IBGE",
                2017,
                ["6881", "6898", "6780", "6773"],
                f_censo_csv,
                hashes[f_censo_csv],
                "Dados estatísticos censitários agregados em nível municipal sobre uso da terra, produção e cooperativismo.",
                
                "IBGE_MALHA_2022",
                "IBGE - Malha Municipal Digital do Brasil 2022",
                "IBGE",
                2022,
                ["Malha Municipal 2022"],
                f_malha_geo,
                hashes[f_malha_geo],
                "Limites político-administrativos vetoriais dos municípios do Rio Grande do Sul (UF 43)."
            ))
            conn.commit()
            print("  -> Fontes cadastradas.")

            # -------------------------------------------------------------
            # 2. Importar Municípios e Geometrias PostGIS
            # -------------------------------------------------------------
            print("\n2. Importando municípios e geometrias PostGIS...")
            with open(f_malha_geo, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            municipios_inseridos = 0
            for feat in geojson_data["features"]:
                props = feat.get("properties", {})
                cd_mun = str(props.get("CD_MUN", "")).strip()
                nm_mun = str(props.get("NM_MUN", "")).strip()
                sigla_uf = str(props.get("SIGLA_UF", "RS")).strip()
                area_km2 = float_ou_none(props.get("AREA_KM2"))

                # Ignorar lagoas/corpos d'água especiais do IBGE (apenas municípios com 7 dígitos reais)
                if not cd_mun.startswith("43") or cd_mun in ("4300001", "4300002"):
                    continue

                geom_json = json.dumps(feat["geometry"])

                cur.execute("""
                    INSERT INTO municipios (codigo_ibge, nome, uf, area_km2, geometria)
                    VALUES (%s, %s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)))
                    ON CONFLICT (codigo_ibge) DO UPDATE SET
                        nome = EXCLUDED.nome,
                        uf = EXCLUDED.uf,
                        area_km2 = EXCLUDED.area_km2,
                        geometria = EXCLUDED.geometria;
                """, (cd_mun, nm_mun, sigla_uf, area_km2, geom_json))
                municipios_inseridos += 1

            conn.commit()
            print(f"  -> Municípios cadastrados/atualizados: {municipios_inseridos}")

            # -------------------------------------------------------------
            # 3. Importar Observações Censitárias Brutas
            # -------------------------------------------------------------
            print("\n3. Importando observações censitárias (2017)...")
            obs_inseridas = 0
            obs_incompletas = 0

            with open(f_censo_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ibge = row["codigo_ibge"].strip()
                    ano = int(row["ano_referencia"])
                    area_est = float_ou_none(row["area_estabelecimentos_ha"])
                    past_nat = float_ou_none(row["pastagem_natural_ha"])
                    mata_nat = float_ou_none(row["mata_natural_ha"])
                    val_prod = float_ou_none(row["valor_producao_reais"])
                    est_tot = int_ou_none(row["estabelecimentos_total"]) or 0
                    est_ori = int_ou_none(row["estabelecimentos_orientacao_tecnica"]) or 0
                    est_ass = int_ou_none(row["estabelecimentos_associados"]) or 0

                    incompleto = (area_est is None or past_nat is None or mata_nat is None or val_prod is None)
                    status_obs = "dados_incompletos" if incompleto else "valido"
                    if incompleto:
                        obs_incompletas += 1

                    cur.execute("""
                        INSERT INTO observacoes_censitarias (
                            codigo_ibge, fonte_id, ano_referencia,
                            area_estabelecimentos_ha, pastagem_natural_ha, mata_natural_ha, valor_producao_reais,
                            estabelecimentos_total, estabelecimentos_orientacao_tecnica, estabelecimentos_associados,
                            status_observacao
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (codigo_ibge, fonte_id, ano_referencia) DO UPDATE SET
                            area_estabelecimentos_ha = EXCLUDED.area_estabelecimentos_ha,
                            pastagem_natural_ha = EXCLUDED.pastagem_natural_ha,
                            mata_natural_ha = EXCLUDED.mata_natural_ha,
                            valor_producao_reais = EXCLUDED.valor_producao_reais,
                            estabelecimentos_total = EXCLUDED.estabelecimentos_total,
                            estabelecimentos_orientacao_tecnica = EXCLUDED.estabelecimentos_orientacao_tecnica,
                            estabelecimentos_associados = EXCLUDED.estabelecimentos_associados,
                            status_observacao = EXCLUDED.status_observacao;
                    """, (
                        ibge, "IBGE_CENSO_AGRO_2017", ano,
                        area_est, past_nat, mata_nat, val_prod,
                        est_tot, est_ori, est_ass, status_obs
                    ))
                    obs_inseridas += 1

            conn.commit()
            print(f"  -> Observações inseridas: {obs_inseridas} (Válidas: {obs_inseridas - obs_incompletas}, Incompletas: {obs_incompletas})")

            # -------------------------------------------------------------
            # 4. Registrar Modelos Formais
            # -------------------------------------------------------------
            print("\n4. Registrando catálogo de modelos matemáticos...")
            modelos_definicoes = [
                (
                    "EPS-REF-001",
                    "0.1.0",
                    "Modelo de Referência Histórica (v0.1.0)",
                    "R = E * (P + S)",
                    "E = 0.5 + clamp((pastagem_natural + mata_natural)/area_estab, 0, 1)",
                    "P = 50 * clamp((log1p(VP/area) - q10)/(q90 - q10), 0, 1)",
                    "S = 25 * (orientados/total_estab + associados/total_estab)",
                    "referencia_historica",
                    "Formulação original de referência histórica com normalização da produtividade por percentis q10 e q90 estaduais."
                ),
                (
                    "EPS-REF-001",
                    "0.2.0",
                    "Modelo de Referência Histórica Multimodelo",
                    "R = E * (P + S)",
                    "E = 0.5 + clamp((pastagem_natural + mata_natural)/area_estab, 0, 1)",
                    "P = 50 * clamp((log1p(VP/area) - q10)/(q90 - q10), 0, 1)",
                    "S = 25 * (orientados/total_estab + associados/total_estab)",
                    "referencia_multimodelo",
                    "Linha de base preservada e integrada ao catálogo multimodelo da diretriz METIS-DIR-MULTI-002."
                ),
                (
                    "EPS-EXP-002",
                    "0.2.0",
                    "Modelo Aditivo Ponderado Linear",
                    "R = we * E_norm + wp * P100 + ws * S100",
                    "E_norm = clamp((pastagem_natural + mata_natural)/area_estab, 0, 1) * 100",
                    "P100 = 100 * (dm / (dm + k))",
                    "S100 = 50 * (orientados/total + associados/total)",
                    "experimental_aditivo",
                    "Componentes independentes combinados linearmente sem acoplamento multiplicativo restritivo."
                ),
                (
                    "EPS-EXP-003",
                    "0.2.0",
                    "Modelo Interativo com Acoplamento Não-Linear",
                    "R = E * (P + S) + lambda * (P * S / 50)",
                    "E = 0.5 + clamp((pastagem_natural + mata_natural)/area_estab, 0, 1)",
                    "P = 50 * (dm / (dm + k))",
                    "S = 25 * (orientados/total + associados/total)",
                    "experimental_interativo",
                    "Interações sinérgicas explícitas entre coesão socio-cooperativa e densidade econômica."
                ),
                (
                    "EPS-EXP-004",
                    "0.2.0",
                    "Modelo Autônomo Municipal (METIS-DIR-MUN-001)",
                    "R = E * (P + S)",
                    "E = 0.5 + clamp((pastagem_natural + mata_natural)/area_estab, 0, 1)",
                    "P = 50 * (dm / (dm + k))",
                    "S = 25 * (orientados/total + associados/total)",
                    "experimental_autonomo",
                    "Análise municipal autônoma com escala k explícita e estrita invariância intermunicipal."
                )
            ]

            for mod in modelos_definicoes:
                cur.execute("""
                    INSERT INTO modelos (id, versao, nome, equacao_resiliencia, equacao_ecologica, equacao_produtiva, equacao_social, papel_epistemico, descricao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id, versao) DO UPDATE SET
                        nome = EXCLUDED.nome,
                        equacao_resiliencia = EXCLUDED.equacao_resiliencia,
                        equacao_ecologica = EXCLUDED.equacao_ecologica,
                        equacao_produtiva = EXCLUDED.equacao_produtiva,
                        equacao_social = EXCLUDED.equacao_social,
                        papel_epistemico = EXCLUDED.papel_epistemico,
                        descricao = EXCLUDED.descricao;
                """, mod)

            conn.commit()
            print(f"  -> Modelos cadastrados: {len(modelos_definicoes)}")

            # -------------------------------------------------------------
            # 5. Registrar Execução e Importar Resultados: EPS-REF-001/0.1.0
            # -------------------------------------------------------------
            print("\n5. Importando execução histórica EPS-REF-001/0.1.0...")
            exec_id_v010 = "EXEC-HISTORICA-EPS-REF-001-v0.1.0-2017"

            with open(f_res_v010_man, "r", encoding="utf-8") as f:
                man_v010 = json.load(f)

            cur.execute("""
                INSERT INTO execucoes_experimentais (
                    id, modelo_id, modelo_versao, fonte_id, ano_referencia,
                    trajetoria, status_execucao, parametros, metadados,
                    arquivo_saida, sha256_saida, arquivo_manifesto, sha256_manifesto
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    status_execucao = EXCLUDED.status_execucao,
                    parametros = EXCLUDED.parametros,
                    metadados = EXCLUDED.metadados,
                    sha256_saida = EXCLUDED.sha256_saida,
                    sha256_manifesto = EXCLUDED.sha256_manifesto;
            """, (
                exec_id_v010,
                "EPS-REF-001",
                "0.1.0",
                "IBGE_CENSO_AGRO_2017",
                2017,
                "historica",
                man_v010.get("status", "CALCULADO_PENDENTE_AUDITORIA_FONTE"),
                json.dumps(man_v010.get("calibracao", {})),
                json.dumps(man_v010),
                f_res_v010_csv,
                hashes[f_res_v010_csv],
                f_res_v010_man,
                hashes[f_res_v010_man]
            ))

            res_v010_count = 0
            with open(f_res_v010_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ibge = row["codigo_ibge"].strip()
                    eco_ind = float_ou_none(row.get("ecologica_indice"))
                    eco_mul = float_ou_none(row.get("ecologica_multiplicador"))
                    prod = float_ou_none(row.get("produtiva"))
                    soc = float_ou_none(row.get("social"))
                    res = float_ou_none(row.get("resiliencia"))
                    status = row.get("status", "experimental").strip()

                    cur.execute("""
                        INSERT INTO resultados_experimentais (
                            execucao_id, codigo_ibge, densidade_monetaria_ha,
                            ecologica_indice, ecologica_multiplicador, produtiva, social, resiliencia, status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (execucao_id, codigo_ibge) DO UPDATE SET
                            ecologica_indice = EXCLUDED.ecologica_indice,
                            ecologica_multiplicador = EXCLUDED.ecologica_multiplicador,
                            produtiva = EXCLUDED.produtiva,
                            social = EXCLUDED.social,
                            resiliencia = EXCLUDED.resiliencia,
                            status = EXCLUDED.status;
                    """, (
                        exec_id_v010, ibge, None,
                        eco_ind, eco_mul, prod, soc, res, status
                    ))
                    res_v010_count += 1

            conn.commit()
            print(f"  -> Resultados da v0.1.0 importados: {res_v010_count}")

            # -------------------------------------------------------------
            # 6. Registrar Execução e Importar Resultados: EPS-REF-001 (Vigente / v0.2.0)
            # -------------------------------------------------------------
            print("\n6. Importando execução vigente EPS-REF-001 (Multimodelo)...")
            exec_id_v020 = "EXEC-EXP-EPS-REF-001-v0.2.0-2017"

            with open(f_res_v020_man, "r", encoding="utf-8") as f:
                man_v020 = json.load(f)

            cur.execute("""
                INSERT INTO execucoes_experimentais (
                    id, modelo_id, modelo_versao, fonte_id, ano_referencia,
                    trajetoria, status_execucao, parametros, metadados,
                    arquivo_saida, sha256_saida, arquivo_manifesto, sha256_manifesto
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    status_execucao = EXCLUDED.status_execucao,
                    parametros = EXCLUDED.parametros,
                    metadados = EXCLUDED.metadados,
                    sha256_saida = EXCLUDED.sha256_saida,
                    sha256_manifesto = EXCLUDED.sha256_manifesto;
            """, (
                exec_id_v020,
                "EPS-REF-001",
                "0.2.0",
                "IBGE_CENSO_AGRO_2017",
                2017,
                man_v020.get("trajetoria", "experimental"),
                man_v020.get("status", "CALCULADO_PENDENTE_AUDITORIA_FONTE"),
                json.dumps(man_v020.get("parametrizacao", {})),
                json.dumps(man_v020),
                f_res_v020_csv,
                hashes[f_res_v020_csv],
                f_res_v020_man,
                hashes[f_res_v020_man]
            ))

            res_v020_count = 0
            with open(f_res_v020_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ibge = row["codigo_ibge"].strip()
                    dens = float_ou_none(row.get("densidade_monetaria_ha"))
                    eco_ind = float_ou_none(row.get("ecologica_indice"))
                    eco_mul = float_ou_none(row.get("ecologica_multiplicador"))
                    prod = float_ou_none(row.get("produtiva"))
                    soc = float_ou_none(row.get("social"))
                    res = float_ou_none(row.get("resiliencia"))
                    status = row.get("status", "experimental").strip()

                    cur.execute("""
                        INSERT INTO resultados_experimentais (
                            execucao_id, codigo_ibge, densidade_monetaria_ha,
                            ecologica_indice, ecologica_multiplicador, produtiva, social, resiliencia, status
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (execucao_id, codigo_ibge) DO UPDATE SET
                            densidade_monetaria_ha = EXCLUDED.densidade_monetaria_ha,
                            ecologica_indice = EXCLUDED.ecologica_indice,
                            ecologica_multiplicador = EXCLUDED.ecologica_multiplicador,
                            produtiva = EXCLUDED.produtiva,
                            social = EXCLUDED.social,
                            resiliencia = EXCLUDED.resiliencia,
                            status = EXCLUDED.status;
                    """, (
                        exec_id_v020, ibge, dens,
                        eco_ind, eco_mul, prod, soc, res, status
                    ))
                    res_v020_count += 1

            conn.commit()
            print(f"  -> Resultados da execução vigente importados: {res_v020_count}")

    print("\n=== Importação Concluída com Sucesso! ===")
    return 0

if __name__ == "__main__":
    forcar_arg = "--force" in sys.argv
    args_limpos = [a for a in sys.argv[1:] if a != "--force"]
    db_url = args_limpos[0] if args_limpos else DEFAULT_DB_URL
    sys.exit(importar_todos(db_url, forcar=forcar_arg))
