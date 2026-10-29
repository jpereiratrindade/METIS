#!/usr/bin/env python3
"""
MÉTIS — Motor de Episódios Epistêmicos de Investigação Territorial
Diretriz Científica: METIS-DIR-EVID-001 (v0.1.0)
Converte avisos meteorológicos do INMET em episódios investigativos estruturados,
congelando as condições antecedentes (AdaptaBrasil MCTI) e o estado basal dos modelos MÉTIS (EPS-REF-001).
"""

import os
import sys
import json
from decimal import Decimal
from datetime import datetime, timezone
import psycopg

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DB_URL = os.environ.get("DATABASE_URL", "postgresql://metis:metis@127.0.0.1:5432/metis")
OUTPUT_EPISODIOS_JSON = os.path.join(REPO_ROOT, "web/api/public/episodios_rs.json")

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def processar_episodios_investigacao(db_url: str = DEFAULT_DB_URL):
    print("============================================================")
    print(" MÉTIS — Motor de Episódios Investigativos (METIS-DIR-EVID-001)")
    print("============================================================")

    episodios_criados = 0
    episodios_atualizados = 0

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # 1. Buscar todos os avisos vinculados a municípios do RS (vigentes, futuros ou expirados recentemente)
            cur.execute("""
                SELECT 
                    m.codigo_ibge, m.nome AS municipio_nome,
                    a.id AS aviso_id, a.codigo AS aviso_codigo, a.descricao,
                    a.severidade, a.inicio, a.fim, a.riscos, a.instrucoes,
                    a.encerrado,
                    CASE 
                        WHEN a.encerrado = TRUE THEN 'cancelado'
                        WHEN CURRENT_TIMESTAMP < a.inicio THEN 'futuro'
                        WHEN CURRENT_TIMESTAMP BETWEEN a.inicio AND a.fim THEN 'vigente'
                        ELSE 'expirado'
                    END AS estado_vigencia
                FROM municipios m
                JOIN avisos_meteorologicos_inmet a 
                  ON (m.codigo_ibge = ANY(string_to_array(a.geocodes, ',')) 
                      OR (a.poligono IS NOT NULL AND m.geometria IS NOT NULL AND ST_Intersects(m.geometria, a.poligono)))
                WHERE m.uf = 'RS'
                ORDER BY a.inicio DESC;
            """)
            candidatos = cur.fetchall()
            print(f"-> Ocorrências territoriais identificadas no RS: {len(candidatos)}")

            for row in candidatos:
                ibge = row[0]
                muni_nome = row[1]
                aviso_id = row[2]
                aviso_cod = row[3]
                descricao = row[4]
                severidade = row[5]
                inicio = row[6]
                fim = row[7]
                riscos = row[8] or []
                instrucoes = row[9] or []
                vigencia = row[11]

                # Determinar estado do ciclo de vida epistêmico
                if vigencia == 'futuro':
                    estado_episodio = 'ameaca_anunciada'
                elif vigencia == 'vigente':
                    estado_episodio = 'em_verificacao'
                elif vigencia == 'cancelado':
                    estado_episodio = 'avaliacao_concluida'
                else: # expirado
                    estado_episodio = 'impactos_respostas'

                # Formatar ID único determinístico do episódio
                inicio_str = inicio.strftime("%Y%m%d")
                ep_id = f"EP-{ibge}-INMET-{aviso_id}-{inicio_str}"

                # 2. Obter snapshot das Condições Antecedentes (AdaptaBrasil MCTI)
                cur.execute("""
                    SELECT indicador_id, nome_indicador, ano_referencia, cenario, valor, classe_risco
                    FROM evidencias_adaptabrasil
                    WHERE codigo_ibge = %s
                    ORDER BY indicador_id, ano_referencia, cenario;
                """, (ibge,))
                condicoes = []
                for ind in cur.fetchall():
                    condicoes.append({
                        "indicador_id": ind[0],
                        "nome": ind[1],
                        "ano": ind[2],
                        "cenario": ind[3],
                        "valor": float(ind[4]) if ind[4] is not None else None,
                        "classe": ind[5]
                    })

                # 3. Obter snapshot do Estado Basal MÉTIS (EPS-REF-001 v0.2.0 Vigente)
                cur.execute("""
                    SELECT r.resiliencia, r.ecologica_multiplicador, r.produtiva, r.social, r.status
                    FROM resultados_experimentais r
                    JOIN execucoes_experimentais e ON r.execucao_id = e.id
                    WHERE r.codigo_ibge = %s AND e.modelo_id = 'EPS-REF-001' AND e.ano_referencia = 2017
                    ORDER BY e.executado_em DESC
                    LIMIT 1;
                """, (ibge,))
                res_row = cur.fetchone()
                estado_metis = {}
                if res_row:
                    estado_metis = {
                        "modelo": "EPS-REF-001",
                        "ano_referencia": 2017,
                        "resiliencia": float(res_row[0]) if res_row[0] is not None else None,
                        "ecologica_multiplicador": float(res_row[1]) if res_row[1] is not None else None,
                        "produtiva": float(res_row[2]) if res_row[2] is not None else None,
                        "social": float(res_row[3]) if res_row[3] is not None else None,
                        "status": res_row[4]
                    }

                # 4. Inserir ou atualizar na tabela episodios_investigacao
                cur.execute("""
                    INSERT INTO episodios_investigacao (
                        id, codigo_ibge, aviso_id, aviso_codigo, tipo_ameaca,
                        severidade, janela_inicio, janela_fim, estado_episodio,
                        condicoes_antecedentes, estado_metis_congelado,
                        notas_cientificas, criado_em, atualizado_em
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    ON CONFLICT (codigo_ibge, aviso_codigo) DO UPDATE SET
                        janela_fim = EXCLUDED.janela_fim,
                        estado_episodio = CASE 
                            WHEN episodios_investigacao.estado_episodio = 'avaliacao_concluida' 
                            THEN 'avaliacao_concluida' 
                            ELSE EXCLUDED.estado_episodio 
                        END,
                        atualizado_em = CURRENT_TIMESTAMP
                    RETURNING (xmax = 0);
                """, (
                    ep_id, ibge, aviso_id, aviso_cod, descricao,
                    severidade, inicio, fim, estado_episodio,
                    json.dumps(condicoes), json.dumps(estado_metis),
                    f"Episódio de perturbação deflagrado por aviso INMET '{descricao}' ({severidade}) em {muni_nome}/RS."
                ))
                is_insert = cur.fetchone()[0]
                if is_insert:
                    episodios_criados += 1
                else:
                    episodios_atualizados += 1

            conn.commit()

            # 5. Exportar catálogo consolidado de episódios para consumo web público
            cur.execute("""
                SELECT 
                    e.id, e.codigo_ibge, m.nome AS municipio_nome,
                    e.aviso_codigo, e.tipo_ameaca, e.severidade,
                    e.janela_inicio, e.janela_fim, e.estado_episodio,
                    e.desfecho_cientifico, e.condicoes_antecedentes,
                    e.estado_metis_congelado, e.evidencias_impacto,
                    e.notas_cientificas, e.criado_em, e.atualizado_em
                FROM episodios_investigacao e
                JOIN municipios m ON e.codigo_ibge = m.codigo_ibge
                ORDER BY e.janela_inicio DESC, e.codigo_ibge ASC;
            """)
            episodios_list = []
            episodios_por_muni = {}
            for r in cur.fetchall():
                ep_obj = {
                    "id": r[0],
                    "codigo_ibge": r[1],
                    "municipio": r[2],
                    "aviso_codigo": r[3],
                    "tipo_ameaca": r[4],
                    "severidade": r[5],
                    "janela_inicio": r[6].isoformat() if r[6] else None,
                    "janela_fim": r[7].isoformat() if r[7] else None,
                    "estado_episodio": r[8],
                    "desfecho_cientifico": r[9],
                    "condicoes_antecedentes": r[10] if isinstance(r[10], (list, dict)) else json.loads(r[10] or "[]"),
                    "estado_metis_congelado": r[11] if isinstance(r[11], dict) else json.loads(r[11] or "{}"),
                    "evidencias_impacto": r[12] if isinstance(r[12], (list, dict)) else json.loads(r[12] or "[]"),
                    "notas": r[13],
                    "criado_em": r[14].isoformat() if r[14] else None,
                    "atualizado_em": r[15].isoformat() if r[15] else None
                }
                episodios_list.append(ep_obj)
                ibge_k = r[1]
                if ibge_k not in episodios_por_muni:
                    episodios_por_muni[ibge_k] = []
                episodios_por_muni[ibge_k].append(ep_obj)

    # Gravar arquivo JSON exportado
    payload_export = {
        "metadados": {
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "diretriz": "METIS-DIR-EVID-001 v0.1.0 (Monitoramento de Perturbações e Investigação da Resiliência)",
            "total_episodios": len(episodios_list),
            "municipios_com_episodios": len(episodios_por_muni),
            "estados_distribuicao": {
                "ameaca_anunciada": sum(1 for e in episodios_list if e["estado_episodio"] == "ameaca_anunciada"),
                "em_verificacao": sum(1 for e in episodios_list if e["estado_episodio"] == "em_verificacao"),
                "impactos_respostas": sum(1 for e in episodios_list if e["estado_episodio"] == "impactos_respostas"),
                "avaliacao_concluida": sum(1 for e in episodios_list if e["estado_episodio"] == "avaliacao_concluida")
            }
        },
        "episodios": episodios_list,
        "por_municipio": episodios_por_muni
    }

    os.makedirs(os.path.dirname(OUTPUT_EPISODIOS_JSON), exist_ok=True)
    with open(OUTPUT_EPISODIOS_JSON, "w", encoding="utf-8") as f:
        json.dump(payload_export, f, cls=DecimalEncoder, ensure_ascii=False, indent=2)

    print(f"\n✓ Episódios processados: {episodios_criados} criados, {episodios_atualizados} atualizados.")
    print(f"✓ Artefato exportado: {OUTPUT_EPISODIOS_JSON} ({len(episodios_list)} episódios em {len(episodios_por_muni)} municípios)")
    print("============================================================\n")
    return payload_export

if __name__ == "__main__":
    db = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_URL
    processar_episodios_investigacao(db)
