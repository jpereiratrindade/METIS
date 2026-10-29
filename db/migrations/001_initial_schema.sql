-- MÉTIS — Migração 001: Esquema Inicial de Persistência Científica Versionada
-- Banco: PostgreSQL + PostGIS
-- Finalidade: Municípios, Fontes, Observações Censitárias, Modelos, Execuções e Resultados Experimentais

-- 1. Habilitar extensão espacial PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Tabela de controle e auditoria de migrações versionadas
CREATE TABLE IF NOT EXISTS registro_migracoes (
    versao VARCHAR(50) PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    aplicado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabela de catálogo de fontes de dados e proveniência censitária
CREATE TABLE IF NOT EXISTS fontes_dados (
    id VARCHAR(50) PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    instituicao VARCHAR(100) NOT NULL DEFAULT 'IBGE',
    ano_referencia INTEGER NOT NULL,
    tabelas_origem TEXT[] NOT NULL DEFAULT '{}',
    arquivo_origem VARCHAR(255) NOT NULL,
    sha256_origem VARCHAR(64) NOT NULL,
    descricao TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. Tabela de municípios e malha territorial oficial (PostGIS)
CREATE TABLE IF NOT EXISTS municipios (
    codigo_ibge VARCHAR(7) PRIMARY KEY,
    nome VARCHAR(120) NOT NULL,
    uf VARCHAR(2) NOT NULL DEFAULT 'RS',
    area_km2 NUMERIC(12, 4),
    geometria geometry(MultiPolygon, 4326),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_municipios_nome ON municipios(nome);
CREATE INDEX IF NOT EXISTS idx_municipios_uf ON municipios(uf);
CREATE INDEX IF NOT EXISTS idx_municipios_geom ON municipios USING GIST(geometria);

-- 5. Tabela de observações censitárias brutas (IBGE Censo Agropecuário 2017)
CREATE TABLE IF NOT EXISTS observacoes_censitarias (
    id BIGSERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL REFERENCES municipios(codigo_ibge) ON DELETE RESTRICT,
    fonte_id VARCHAR(50) NOT NULL REFERENCES fontes_dados(id) ON DELETE RESTRICT,
    ano_referencia INTEGER NOT NULL,
    area_estabelecimentos_ha NUMERIC(14, 4),
    pastagem_natural_ha NUMERIC(14, 4),
    mata_natural_ha NUMERIC(14, 4),
    valor_producao_reais NUMERIC(16, 2),
    estabelecimentos_total INTEGER NOT NULL,
    estabelecimentos_orientacao_tecnica INTEGER NOT NULL,
    estabelecimentos_associados INTEGER NOT NULL,
    status_observacao VARCHAR(30) NOT NULL DEFAULT 'valido',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_observacao_municipio_fonte_ano UNIQUE (codigo_ibge, fonte_id, ano_referencia)
);

CREATE INDEX IF NOT EXISTS idx_obs_ibge ON observacoes_censitarias(codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_obs_fonte_ano ON observacoes_censitarias(fonte_id, ano_referencia);
CREATE INDEX IF NOT EXISTS idx_obs_status ON observacoes_censitarias(status_observacao);

-- 6. Tabela de catálogo formal de modelos matemáticos
CREATE TABLE IF NOT EXISTS modelos (
    id VARCHAR(50) NOT NULL,
    versao VARCHAR(20) NOT NULL,
    nome VARCHAR(150) NOT NULL,
    equacao_resiliencia VARCHAR(150) NOT NULL,
    equacao_ecologica VARCHAR(200) NOT NULL,
    equacao_produtiva VARCHAR(200) NOT NULL,
    equacao_social VARCHAR(200) NOT NULL,
    papel_epistemico VARCHAR(50) NOT NULL,
    descricao TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, versao)
);

-- 7. Tabela de execuções experimentais com proveniência e manifestos
CREATE TABLE IF NOT EXISTS execucoes_experimentais (
    id VARCHAR(64) PRIMARY KEY,
    modelo_id VARCHAR(50) NOT NULL,
    modelo_versao VARCHAR(20) NOT NULL,
    fonte_id VARCHAR(50) NOT NULL REFERENCES fontes_dados(id) ON DELETE RESTRICT,
    ano_referencia INTEGER NOT NULL,
    trajetoria VARCHAR(30) NOT NULL DEFAULT 'historica',
    status_execucao VARCHAR(50) NOT NULL,
    parametros JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadados JSONB NOT NULL DEFAULT '{}'::jsonb,
    arquivo_saida VARCHAR(255) NOT NULL,
    sha256_saida VARCHAR(64) NOT NULL,
    arquivo_manifesto VARCHAR(255) NOT NULL,
    sha256_manifesto VARCHAR(64) NOT NULL,
    executado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_execucao_modelo FOREIGN KEY (modelo_id, modelo_versao) REFERENCES modelos(id, versao) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_exec_modelo ON execucoes_experimentais(modelo_id, modelo_versao);
CREATE INDEX IF NOT EXISTS idx_exec_fonte ON execucoes_experimentais(fonte_id, ano_referencia);
CREATE INDEX IF NOT EXISTS idx_exec_trajetoria ON execucoes_experimentais(trajetoria);

-- 8. Tabela de resultados experimentais por município e execução
CREATE TABLE IF NOT EXISTS resultados_experimentais (
    id BIGSERIAL PRIMARY KEY,
    execucao_id VARCHAR(64) NOT NULL REFERENCES execucoes_experimentais(id) ON DELETE CASCADE,
    codigo_ibge VARCHAR(7) NOT NULL REFERENCES municipios(codigo_ibge) ON DELETE RESTRICT,
    densidade_monetaria_ha DOUBLE PRECISION,
    ecologica_indice DOUBLE PRECISION,
    ecologica_multiplicador DOUBLE PRECISION,
    produtiva DOUBLE PRECISION,
    social DOUBLE PRECISION,
    resiliencia DOUBLE PRECISION,
    status VARCHAR(30) NOT NULL DEFAULT 'experimental',
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_resultado_execucao_municipio UNIQUE (execucao_id, codigo_ibge)
);

CREATE INDEX IF NOT EXISTS idx_res_execucao ON resultados_experimentais(execucao_id);
CREATE INDEX IF NOT EXISTS idx_res_ibge ON resultados_experimentais(codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_res_status ON resultados_experimentais(status);

-- 9. Visão analítica consolidada para consumo das futuras APIs e interfaces
CREATE OR REPLACE VIEW vw_resultados_completos AS
SELECT 
    r.id AS resultado_id,
    r.execucao_id,
    e.modelo_id,
    e.modelo_versao,
    e.ano_referencia,
    e.trajetoria,
    m.codigo_ibge,
    m.nome AS municipio,
    m.uf,
    m.area_km2,
    r.densidade_monetaria_ha,
    r.ecologica_indice,
    r.ecologica_multiplicador,
    r.produtiva,
    r.social,
    r.resiliencia,
    r.status,
    e.parametros AS parametros_execucao,
    e.metadados AS metadados_execucao,
    m.geometria
FROM resultados_experimentais r
JOIN execucoes_experimentais e ON e.id = r.execucao_id
JOIN municipios m ON m.codigo_ibge = r.codigo_ibge;
