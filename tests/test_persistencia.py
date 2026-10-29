#!/usr/bin/env python3
"""
MÉTIS — Suíte de Testes Automatizados de Persistência Científica Versionada
Validação formal de conformidade com a Prioridade Técnica 001:
1. 497 municípios únicos sem duplicações e geometrias PostGIS válidas.
2. Identidade numérica estrita entre dados brutos no banco e CSV do Censo Agropecuário 2017.
3. Identidade numérica estrita entre resultados no banco e CSV de EPS-REF-001/0.1.0.
4. Identidade numérica estrita para a execução multimodelo vigente.
5. Rastreabilidade epistêmica integral (proveniência, fonte, modelo, versão, parâmetros, manifestos).
6. Integridade criptográfica via hashes SHA-256.
7. Reprodutibilidade determinística em instalação limpa (schema isolado).
"""

import os
import sys
import csv
import json
import hashlib
import math
import unittest
import psycopg

# Garantir raiz do repositório no sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts.importar_dados_banco import importar_todos

DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")
STRICT_MODE = os.environ.get("METIS_STRICT_TESTS") == "1"

def checar_conexao_db(url: str) -> bool:
    try:
        with psycopg.connect(url, connect_timeout=2) as conn:
            return True
    except Exception:
        return False

DB_DISPONIVEL = checar_conexao_db(DB_URL)

def calcular_hash_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

