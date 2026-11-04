-- METIS-DIR-INMET-002: consolidação operacional e separação de ciclos de vida

-- O conector anterior inferia encerramento pela ausência no feed. Sem payload que
-- comprove cancelamento, registros legados não podem ser classificados como cancelados.
ALTER TABLE avisos_meteorologicos_inmet DROP CONSTRAINT IF EXISTS ck_inmet_situacao_origem;
ALTER TABLE avisos_meteorologicos_inmet ADD CONSTRAINT ck_inmet_situacao_origem
    CHECK (situacao_origem IN ('ativo', 'cancelado', 'indeterminado'));

UPDATE avisos_meteorologicos_inmet
SET situacao_origem = 'indeterminado'
WHERE situacao_origem = 'cancelado' AND ultima_coleta_id IS NULL;

-- Cancelamento meteorológico não encerra investigação científica. Episódios em aberto
-- retornam à fase de coleta de impactos; conclusões científicas explícitas são preservadas.
UPDATE episodios_investigacao e
SET estado_episodio = 'impactos_respostas', atualizado_em = CURRENT_TIMESTAMP
FROM avisos_meteorologicos_inmet a
WHERE e.aviso_id = a.id
  AND a.situacao_origem IN ('cancelado', 'indeterminado')
  AND e.estado_episodio = 'avaliacao_concluida'
  AND e.desfecho_cientifico = 'em_aberto';

DROP VIEW IF EXISTS vw_municipios_avisos_inmet;
CREATE VIEW vw_municipios_avisos_inmet AS
SELECT
    m.codigo_ibge, m.nome AS municipio_nome, m.uf,
    a.id AS aviso_id, a.codigo AS aviso_codigo, a.descricao, a.severidade,
    a.aviso_cor, a.inicio, a.fim,
    (a.situacao_origem = 'cancelado') AS encerrado,
    CASE
        WHEN a.situacao_origem = 'cancelado' THEN 'cancelado'
        WHEN a.situacao_origem = 'indeterminado' THEN 'indeterminado'
        WHEN CURRENT_TIMESTAMP < a.inicio THEN 'futuro'
        WHEN CURRENT_TIMESTAMP <= a.fim THEN 'vigente'
        ELSE 'expirado'
    END AS estado_vigencia,
    a.riscos, a.instrucoes,
    (m.codigo_ibge = ANY(string_to_array(a.geocodes, ','))) AS afetado_por_geocodigo,
    CASE WHEN a.poligono IS NOT NULL AND m.geometria IS NOT NULL
         THEN ST_Intersects(m.geometria, a.poligono) ELSE FALSE END AS afetado_por_intersecao_espacial
FROM municipios m
JOIN avisos_meteorologicos_inmet a
  ON (m.codigo_ibge = ANY(string_to_array(a.geocodes, ','))
      OR (a.poligono IS NOT NULL AND m.geometria IS NOT NULL AND ST_Intersects(m.geometria, a.poligono)));

COMMENT ON COLUMN avisos_meteorologicos_inmet.situacao_origem IS
    'Estado declarado pelo provedor; indeterminado identifica legado sem prova de cancelamento.';
