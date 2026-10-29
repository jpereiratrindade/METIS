-- MÉTIS — Migração 004: Motor de Episódios Investigativos e Catálogo Climático
-- Banco: PostgreSQL 17 + PostGIS 3.5
-- Diretriz: METIS-DIR-EVID-001 (Monitoramento de Perturbações e Investigação da Resiliência)

-- 1. Catálogo Metodológico Oficial do AdaptaBrasil MCTI
CREATE TABLE IF NOT EXISTS catalogo_indicadores_adaptabrasil (
    indicador_id INTEGER PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    titulo VARCHAR(250),
    descricao_simples TEXT,
    anos_disponiveis INTEGER[] DEFAULT '{}',
    cenarios_json JSONB DEFAULT '[]'::jsonb,
    legenda_json JSONB DEFAULT '{}'::jsonb,
    direcao_interpretacao VARCHAR(50) DEFAULT 'pessimista',
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabela de Auditoria e Status Operacional dos Conectores
CREATE TABLE IF NOT EXISTS status_conectores (
    fonte VARCHAR(50) PRIMARY KEY,
    ultima_tentativa TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ultima_coleta_sucesso TIMESTAMPTZ,
    status VARCHAR(30) NOT NULL DEFAULT 'nao_executado',
    registros_processados INTEGER DEFAULT 0,
    mensagem TEXT
);

-- 3. Atualizar View de Municípios e Avisos INMET com Ciclo de Vida Temporal Estrito
DROP VIEW IF EXISTS vw_municipios_avisos_inmet;
CREATE VIEW vw_municipios_avisos_inmet AS
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
    CASE 
        WHEN a.encerrado = TRUE THEN 'cancelado'
        WHEN CURRENT_TIMESTAMP < a.inicio THEN 'futuro'
        WHEN CURRENT_TIMESTAMP BETWEEN a.inicio AND a.fim THEN 'vigente'
        ELSE 'expirado'
    END AS estado_vigencia,
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

-- 4. Tabela de Episódios de Investigação Científica (METIS-DIR-EVID-001)
CREATE TABLE IF NOT EXISTS episodios_investigacao (
    id VARCHAR(100) PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL REFERENCES municipios(codigo_ibge) ON DELETE RESTRICT,
    aviso_id BIGINT REFERENCES avisos_meteorologicos_inmet(id) ON DELETE RESTRICT,
    aviso_codigo VARCHAR(120) NOT NULL,
    tipo_ameaca VARCHAR(150) NOT NULL,
    severidade VARCHAR(50) NOT NULL,
    janela_inicio TIMESTAMPTZ NOT NULL,
    janela_fim TIMESTAMPTZ NOT NULL,
    estado_episodio VARCHAR(50) NOT NULL DEFAULT 'ameaca_anunciada'
        CHECK (estado_episodio IN ('ameaca_anunciada', 'em_verificacao', 'impactos_respostas', 'avaliacao_concluida')),
    condicoes_antecedentes JSONB NOT NULL DEFAULT '{}'::jsonb,
    estado_metis_congelado JSONB NOT NULL DEFAULT '{}'::jsonb,
    desfecho_cientifico VARCHAR(50) NOT NULL DEFAULT 'em_aberto'
        CHECK (desfecho_cientifico IN ('em_aberto', 'corroborado', 'contraditado', 'inconclusivo', 'reconfiguracao_documentada')),
    evidencias_impacto JSONB NOT NULL DEFAULT '[]'::jsonb,
    notas_cientificas TEXT,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_episodio_muni_aviso UNIQUE (codigo_ibge, aviso_codigo)
);

CREATE INDEX IF NOT EXISTS idx_episodio_ibge ON episodios_investigacao(codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_episodio_estado ON episodios_investigacao(estado_episodio);
CREATE INDEX IF NOT EXISTS idx_episodio_desfecho ON episodios_investigacao(desfecho_cientifico);
