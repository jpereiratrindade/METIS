-- ==============================================================================
-- MÉTIS — Migração 002: Imutabilidade Científica e Rigor Censitário
-- ==============================================================================
-- Esta migração resolve duas lacunas críticas apontadas na revisão independente:
-- 1. Diferenciação metodológica estrita entre 'ausência de observação' (NULL)
--    e 'zero observado' (0) nas contagens censitárias do IBGE.
-- 2. Garantia de imutabilidade criptográfica/relacional para execuções homologadas
--    e séries históricas de referência (bloqueio de UPDATE/DELETE via triggers).
-- ==============================================================================

-- 1. Permitir NULL nas contagens de estabelecimentos quando a observação for incompleta
ALTER TABLE observacoes_censitarias 
    ALTER COLUMN estabelecimentos_total DROP NOT NULL,
    ALTER COLUMN estabelecimentos_orientacao_tecnica DROP NOT NULL,
    ALTER COLUMN estabelecimentos_associados DROP NOT NULL;

-- 2. Adicionar controle de imutabilidade na tabela de execuções experimentais
ALTER TABLE execucoes_experimentais 
    ADD COLUMN IF NOT EXISTS imutavel BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS homologado_em TIMESTAMPTZ;

-- 3. Função e Trigger para blindar 'execucoes_experimentais' imutáveis
CREATE OR REPLACE FUNCTION fn_bloquear_mutacao_execucao_imutavel()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Se a execução já era imutável, rejeita qualquer alteração de parâmetros, modelo ou hashes
        IF OLD.imutavel = TRUE THEN
            -- Permite apenas a transição de não-imutável para imutável (fechamento de homologação)
            IF NEW.imutavel = TRUE AND OLD.imutavel = TRUE THEN
                RAISE EXCEPTION 'VIOLAÇÃO DE IMUTABILIDADE CIENTÍFICA (MÉTIS): A execução % está homologada como imutável e não admite alteração de parâmetros ou resultados.', OLD.id;
            END IF;
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        IF OLD.imutavel = TRUE THEN
            RAISE EXCEPTION 'VIOLAÇÃO DE IMUTABILIDADE CIENTÍFICA (MÉTIS): A execução % está homologada como imutável e não pode ser excluída do histórico científico.', OLD.id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_proteger_execucao_imutavel ON execucoes_experimentais;
CREATE TRIGGER trg_proteger_execucao_imutavel
BEFORE UPDATE OR DELETE ON execucoes_experimentais
FOR EACH ROW
EXECUTE FUNCTION fn_bloquear_mutacao_execucao_imutavel();

-- 4. Função e Trigger para blindar 'resultados_experimentais' associados a execuções imutáveis
CREATE OR REPLACE FUNCTION fn_bloquear_mutacao_resultado_imutavel()
RETURNS TRIGGER AS $$
DECLARE
    v_imutavel BOOLEAN;
BEGIN
    SELECT imutavel INTO v_imutavel FROM execucoes_experimentais WHERE id = OLD.execucao_id;
    IF v_imutavel = TRUE THEN
        RAISE EXCEPTION 'VIOLAÇÃO DE IMUTABILIDADE CIENTÍFICA (MÉTIS): O resultado do município % na execução % pertence a uma série imutável e não pode ser sobrescrito ou apagado.', OLD.codigo_ibge, OLD.execucao_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_proteger_resultado_imutavel ON resultados_experimentais;
CREATE TRIGGER trg_proteger_resultado_imutavel
BEFORE UPDATE OR DELETE ON resultados_experimentais
FOR EACH ROW
EXECUTE FUNCTION fn_bloquear_mutacao_resultado_imutavel();

-- 5. Atualizar a View vw_resultados_completos para incluir 'imutavel'
DROP VIEW IF EXISTS vw_resultados_completos;
CREATE VIEW vw_resultados_completos AS
SELECT 
    r.id AS resultado_id,
    r.execucao_id,
    e.imutavel AS execucao_imutavel,
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
