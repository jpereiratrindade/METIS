-- MÉTIS — Migração 003: Evidências Climáticas e Perturbações Agroterritoriais
-- Banco: PostgreSQL 17 + PostGIS 3.5
-- Finalidade: Integrar AdaptaBrasil (MCTI) e Avisos Meteorológicos (INMET) como camadas epistêmicas de validação

-- 1. Tabela de Indicadores e Riscos Climáticos (AdaptaBrasil MCTI)
CREATE TABLE IF NOT EXISTS evidencias_adaptabrasil (
    id BIGSERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL REFERENCES municipios(codigo_ibge) ON DELETE RESTRICT,
    indicador_id INTEGER NOT NULL,
    nome_indicador VARCHAR(200) NOT NULL,
    ano_referencia INTEGER NOT NULL,
    cenario VARCHAR(50) NOT NULL DEFAULT 'baseline',
    pessimist INTEGER DEFAULT 0,
    valor NUMERIC(8, 4),
    classe_risco VARCHAR(50),
    cor_hex VARCHAR(10),
    sha256_origem VARCHAR(64) NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_adaptabrasil_registro UNIQUE (codigo_ibge, indicador_id, ano_referencia, cenario)
);

CREATE INDEX IF NOT EXISTS idx_adaptabrasil_ibge ON evidencias_adaptabrasil(codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_adaptabrasil_indicador ON evidencias_adaptabrasil(indicador_id, ano_referencia);
CREATE INDEX IF NOT EXISTS idx_adaptabrasil_cenario ON evidencias_adaptabrasil(cenario);

-- 2. Tabela de Avisos Meteorológicos Operacionais e Históricos (INMET)
CREATE TABLE IF NOT EXISTS avisos_meteorologicos_inmet (
    id BIGSERIAL PRIMARY KEY,
    id_aviso_inmet INTEGER NOT NULL,
    codigo VARCHAR(120) NOT NULL UNIQUE,
    descricao VARCHAR(150) NOT NULL,
    severidade VARCHAR(50) NOT NULL,
    aviso_cor VARCHAR(10),
    inicio TIMESTAMPTZ NOT NULL,
    fim TIMESTAMPTZ NOT NULL,
    poligono geometry(Geometry, 4326),
    geocodes TEXT,
    municipios_texto TEXT,
    riscos TEXT[] DEFAULT '{}',
    instrucoes TEXT[] DEFAULT '{}',
    encerrado BOOLEAN DEFAULT FALSE,
    sha256_origem VARCHAR(64) NOT NULL,
    consultado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inmet_codigo ON avisos_meteorologicos_inmet(codigo);
CREATE INDEX IF NOT EXISTS idx_inmet_vigencia ON avisos_meteorologicos_inmet(inicio, fim);
CREATE INDEX IF NOT EXISTS idx_inmet_severidade ON avisos_meteorologicos_inmet(severidade);
CREATE INDEX IF NOT EXISTS idx_inmet_poligono ON avisos_meteorologicos_inmet USING GIST(poligono);

-- 3. View PostGIS de Interseção Espacial e Relacional entre Municípios e Avisos INMET
CREATE OR REPLACE VIEW vw_municipios_avisos_inmet AS
SELECT 
    m.codigo_ibge,
    m.nome AS municipio_nome,
    m.uf,
    a.id AS aviso_id,
    a.codigo AS aviso_codigo,
    a.descricao,
    a.severidade,
    a.aviso_cor,
    a.inicio,
    a.fim,
    a.encerrado,
    a.riscos,
    a.instrucoes,
    (m.codigo_ibge = ANY(string_to_array(a.geocodes, ','))) AS afetado_por_geocodigo,
    CASE 
        WHEN a.poligono IS NOT NULL AND m.geometria IS NOT NULL 
        THEN ST_Intersects(m.geometria, a.poligono)
        ELSE FALSE 
    END AS afetado_por_intersecao_espacial
FROM municipios m
JOIN avisos_meteorologicos_inmet a 
  ON (m.codigo_ibge = ANY(string_to_array(a.geocodes, ',')) 
      OR (a.poligono IS NOT NULL AND m.geometria IS NOT NULL AND ST_Intersects(m.geometria, a.poligono)));
