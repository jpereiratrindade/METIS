-- ==============================================================================
-- MÉTIS — Migração 007: Propostas Candidatas MCP e Idempotência (NOESE/CONTINUUM)
-- ==============================================================================
-- Preserva separação estrita entre registros canônicos/imutáveis do laboratório
-- e contribuições candidatas enviadas por clientes MCP externos (ex: ChatGPT).
-- ==============================================================================

CREATE TABLE IF NOT EXISTS propostas_investigacao_mcp (
    id VARCHAR(64) PRIMARY KEY,
    request_id UUID NOT NULL UNIQUE,
    assinatura_sha256 VARCHAR(64) NOT NULL,
    codigo_ibge VARCHAR(7) NOT NULL REFERENCES municipios(codigo_ibge) ON DELETE RESTRICT,
    episodio_id VARCHAR(100) REFERENCES episodios_investigacao(id) ON DELETE RESTRICT,
    tipo VARCHAR(40) NOT NULL
        CHECK (tipo IN ('nota_candidata', 'hipotese_parametro', 'observacao_impacto')),
    modelo_id VARCHAR(50),
    parametros JSONB NOT NULL DEFAULT '{}'::jsonb,
    texto TEXT NOT NULL,
    limitacoes TEXT NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pendente_revisao'
        CHECK (status IN ('pendente_revisao', 'incorporada', 'descartada')),
    origem_tipo VARCHAR(30) NOT NULL DEFAULT 'mcp_client',
    origem_cliente VARCHAR(120) NOT NULL,
    resultado_json JSONB NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_propostas_mcp_ibge ON propostas_investigacao_mcp(codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_propostas_mcp_episodio ON propostas_investigacao_mcp(episodio_id);
CREATE INDEX IF NOT EXISTS idx_propostas_mcp_status ON propostas_investigacao_mcp(status);
