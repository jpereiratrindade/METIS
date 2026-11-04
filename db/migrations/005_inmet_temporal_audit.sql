-- METIS-DIR-INMET-002: sincronizacao, versionamento e historico INMET

CREATE TABLE IF NOT EXISTS inmet_coletas (
    id BIGSERIAL PRIMARY KEY,
    iniciada_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finalizada_em TIMESTAMPTZ,
    origem_url TEXT NOT NULL,
    acionamento VARCHAR(20) NOT NULL DEFAULT 'manual'
        CHECK (acionamento IN ('manual', 'agendado', 'api', 'teste')),
    status VARCHAR(30) NOT NULL DEFAULT 'iniciada'
        CHECK (status IN ('iniciada', 'sucesso', 'falha_rede', 'falha_validacao', 'falha_persistencia')),
    http_status INTEGER,
    sha256_payload VARCHAR(64),
    arquivo_payload TEXT,
    avisos_recebidos INTEGER NOT NULL DEFAULT 0,
    avisos_validos INTEGER NOT NULL DEFAULT 0,
    versoes_criadas INTEGER NOT NULL DEFAULT 0,
    mensagem TEXT
);

CREATE INDEX IF NOT EXISTS idx_inmet_coletas_iniciada ON inmet_coletas(iniciada_em DESC);
CREATE INDEX IF NOT EXISTS idx_inmet_coletas_status ON inmet_coletas(status, iniciada_em DESC);

ALTER TABLE avisos_meteorologicos_inmet
    ADD COLUMN IF NOT EXISTS situacao_origem VARCHAR(20) NOT NULL DEFAULT 'ativo',
    ADD COLUMN IF NOT EXISTS primeira_observacao_em TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS ultima_observacao_em TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS ultima_coleta_id BIGINT REFERENCES inmet_coletas(id) ON DELETE RESTRICT;

UPDATE avisos_meteorologicos_inmet
SET primeira_observacao_em = COALESCE(primeira_observacao_em, consultado_em),
    ultima_observacao_em = COALESCE(ultima_observacao_em, consultado_em),
    situacao_origem = CASE WHEN encerrado THEN 'cancelado' ELSE 'ativo' END
WHERE primeira_observacao_em IS NULL OR ultima_observacao_em IS NULL;

ALTER TABLE avisos_meteorologicos_inmet
    DROP CONSTRAINT IF EXISTS ck_inmet_situacao_origem;
ALTER TABLE avisos_meteorologicos_inmet
    ADD CONSTRAINT ck_inmet_situacao_origem
    CHECK (situacao_origem IN ('ativo', 'cancelado'));

CREATE TABLE IF NOT EXISTS inmet_avisos_versoes (
    id BIGSERIAL PRIMARY KEY,
    aviso_id BIGINT NOT NULL REFERENCES avisos_meteorologicos_inmet(id) ON DELETE RESTRICT,
    coleta_id BIGINT NOT NULL REFERENCES inmet_coletas(id) ON DELETE RESTRICT,
    fingerprint_sha256 VARCHAR(64) NOT NULL,
    descricao VARCHAR(150) NOT NULL,
    severidade VARCHAR(50) NOT NULL,
    aviso_cor VARCHAR(10),
    inicio TIMESTAMPTZ NOT NULL,
    fim TIMESTAMPTZ NOT NULL,
    poligono geometry(Geometry, 4326),
    geocodes TEXT,
    municipios_texto TEXT,
    riscos TEXT[] NOT NULL DEFAULT '{}',
    instrucoes TEXT[] NOT NULL DEFAULT '{}',
    situacao_origem VARCHAR(20) NOT NULL DEFAULT 'ativo'
        CHECK (situacao_origem IN ('ativo', 'cancelado')),
    observado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_inmet_aviso_coleta UNIQUE (aviso_id, coleta_id)
);

CREATE INDEX IF NOT EXISTS idx_inmet_versoes_aviso ON inmet_avisos_versoes(aviso_id, observado_em DESC);
CREATE INDEX IF NOT EXISTS idx_inmet_versoes_coleta ON inmet_avisos_versoes(coleta_id);
CREATE INDEX IF NOT EXISTS idx_inmet_versoes_poligono ON inmet_avisos_versoes USING GIST(poligono);

CREATE TABLE IF NOT EXISTS inmet_avisos_municipios (
    versao_id BIGINT NOT NULL REFERENCES inmet_avisos_versoes(id) ON DELETE RESTRICT,
    codigo_ibge VARCHAR(7) NOT NULL REFERENCES municipios(codigo_ibge) ON DELETE RESTRICT,
    via_geocodigo BOOLEAN NOT NULL DEFAULT FALSE,
    via_intersecao_espacial BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (versao_id, codigo_ibge),
    CHECK (via_geocodigo OR via_intersecao_espacial)
);

CREATE INDEX IF NOT EXISTS idx_inmet_avisos_municipios_ibge
    ON inmet_avisos_municipios(codigo_ibge, versao_id);

DROP VIEW IF EXISTS vw_municipios_avisos_inmet;
CREATE VIEW vw_municipios_avisos_inmet AS
SELECT
    m.codigo_ibge, m.nome AS municipio_nome, m.uf,
    a.id AS aviso_id, a.codigo AS aviso_codigo, a.descricao, a.severidade,
    a.aviso_cor, a.inicio, a.fim,
    (a.situacao_origem = 'cancelado') AS encerrado,
    CASE
        WHEN a.situacao_origem = 'cancelado' THEN 'cancelado'
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

COMMENT ON TABLE inmet_coletas IS 'Auditoria imutavel de cada tentativa de sincronizacao INMET.';
COMMENT ON TABLE inmet_avisos_versoes IS 'Snapshots distintos dos atributos de cada aviso; nunca atualizados.';
COMMENT ON TABLE inmet_avisos_municipios IS 'Vinculos territoriais congelados por versao do aviso.';