class TestPersistenciaMetis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DB_DISPONIVEL:
            if STRICT_MODE:
                raise AssertionError(
                    f"FALHA CRÍTICA DE HOMOLOGAÇÃO: Banco PostgreSQL/PostGIS inacessível em {DB_URL}. "
                    "Sob modo estrito (METIS_STRICT_TESTS=1), a indisponibilidade do banco impede a homologação."
                )
            raise unittest.SkipTest(
                f"Banco PostgreSQL/PostGIS inacessível em {DB_URL}. "
                "Inicie o serviço executando './scripts/db_up.sh' antes de rodar os testes de persistência."
            )
        cls.conn = psycopg.connect(DB_URL, autocommit=True)
        cls.cur = cls.conn.cursor()

    @classmethod
    def tearDownClass(cls):
        cls.cur.close()
        cls.conn.close()

    def test_01_municipios_contagem_e_unicidade(self):
        """Critério 1: Exatamente 497 municípios do RS, sem duplicações, geocódigos válidos."""
        self.cur.execute("""
            SELECT 
                COUNT(*) AS total,
                COUNT(DISTINCT codigo_ibge) AS unicos,
                COUNT(DISTINCT nome) AS nomes_distintos,
                COUNT(*) FILTER (WHERE uf = 'RS') AS total_rs,
                COUNT(*) FILTER (WHERE length(codigo_ibge) = 7 AND codigo_ibge LIKE '43%') AS codigos_validos
            FROM municipios;
        """)
        row = self.cur.fetchone()
        total, unicos, nomes_distintos, total_rs, codigos_validos = row

        self.assertEqual(total, 497, f"Total de municípios deve ser 497, encontrado: {total}")
        self.assertEqual(unicos, 497, "Não pode haver duplicação de geocódigo IBGE")
        self.assertEqual(total_rs, 497, "Todos os municípios devem pertencer à UF RS")
        self.assertEqual(codigos_validos, 497, "Todos os geocódigos devem ter 7 dígitos iniciando por 43")

    def test_02_postgis_geometrias_validas(self):
        """Critério 1 (espacial): Todas as geometrias PostGIS devem ser válidas e com SRID 4326."""
        self.cur.execute("""
            SELECT 
                COUNT(*) AS total_geom,
                COUNT(*) FILTER (WHERE geometria IS NOT NULL) AS com_geom,
                COUNT(*) FILTER (WHERE ST_SRID(geometria) = 4326) AS srid_4326,
                COUNT(*) FILTER (WHERE GeometryType(geometria) = 'MULTIPOLYGON') AS multipolygon,
                COUNT(*) FILTER (WHERE ST_IsValid(geometria)) AS validas
            FROM municipios;
        """)
        total_geom, com_geom, srid_4326, multipolygon, validas = self.cur.fetchone()

        self.assertEqual(total_geom, 497)
        self.assertEqual(com_geom, 497, "Todos os 497 municípios devem possuir geometria espacial")
        self.assertEqual(srid_4326, 497, "Todas as geometrias devem estar no referencial SRID 4326")
        self.assertEqual(multipolygon, 497, "Todas as geometrias devem ser MultiPolygon")
        self.assertEqual(validas, 497, "Todas as geometrias PostGIS devem ser topologicamente válidas")

    def test_03_observacoes_censitarias_identidade_estrita(self):
        """Critério 2: Dados de entrada no banco devem ser 100% idênticos ao CSV oficial do Censo 2017."""
        csv_path = "data/gerados/municipios_rs_2017_homologado.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            csv_rows = {r["codigo_ibge"].strip(): r for r in csv.DictReader(f)}

        self.assertEqual(len(csv_rows), 497)

        self.cur.execute("""
            SELECT 
                codigo_ibge, ano_referencia,
                area_estabelecimentos_ha, pastagem_natural_ha, mata_natural_ha, valor_producao_reais,
                estabelecimentos_total, estabelecimentos_orientacao_tecnica, estabelecimentos_associados,
                status_observacao
            FROM observacoes_censitarias
            WHERE fonte_id = 'IBGE_CENSO_AGRO_2017' AND ano_referencia = 2017;
        """)
        db_rows = {r[0]: r for r in self.cur.fetchall()}
        self.assertEqual(len(db_rows), 497, "Deve haver 497 observações censitárias no banco")

        divergencias = []
        for ibge, csv_r in csv_rows.items():
            db_r = db_rows.get(ibge)
            self.assertIsNotNone(db_r, f"Município {ibge} não encontrado no banco")

            # Comparar inteiros de contagem
            est_tot_csv = int(csv_r["estabelecimentos_total"])
            est_ori_csv = int(csv_r["estabelecimentos_orientacao_tecnica"])
            est_ass_csv = int(csv_r["estabelecimentos_associados"])

            if db_r[6] != est_tot_csv or db_r[7] != est_ori_csv or db_r[8] != est_ass_csv:
                divergencias.append(f"{ibge}: contagem de estabelecimentos diverge")

            # Comparar floats / nulos
            for idx, col_name in [(2, "area_estabelecimentos_ha"), (3, "pastagem_natural_ha"),
                                  (4, "mata_natural_ha"), (5, "valor_producao_reais")]:
                csv_val = csv_r[col_name].strip()
                db_val = db_r[idx]
                if csv_val == "":
                    if db_val is not None:
                        divergencias.append(f"{ibge} {col_name}: CSV é nulo mas banco tem {db_val}")
                else:
                    csv_f = float(csv_val)
                    db_f = float(db_val)
                    if abs(csv_f - db_f) > 1e-4:
                        divergencias.append(f"{ibge} {col_name}: CSV={csv_f} != DB={db_f}")

        self.assertEqual(len(divergencias), 0, f"Divergências encontradas nas observações: {divergencias[:5]}")

        # Validar contagem formal de incompletos para 2017
        self.cur.execute("SELECT COUNT(*) FROM observacoes_censitarias WHERE ano_referencia = 2017 AND status_observacao = 'dados_incompletos';")
        self.assertEqual(self.cur.fetchone()[0], 5, "Exatamente 5 municípios devem ter status 'dados_incompletos' em 2017")

    def test_04_resultados_v010_identidade_estrita(self):
        """Critério 2: Resultados de EPS-REF-001/0.1.0 no banco devem coincidir exatamente com CSV histórico."""
        csv_path = "results/historico/RS_497_RESULTADOS_v0.1.0_percentil.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            csv_rows = {r["codigo_ibge"].strip(): r for r in csv.DictReader(f)}

        self.assertEqual(len(csv_rows), 497)

        exec_id = "EXEC-HISTORICA-EPS-REF-001-v0.1.0-2017"
        self.cur.execute("""
            SELECT 
                codigo_ibge, ecologica_indice, ecologica_multiplicador, produtiva, social, resiliencia, status
            FROM resultados_experimentais
            WHERE execucao_id = %s;
        """, (exec_id,))
        db_rows = {r[0]: r for r in self.cur.fetchall()}
        self.assertEqual(len(db_rows), 497, "Deve haver 497 resultados para a execução v0.1.0")

        divergencias = []
        for ibge, csv_r in csv_rows.items():
            db_r = db_rows.get(ibge)
            self.assertIsNotNone(db_r, f"Município {ibge} sem resultado v0.1.0 no banco")

            # Status
            status_csv = csv_r["status"].strip()
            status_db = db_r[6].strip()
            if status_csv != status_db:
                divergencias.append(f"{ibge} status: CSV={status_csv} != DB={status_db}")

            # Componentes numéricos
            cols = [
                ("ecologica_indice", 1),
                ("ecologica_multiplicador", 2),
                ("produtiva", 3),
                ("social", 4),
                ("resiliencia", 5),
            ]
            for col_name, db_idx in cols:
                csv_val = csv_r[col_name].strip()
                db_val = db_r[db_idx]
                if csv_val == "":
                    if db_val is not None:
                        divergencias.append(f"{ibge} {col_name}: CSV é vazio mas DB={db_val}")
                else:
                    if db_val is None:
                        divergencias.append(f"{ibge} {col_name}: CSV={csv_val} mas DB é None")
                    else:
                        csv_f = float(csv_val)
                        db_f = float(db_val)
                        # Tolerância de precisão numérica padrão float
                        if abs(csv_f - db_f) > 1e-4:
                            divergencias.append(f"{ibge} {col_name}: CSV={csv_f:.6f} != DB={db_f:.6f}")

        self.assertEqual(len(divergencias), 0, f"Divergências encontradas nos resultados v0.1.0: {divergencias[:5]}")

    def test_05_resultados_v020_multimodelo_identidade_estrita(self):
        """Critério 2: Resultados vigentes multimodelo no banco devem coincidir com RS_497_RESULTADOS.csv."""
        csv_path = "results/RS_497_RESULTADOS.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            csv_rows = {r["codigo_ibge"].strip(): r for r in csv.DictReader(f)}

        self.assertEqual(len(csv_rows), 497)

        exec_id = "EXEC-EXP-EPS-REF-001-v0.2.0-2017"
        self.cur.execute("""
            SELECT 
                codigo_ibge, densidade_monetaria_ha, ecologica_indice, ecologica_multiplicador,
                produtiva, social, resiliencia, status
            FROM resultados_experimentais
            WHERE execucao_id = %s;
        """, (exec_id,))
        db_rows = {r[0]: r for r in self.cur.fetchall()}
        self.assertEqual(len(db_rows), 497)

        divergencias = []
        for ibge, csv_r in csv_rows.items():
            db_r = db_rows.get(ibge)
            self.assertIsNotNone(db_r)

            cols = [
                ("densidade_monetaria_ha", 1),
                ("ecologica_indice", 2),
                ("ecologica_multiplicador", 3),
                ("produtiva", 4),
                ("social", 5),
                ("resiliencia", 6),
            ]
            for col_name, db_idx in cols:
                csv_val = csv_r[col_name].strip()
                db_val = db_r[db_idx]
                if csv_val == "":
                    if db_val is not None:
                        divergencias.append(f"{ibge} {col_name}: CSV vazio != DB={db_val}")
                else:
                    if db_val is None:
                        divergencias.append(f"{ibge} {col_name}: CSV={csv_val} != DB None")
                    else:
                        csv_f = float(csv_val)
                        db_f = float(db_val)
                        if abs(csv_f - db_f) > 1e-4:
                            divergencias.append(f"{ibge} {col_name}: CSV={csv_f:.4f} != DB={db_f:.4f}")

        self.assertEqual(len(divergencias), 0, f"Divergências na execução vigente: {divergencias[:5]}")

    def test_06_associacao_epistemica_e_proveniencia(self):
        """Critério 3: Cada resultado deve associar-se à fonte, modelo, versão, parâmetros e execução."""
        # 1. Consulta pela visão consolidada
        self.cur.execute("""
            SELECT 
                resultado_id, execucao_id, modelo_id, modelo_versao, ano_referencia,
                codigo_ibge, municipio, resiliencia, status, parametros_execucao
            FROM vw_resultados_completos
            WHERE execucao_id = 'EXEC-HISTORICA-EPS-REF-001-v0.1.0-2017'
            LIMIT 5;
        """)
        rows = self.cur.fetchall()
        self.assertEqual(len(rows), 5)
        for r in rows:
            self.assertEqual(r[2], "EPS-REF-001")
            self.assertEqual(r[3], "0.1.0")
            self.assertEqual(r[4], 2017)
            self.assertIn("q10", r[9])
            self.assertIn("q90", r[9])

        # 2. Verificar integridade referencial de chaves estrangeiras
        self.cur.execute("""
            SELECT COUNT(*)
            FROM resultados_experimentais r
            LEFT JOIN execucoes_experimentais e ON e.id = r.execucao_id
            WHERE e.id IS NULL;
        """)
        self.assertEqual(self.cur.fetchone()[0], 0, "Nenhum resultado pode ser órfão de execução")

        self.cur.execute("""
            SELECT COUNT(*)
            FROM execucoes_experimentais e
            LEFT JOIN modelos m ON m.id = e.modelo_id AND m.versao = e.modelo_versao
            WHERE m.id IS NULL;
        """)
        self.assertEqual(self.cur.fetchone()[0], 0, "Nenhuma execução pode ser órfã de modelo")

    def test_07_integridade_criptografica_hashes_sha256(self):
        """Critério 5: Os hashes registrados nas tabelas devem coincidir com os arquivos em disco."""
        # Fontes de dados
        self.cur.execute("SELECT id, arquivo_origem, sha256_origem FROM fontes_dados;")
        for fonte_id, arq, sha_db in self.cur.fetchall():
            self.assertTrue(os.path.isfile(arq), f"Arquivo de fonte não encontrado: {arq}")
            sha_disco = calcular_hash_arquivo(arq)
            self.assertEqual(sha_db, sha_disco, f"Hash da fonte {fonte_id} diverge entre banco e disco")

        # Execuções experimentais
        self.cur.execute("SELECT id, arquivo_saida, sha256_saida, arquivo_manifesto, sha256_manifesto FROM execucoes_experimentais;")
        for exec_id, arq_s, sha_s_db, arq_m, sha_m_db in self.cur.fetchall():
            self.assertTrue(os.path.isfile(arq_s), f"Arquivo de saída não encontrado: {arq_s}")
            self.assertTrue(os.path.isfile(arq_m), f"Arquivo de manifesto não encontrado: {arq_m}")
            self.assertEqual(sha_s_db, calcular_hash_arquivo(arq_s), f"Hash do CSV de saída da execução {exec_id} diverge")
            self.assertEqual(sha_m_db, calcular_hash_arquivo(arq_m), f"Hash do manifesto da execução {exec_id} diverge")

    def test_08_reprodutibilidade_em_instalacao_limpa(self):
        """Critério 4: A estrutura deve poder ser recriada e populada do zero em um schema limpo."""
        schema_teste = "metis_teste_limpo"
        self.cur.execute(f"DROP SCHEMA IF EXISTS {schema_teste} CASCADE;")
        self.cur.execute(f"CREATE SCHEMA {schema_teste};")
        self.cur.execute(f"SET search_path TO {schema_teste}, public;")

        # Executar migrações 001 e 002 no schema de teste
        for mig in ["001_initial_schema.sql", "002_scientific_immutability.sql"]:
            with open(f"db/migrations/{mig}", "r", encoding="utf-8") as f:
                sql_migracao = f.read()
            self.cur.execute(sql_migracao)

        # Executar rotina completa de importação dos dados no schema limpo
        codigo_retorno = importar_todos(DB_URL, forcar=True, schema=schema_teste)
        self.assertEqual(codigo_retorno, 0, "A importação completa no schema limpo deve retornar 0")

        # Verificar se as tabelas foram criadas e populadas no schema limpo
        self.cur.execute(f"SELECT COUNT(*) FROM {schema_teste}.municipios;")
        self.assertEqual(self.cur.fetchone()[0], 497, "Schema limpo deve conter 497 municípios")

        self.cur.execute(f"SELECT COUNT(*) FROM {schema_teste}.observacoes_censitarias;")
        self.assertEqual(self.cur.fetchone()[0], 994, "Schema limpo deve conter 994 observações (497 de 2017 e 497 de 2006)")

        self.cur.execute(f"SELECT COUNT(*) FROM {schema_teste}.execucoes_experimentais;")
        self.assertEqual(self.cur.fetchone()[0], 3, "Schema limpo deve conter 3 execuções registradas")

        self.cur.execute(f"SELECT COUNT(*) FROM {schema_teste}.resultados_experimentais;")
        self.assertEqual(self.cur.fetchone()[0], 1491, "Schema limpo deve conter 1491 resultados experimentais")

        # Restaurar search_path e remover schema de teste
        self.cur.execute("SET search_path TO public;")
        self.cur.execute(f"DROP SCHEMA IF EXISTS {schema_teste} CASCADE;")

    def test_09_observacoes_censitarias_2006_identidade_estrita(self):
        """Critério 2 (Série Histórica): Dados do Censo 2006 no banco devem coincidir 100% com CSV homologado."""
        csv_path = "data/gerados/municipios_rs_2006_homologado.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            csv_rows = {r["codigo_ibge"].strip(): r for r in csv.DictReader(f)}

        self.assertEqual(len(csv_rows), 497)

        self.cur.execute("""
            SELECT 
                codigo_ibge, ano_referencia,
                area_estabelecimentos_ha, pastagem_natural_ha, mata_natural_ha, valor_producao_reais,
                estabelecimentos_total, estabelecimentos_orientacao_tecnica, estabelecimentos_associados,
                status_observacao
            FROM observacoes_censitarias
            WHERE fonte_id = 'IBGE_CENSO_AGRO_2006' AND ano_referencia = 2006;
        """)
        db_rows = {r[0]: r for r in self.cur.fetchall()}
        self.assertEqual(len(db_rows), 497, "Deve haver 497 observações para o Censo 2006 no banco")

        # Verificação metodológica crucial: Pinto Bandeira (4314548) não existia em 2006
        # Os campos censitários devem ser estritamente NULL, e NÃO convertidos para zero!
        self.assertIsNone(db_rows["4314548"][6], "Pinto Bandeira em 2006 deve ter estabelecimentos_total como NULL")
        self.assertIsNone(db_rows["4314548"][7], "Pinto Bandeira em 2006 deve ter orientacao_tecnica como NULL")
        self.assertIsNone(db_rows["4314548"][8], "Pinto Bandeira em 2006 deve ter associados como NULL")

        def _parse_int(val):
            v = val.strip()
            return int(v) if v else None

        divergencias = []
        for ibge, csv_r in csv_rows.items():
            db_r = db_rows.get(ibge)
            self.assertIsNotNone(db_r, f"Município {ibge} não encontrado no banco para 2006")

            est_tot_csv = _parse_int(csv_r["estabelecimentos_total"])
            est_ori_csv = _parse_int(csv_r["estabelecimentos_orientacao_tecnica"])
            est_ass_csv = _parse_int(csv_r["estabelecimentos_associados"])

            if db_r[6] != est_tot_csv or db_r[7] != est_ori_csv or db_r[8] != est_ass_csv:
                divergencias.append(f"{ibge}: contagem de estabelecimentos 2006 diverge (DB={db_r[6]} != CSV={est_tot_csv})")

            for idx, col_name in [(2, "area_estabelecimentos_ha"), (3, "pastagem_natural_ha"),
                                  (4, "mata_natural_ha"), (5, "valor_producao_reais")]:
                csv_val = csv_r[col_name].strip()
                db_val = db_r[idx]
                if csv_val == "":
                    if db_val is not None:
                        divergencias.append(f"{ibge} {col_name}: CSV é nulo mas banco tem {db_val}")
                else:
                    csv_f = float(csv_val)
                    db_f = float(db_val)
                    if abs(csv_f - db_f) > 1e-4:
                        divergencias.append(f"{ibge} {col_name}: CSV={csv_f} != DB={db_f}")

        self.assertEqual(len(divergencias), 0, f"Divergências nas observações 2006: {divergencias[:5]}")

    def test_10_resultados_2006_identidade_estrita(self):
        """Critério 2 (Série Histórica): Resultados do Censo 2006 no banco devem coincidir com RS_497_RESULTADOS_2006.csv."""
        csv_path = "results/RS_497_RESULTADOS_2006.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            csv_rows = {r["codigo_ibge"].strip(): r for r in csv.DictReader(f)}

        self.assertEqual(len(csv_rows), 497)

        exec_id = "EXEC-EXP-EPS-REF-001-v0.2.0-2006"
        self.cur.execute("""
            SELECT 
                codigo_ibge, densidade_monetaria_ha, ecologica_indice, ecologica_multiplicador,
                produtiva, social, resiliencia, status
            FROM resultados_experimentais
            WHERE execucao_id = %s;
        """, (exec_id,))
        db_rows = {r[0]: r for r in self.cur.fetchall()}
        self.assertEqual(len(db_rows), 497, "Deve haver 497 resultados para a execução 2006")

        divergencias = []
        for ibge, csv_r in csv_rows.items():
            db_r = db_rows.get(ibge)
            self.assertIsNotNone(db_r)

            cols = [
                ("densidade_monetaria_ha", 1),
                ("ecologica_indice", 2),
                ("ecologica_multiplicador", 3),
                ("produtiva", 4),
                ("social", 5),
                ("resiliencia", 6),
            ]
            for col_name, db_idx in cols:
                csv_val = csv_r[col_name].strip()
                db_val = db_r[db_idx]
                if csv_val == "":
                    if db_val is not None:
                        divergencias.append(f"{ibge} {col_name}: CSV vazio != DB={db_val}")
                else:
                    if db_val is None:
                        divergencias.append(f"{ibge} {col_name}: CSV={csv_val} != DB None")
                    else:
                        csv_f = float(csv_val)
                        db_f = float(db_val)
                        if abs(csv_f - db_f) > 1e-4:
                            divergencias.append(f"{ibge} {col_name}: CSV={csv_f:.4f} != DB={db_f:.4f}")

        self.assertEqual(len(divergencias), 0, f"Divergências na execução 2006: {divergencias[:5]}")

    def test_11_imutabilidade_cientifica_bloqueio_de_mutacao(self):
        """Critério 3: O PostgreSQL deve barrar ativamente UPDATE ou DELETE em execuções e resultados homologados."""
        exec_id = "EXEC-HISTORICA-EPS-REF-001-v0.1.0-2017"

        # 1. Tentar UPDATE em execução homologada imutável
        with self.assertRaises(psycopg.Error) as ctx_exec:
            self.cur.execute(
                "UPDATE execucoes_experimentais SET parametros = '{\"hack\": true}'::jsonb WHERE id = %s;",
                (exec_id,)
            )
        self.assertIn("VIOLAÇÃO DE IMUTABILIDADE CIENTÍFICA", str(ctx_exec.exception))

        # 2. Tentar UPDATE em resultado de execução imutável
        with self.assertRaises(psycopg.Error) as ctx_res_up:
            self.cur.execute(
                "UPDATE resultados_experimentais SET resiliencia = 99.99 WHERE execucao_id = %s AND codigo_ibge = '4300034';",
                (exec_id,)
            )
        self.assertIn("VIOLAÇÃO DE IMUTABILIDADE CIENTÍFICA", str(ctx_res_up.exception))

        # 3. Tentar DELETE em resultado de execução imutável
        with self.assertRaises(psycopg.Error) as ctx_res_del:
            self.cur.execute(
                "DELETE FROM resultados_experimentais WHERE execucao_id = %s AND codigo_ibge = '4300034';",
                (exec_id,)
            )
        self.assertIn("VIOLAÇÃO DE IMUTABILIDADE CIENTÍFICA", str(ctx_res_del.exception))

    def test_12_evidencias_climaticas_e_inmet(self):
        """Critério 6: Migração 003 e integração epistêmica de AdaptaBrasil e avisos INMET."""
        # 1. Verificar cobertura de AdaptaBrasil para os 497 municípios
        self.cur.execute("""
            SELECT COUNT(DISTINCT codigo_ibge) 
            FROM evidencias_adaptabrasil;
        """)
        muni_adapta = self.cur.fetchone()[0]
        self.assertEqual(muni_adapta, 497, f"AdaptaBrasil deve cobrir 497 municípios, obtido {muni_adapta}")

        # 2. Verificar integridade da tabela de avisos INMET
        self.cur.execute("SELECT COUNT(*) FROM avisos_meteorologicos_inmet;")
        total_avisos = self.cur.fetchone()[0]
        self.assertGreaterEqual(total_avisos, 1, "Deve haver ao menos 1 aviso meteorológico registrado")

        # 3. Verificar que a View espacial PostGIS executa sem erros
        self.cur.execute("SELECT COUNT(*) FROM vw_municipios_avisos_inmet WHERE uf = 'RS';")
        total_muni_afetados = self.cur.fetchone()[0]
        self.assertIsInstance(total_muni_afetados, int)

        # 4. Verificar existência e conformidade do artefato JSON consolidado
        json_path = os.path.join(REPO_ROOT, "web/api/public/evidencias_rs.json")
        self.assertTrue(os.path.exists(json_path), f"Arquivo {json_path} deve existir")
        with open(json_path, "r", encoding="utf-8") as f:
            dados = json.load(f)
        self.assertIn("metadados", dados)
        self.assertIn("municipios", dados)
        self.assertEqual(len(dados["municipios"]), 497, "JSON consolidado deve cobrir exatamente 497 municípios")

if __name__ == "__main__":
    unittest.main()
