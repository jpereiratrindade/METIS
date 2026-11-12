-- METIS: Migração 008 — Alertas Agroclimáticos SIMAGRO-RS (SEAPI/DDPA)
-- Finalidade: Integrar índices diários de alerta agrometeorológico (3d e 7d) para os 497 municípios do RS

CREATE TABLE IF NOT EXISTS simagro_coletas (
    id BIGSERIAL PRIMARY KEY,
    iniciada_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finalizada_em TIMESTAMPTZ,
    origem_url TEXT NOT NULL,
    janela VARCHAR(10) NOT NULL CHECK (janela IN ('3d', '7d')),
    data_referencia DATE NOT NULL,
    acionamento VARCHAR(20) NOT NULL DEFAULT 'manual'
        CHECK (acionamento IN ('manual', 'agendado', 'api', 'teste')),
    status VARCHAR(30) NOT NULL DEFAULT 'iniciada'
        CHECK (status IN ('iniciada', 'sucesso', 'falha_rede', 'falha_validacao', 'falha_persistencia')),
    http_status INTEGER,
    sha256_payload VARCHAR(64),
    arquivo_payload TEXT,
    registros_recebidos INTEGER NOT NULL DEFAULT 0,
    registros_validos INTEGER NOT NULL DEFAULT 0,
    mensagem TEXT
);

CREATE INDEX IF NOT EXISTS idx_simagro_coletas_iniciada ON simagro_coletas(iniciada_em DESC);
CREATE INDEX IF NOT EXISTS idx_simagro_coletas_janela_data ON simagro_coletas(janela, data_referencia DESC);

CREATE TABLE IF NOT EXISTS simagro_municipios_mapa (
    id_ponto INTEGER PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL UNIQUE REFERENCES municipios(codigo_ibge) ON DELETE RESTRICT,
    nome_simagro VARCHAR(150),
    region_id INTEGER,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidencias_simagro_alertas (
    id BIGSERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL REFERENCES municipios(codigo_ibge) ON DELETE RESTRICT,
    id_ponto INTEGER NOT NULL,
    data_referencia DATE NOT NULL,
    janela VARCHAR(10) NOT NULL CHECK (janela IN ('3d', '7d')),
    prec SMALLINT NOT NULL DEFAULT 0 CHECK (prec BETWEEN 0 AND 3),
    estiagem SMALLINT NOT NULL DEFAULT 0 CHECK (estiagem BETWEEN 0 AND 3),
    estiagem_agricola SMALLINT NOT NULL DEFAULT 0 CHECK (estiagem_agricola BETWEEN 0 AND 3),
    geada SMALLINT NOT NULL DEFAULT 0 CHECK (geada BETWEEN 0 AND 3),
    t_acima SMALLINT NOT NULL DEFAULT 0 CHECK (t_acima BETWEEN 0 AND 3),
    t_abaixo SMALLINT NOT NULL DEFAULT 0 CHECK (t_abaixo BETWEEN 0 AND 3),
    itu SMALLINT NOT NULL DEFAULT 0 CHECK (itu BETWEEN 0 AND 3),
    ci_ovino SMALLINT NOT NULL DEFAULT 0 CHECK (ci_ovino BETWEEN 0 AND 3),
    nivel_maximo SMALLINT GENERATED ALWAYS AS (
        GREATEST(prec, estiagem, estiagem_agricola, geada, t_acima, t_abaixo, itu, ci_ovino)
    ) STORED,
    sha256_origem VARCHAR(64) NOT NULL,
    coleta_id BIGINT REFERENCES simagro_coletas(id) ON DELETE RESTRICT,
    consultado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_simagro_muni_data_janela UNIQUE (codigo_ibge, data_referencia, janela)
);

CREATE INDEX IF NOT EXISTS idx_simagro_alertas_data_janela
    ON evidencias_simagro_alertas(data_referencia DESC, janela);
CREATE INDEX IF NOT EXISTS idx_simagro_alertas_ibge_data
    ON evidencias_simagro_alertas(codigo_ibge, data_referencia DESC);
CREATE INDEX IF NOT EXISTS idx_simagro_alertas_nivel
    ON evidencias_simagro_alertas(nivel_maximo DESC, data_referencia DESC);

CREATE OR REPLACE VIEW vw_simagro_alertas_recentes AS
WITH ultimas_datas AS (
    SELECT janela, MAX(data_referencia) AS data_referencia
    FROM evidencias_simagro_alertas
    GROUP BY janela
)
SELECT
    a.codigo_ibge,
    m.nome AS municipio_nome,
    m.uf,
    a.id_ponto,
    a.data_referencia,
    a.janela,
    a.prec,
    a.estiagem,
    a.estiagem_agricola,
    a.geada,
    a.t_acima,
    a.t_abaixo,
    a.itu,
    a.ci_ovino,
    a.nivel_maximo,
    a.consultado_em
FROM evidencias_simagro_alertas a
JOIN ultimas_datas u
  ON u.janela = a.janela AND u.data_referencia = a.data_referencia
JOIN municipios m
  ON m.codigo_ibge = a.codigo_ibge;
