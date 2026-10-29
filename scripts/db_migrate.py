#!/usr/bin/env python3
"""
MÉTIS — Gerenciador de Migrações SQL Versionadas
Executa migrações na ordem estrita e registra hashes SHA-256 na tabela `registro_migracoes`.
"""

import os
import sys
import hashlib
import glob
import psycopg

DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")

def calcular_sha256(conteudo: str) -> str:
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()

def aplicar_migracoes(db_url: str = DEFAULT_DB_URL, migrations_dir: str = "db/migrations") -> int:
    print(f"=== MÉTIS: Execução de Migrações SQL ===")
    print(f"Conexão: {db_url}")
    print(f"Diretório: {migrations_dir}")

    if not os.path.isdir(migrations_dir):
        print(f"ERRO: Diretório de migrações '{migrations_dir}' não encontrado.")
        return 1

    arquivos_migracao = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
    if not arquivos_migracao:
        print(f"Nenhum arquivo SQL encontrado em {migrations_dir}.")
        return 0

    try:
        with psycopg.connect(db_url, autocommit=False) as conn:
            with conn.cursor() as cur:
                # 1. Assegurar tabela de controle de migrações
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS registro_migracoes (
                        versao VARCHAR(50) PRIMARY KEY,
                        nome VARCHAR(150) NOT NULL,
                        sha256 VARCHAR(64) NOT NULL,
                        aplicado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.commit()

                # 2. Obter migrações já aplicadas
                cur.execute("SELECT versao, sha256 FROM registro_migracoes ORDER BY versao;")
                migracoes_aplicadas = {row[0]: row[1] for row in cur.fetchall()}

                aplicadas_nesta_execucao = 0

                for caminho_arq in arquivos_migracao:
                    nome_arquivo = os.path.basename(caminho_arq)
                    versao = nome_arquivo.split("_")[0]

                    with open(caminho_arq, "r", encoding="utf-8") as f:
                        conteudo_sql = f.read()

                    sha256_atual = calcular_sha256(conteudo_sql)

                    if versao in migracoes_aplicadas:
                        sha_registrado = migracoes_aplicadas[versao]
                        if sha_registrado != sha256_atual:
                            print(f"[ALERTA] Migração {versao} ({nome_arquivo}) já foi aplicada com SHA diferente!")
                            print(f"  Registrado: {sha_registrado}")
                            print(f"  Atual:      {sha256_atual}")
                        else:
                            print(f"[SKIP] Migração {versao} ({nome_arquivo}) já aplicada.")
                        continue

                    print(f"[APLICANDO] {versao} ({nome_arquivo}) ...")
                    cur.execute(conteudo_sql)
                    cur.execute("""
                        INSERT INTO registro_migracoes (versao, nome, sha256, aplicado_em)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP);
                    """, (versao, nome_arquivo, sha256_atual))
                    conn.commit()
                    aplicadas_nesta_execucao += 1
                    print(f"  -> Concluída com sucesso (SHA-256: {sha256_atual[:12]}...)")

            print(f"=== Migrações finalizadas com sucesso! (Novas aplicadas: {aplicadas_nesta_execucao}) ===\n")
            return 0
    except Exception as e:
        print(f"ERRO ao executar migrações: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    db_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_URL
    sys.exit(aplicar_migracoes(db_url))
