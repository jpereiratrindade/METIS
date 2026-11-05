# MÉTIS — Relatório de Homologação da Persistência Científica Versionada
**Documento:** METIS-REL-PERSIST-001  
**Versão:** 2.0.0  
**Data:** 05/11/2026 (Aditivo de Homologação das Migrações 003 a 006)  
**Natureza:** Relatório formal de homologação técnica e científica da persistência PostgreSQL 17 / PostGIS 3.5, evidências climáticas, motor de episódios e auditoria temporal  
**Status:** HOMOLOGADO E BLINDADO  

---

## 1. Sumário Executivo

Este documento homologa a implantação e a evolução contínua da **camada de persistência científica do MÉTIS**, estruturada sobre **PostgreSQL 17 com extensão geoespacial PostGIS 3.5**, contemplando:
1. **Isolamento de Segurança:** O servidor web expõe estritamente o diretório `web/` com bind padrão em `127.0.0.1`, isolando a raiz do repositório, `.env`, `.git/` e códigos de infraestrutura.
2. **Imutabilidade Científica:** O banco bloqueia ativamente, via triggers PL/pgSQL nativos, qualquer alteração (`UPDATE`) ou exclusão (`DELETE`) em execuções e resultados homologados.
3. **Rigor Censitário:** Diferenciação estrita entre ausência de observação (`NULL`) e zero observado (`0`), com colunas anuláveis em `observacoes_censitarias`.
4. **Camada de Confrontação Empírica (Migrações 003 e 004):** Ingestão contínua do catálogo AdaptaBrasil MCTI (558 indicadores) e avisos meteorológicos do INMET com cruzamento espacial topológico (`ST_Intersects`).
5. **Motor de Episódios Investigativos:** Registro imutável de episódios de teste de estresse perante perturbações, congelando o baseline $R(t_0)$ sem contaminação aditiva da fórmula matemática territorial.
6. **Auditoria Temporal e Histórico Append-Only (Migrações 005 e 006):** Versionamento estrito de avisos em `inmet_avisos_versoes`, trilha de coletas com hashes SHA-256 em `inmet_coletas`, associação territorial por versão em `inmet_avisos_municipios` e exclusão mútua por *advisory locks* (`pg_advisory_lock(942103)`).
7. **Reprodutibilidade Ponta a Ponta:** Suíte de 14 testes automatizados de persistência (`tests/test_persistencia.py`) e 4 testes temporais (`tests/test_inmet_temporal.py`) aprovados com 100% de sucesso.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              ARQUITETURA DE PERSISTÊNCIA                               │
│                                                                                        │
│   [Fontes Censitárias IBGE]              [Malha GeoJSON IBGE]     [AdaptaBrasil MCTI]  │
│   (Censos 2006 e 2017)                   (497 Polígonos RS)       (558 Indicadores)    │
│            │                                     │                         │           │
│            ▼                                     ▼                         ▼           │
│   [fontes_dados] ── SHA-256 ──────────► [municipios] ◄────── [catalogo_indicadores]   │
│            │                             (SRID 4326)                       │           │
│            ▼                                     ▲                         ▼           │
│   [observacoes_censitarias]                      │            [evidencias_adaptabrasil]│
│   (NULL estrito para incompletos)                │                         │           │
│            │                                     │                         │           │
│            ▼                                     │                         │           │
│   [modelos] (Catálogo Formal)                    │                         │           │
│   (EPS-REF-001 a EPS-EXP-004)                    │                         │           │
│            │                                     │                         │           │
│            ▼                                     │                         │           │
│   [execucoes_experimentais]                      │                         │           │
│   (Trigger: imutavel = TRUE)                     │                         │           │
│            │                                     │                         │           │
│            ▼                                     │                         │           │
│   [resultados_experimentais] ────────────────────┘                         │           │
│   (Bloqueio de UPDATE/DELETE)                    │                         │           │
│            │                                     │                         │           │
│            ▼                                     ▼                         │           │
│   [vw_resultados_completos] ◄── [vw_municipios_avisos_inmet]               │           │
│            │                    (ST_Intersects em tempo real)              │           │
│            │                                     ▲                         │           │
│            │                           [inmet_avisos_municipios]           │           │
│            │                                     ▲                         │           │
│            │                           [inmet_avisos_versoes]              │           │
│            │                                     ▲                         │           │
│            │                             [inmet_coletas]                   │           │
│            │                                     │                         │           │
│            ▼                                     ▼                         ▼           │
│   ══════════════════════════════════════════════════════════════════════════════════   │
│               [MOTOR DE EPISÓDIOS INVESTIGATIVOS: episodios_investigacao]              │
│               - Snapshot Imutável de R(t₀), E, P, S                                    │
│               - Condições Antecedentes (AdaptaBrasil)                                  │
│               - Ciclo de Vida: Ameaça ➔ Verificação ➔ Impactos ➔ Conclusão             │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Verificação dos Critérios de Aceite Homologados

| # | Critério de Aceite | Migração | Resultado | Evidência Técnica |
| :---: | :--- | :---: | :---: | :--- |
| **CA-01** | **497 municípios sem duplicações** | 001 | **APROVADO** | Exatamente 497 registros na tabela `municipios`. Todos com código IBGE de 7 dígitos iniciando por `43`, com geometrias `MultiPolygon` válidas no PostGIS (`ST_IsValid` = true, SRID 4326). |
| **CA-02** | **Identidade estrita de dados de entrada (2017 e 2006)** | 001 | **APROVADO** | As observações em `observacoes_censitarias` coincidem valor por valor com os CSVs homologados de 2017 e 2006. Ocorrências incompletas preservam `NULL` estrito, sem conversão indevida para zero. |
| **CA-03** | **Identidade estrita de resultados experimentais** | 001 | **APROVADO** | Os 497 resultados de `EPS-REF-001/0.1.0` coincidem rigorosamente com o histórico. Resultados vigentes de 2017 e 2006 conferem 100% com `results/RS_497_RESULTADOS.csv` e `results/RS_497_RESULTADOS_2006.csv`. |
| **CA-04** | **Rastreabilidade epistêmica e proveniência** | 001 | **APROVADO** | Cada registro em `resultados_experimentais` está associado à execução (`execucoes_experimentais`), ao modelo formal e versão (`modelos`), aos parâmetros e à fonte censitária (`fontes_dados`). |
| **CA-05** | **Integridade criptográfica auditável** | 001 | **APROVADO** | Todos os hashes SHA-256 gravados nas tabelas conferem com os hashes dos arquivos físicos em disco. |
| **CA-06** | **Reprodutibilidade em instalação limpa** | 001 | **APROVADO** | Procedimento automatizado testado em schema isolado (`metis_teste_limpo`), aplicando todas as migrações e executando a rotina real de importação completa sem intervenção manual. |
| **CA-07** | **Extensão multitemporal (Censo 2006)** | 001 | **APROVADO** | Ingestão e cálculo oficial para o Censo Agropecuário 2006 (497 municípios: 493 válidos e 4 incompletos territoriais), associados com integridade numérica estrita e rastreabilidade temporal. |
| **CA-08** | **Imutabilidade científica ativa no PostgreSQL** | 002 | **APROVADO** | Triggers PL/pgSQL interceptam e abortam com exceção qualquer tentativa de `UPDATE` ou `DELETE` em execuções e resultados homologados. |
| **CA-09** | **Isolamento de segurança do servidor web** | 001 | **APROVADO** | Orquestrador `./run.sh` serve exclusivamente `--directory web` com bind padrão `127.0.0.1`. Raiz do projeto (`.git`, `.env`, códigos internos) inacessível externamente. |
| **CA-10** | **Catálogo e Evidências AdaptaBrasil (MCTI)** | 003 | **APROVADO** | Cobertura integral dos 497 municípios do RS com 2.982 registros em `evidencias_adaptabrasil` e 558 indicadores catalogados em `catalogo_indicadores_adaptabrasil`. |
| **CA-11** | **Interseção Espacial de Avisos INMET** | 003 | **APROVADO** | View espacial `vw_municipios_avisos_inmet` executa `ST_Intersects` em tempo real entre polígonos meteorológicos e malha municipal, classificando estados de vigência (`vigente`, `futuro`, `expirado`, `cancelado`). |
| **CA-12** | **Motor de Episódios Investigativos** | 004 | **APROVADO** | Tabela `episodios_investigacao` congela o baseline $R(t_0)$, $E$, $P$, $S$ em JSON imutável, registra condições antecedentes e preserva o isolamento epistêmico da equação de resiliência. |
| **CA-13** | **Auditoria Temporal e Versionamento Append-Only** | 005 | **APROVADO** | Tabelas `inmet_coletas`, `inmet_avisos_versoes` e `inmet_avisos_municipios` registram todo ciclo temporal, fingerprints SHA-256 de atributos e amarração geográfica imutável por versão. |
| **CA-14** | **Exclusão Mútua e Consolidação Operacional** | 006 | **APROVADO** | Bloqueio distribuído via `pg_advisory_lock(942103)` impede sincronizações concorrentes entre CLI, API e agendador daemon; cancelamento do INMET não conclui investigações em aberto. |

---

## 3. Hashes Criptográficos das Evidências Físicas

As fontes de dados e os resultados homologados possuem as seguintes somas de verificação SHA-256 auditáveis:

```text
b7b10c2094241bc7352995c3252bd9b72a81b0acc1a88cccbd1d67b465fff6b6  data/gerados/municipios_rs_2017_homologado.csv
e030b4bcba83cba7b9de5696ffb2b60a351696dc8133db28399d11fffaf9d39f  data/gerados/municipios_rs_2006_homologado.csv
423e513822204a3666d933758369ec264663a8a3a9fbff4a19dc8782f7571bef  data/gerados/municipios_rs_2022.geojson
8a69741a3a6178adbef58bf1c8cc99fde4ba21c0e4446d8bf50396f614c15443  results/historico/RS_497_RESULTADOS_v0.1.0_percentil.csv
1d42d48caa0501fa7c68b934f5898bc2f89c9e066aaada6761a8727341067568  results/historico/RS_497_RESULTADOS_v0.1.0_percentil.manifest.json
5f8c9d90bcb661dad6ef6bad5c20808d64d1a987cedf27f9e38493f22784f0bc  results/RS_497_RESULTADOS.csv
9baa9b4e24a64c57311f504367c6dacc7477765e5ccab08c3176d1d6a85f3cbb  results/RS_497_RESULTADOS.manifest.json
7f1d6ba64e60cc60be275280db51ea5ade180a8557bd2a0c19bb3331f2a35e68  results/RS_497_RESULTADOS_2006.csv
ec044520592e094cd7ca26447e68cef10e2267a74c09b714b5ffdfdee195199e  results/RS_497_RESULTADOS_2006.manifest.json
```

---

## 4. Dicionário das Tabelas de Evidências e Auditoria (Migrações 003 a 006)

### 4.1. `catalogo_indicadores_adaptabrasil` (Migração 003)
Catálogo oficial dos 558 indicadores hierárquicos do Ministério da Ciência, Tecnologia e Inovações (MCTI).
- `codigo` (INTEGER, PK): Identificador do indicador (ex: `5001`).
- `nome`: Nome oficial no AdaptaBrasil.
- `descricao`, `unidade_medida`, `formula_calculo`: Metadados científicos originais.

### 4.2. `evidencias_adaptabrasil` (Migração 003)
Armazena as observações municipais de risco e vulnerabilidade para os 497 municípios.
- Chave composta `(codigo_ibge, indicador_id, ano_cenario)`.
- Valores: Baseline 2017, Projeções 2030 e 2050 sob o cenário IPCC RCP4.5.

### 4.3. `avisos_meteorologicos_inmet` e `vw_municipios_avisos_inmet` (Migração 003 e 005)
Projeta o estado atual consolidado dos alertas meteorológicos severos do INMET.
- `geometria`: Polígono com SRID 4326.
- `severidade`: `Aviso`, `Perigo Potencial`, `Perigo`, `Grande Perigo`.
- `vw_municipios_avisos_inmet`: View espacial dinâmica com cruzamento `ST_Intersects(m.geometria, a.geometria)` e classificação de vigência.

### 4.4. `episodios_investigacao` (Migração 004)
Núcleo do motor investigativo científico (METIS-DIR-EVID-001).
- `id` (VARCHAR(64), PK): Ex: `EP-4302105-20261029-001`.
- `codigo_ibge` e `aviso_id`: Vínculo espacial e causal da perturbação.
- `estado_episodio`: Ciclo de vida (`ameaca_anunciada`, `em_verificacao`, `impactos_respostas`, `avaliacao_concluida`).
- `estado_metis_congelado` (JSONB): Baseline $R(t_0)$, $E$, $P$, $S$ no momento do choque.
- `condicoes_antecedentes` (JSONB): Vulnerabilidade AdaptaBrasil prévia.
- `desfecho_cientifico`: Parecer de validação ou refutação da hipótese territorial.

### 4.5. `inmet_coletas`, `inmet_avisos_versoes` e `inmet_avisos_municipios` (Migração 005)
Arquitetura append-only para auditoria e reprodução histórica.
- `inmet_coletas`: Registra cada tentativa de sincronização (inclusive falhas de rede), payload bruto, SHA-256 e status.
- `inmet_avisos_versoes`: Versão dos avisos a cada mutação de atributos, fingerprint SHA-256 e janela temporal.
- `inmet_avisos_municipios`: Amarração territorial estática dos municípios afetados em cada versão individual do aviso.

---

## 5. Procedimento de Validação e Testes Automatizados

A homologação é verificada continuamente pelo script orquestrador:

```bash
# Execução da suíte integral (CTest C++26 + 14 Testes PostGIS + 4 Testes Temporais):
./run.sh test
```

---

## 6. Parecer Conclusivo da Homologação

A camada de persistência científica do MÉTIS atinge conformidade plena:
1. **Integridade de Dados:** O núcleo histórico, o catálogo multimodelo e a malha censitária permanecem 100% imutáveis e protegidos contra mutações acidentais.
2. **Robustez Temporal:** Toda evidência climática externa (AdaptaBrasil e INMET) é tratada com rastreabilidade auditável por hashes SHA-256 e advisory locks.
3. **Isolamento Epistêmico:** Alertas e perturbações externas não contaminam a formulação matemática de $R$, operando exclusivamente como confrontadores empíricos através do Motor de Episódios Investigativos.

> **Homologado por:** Equipe MÉTIS / Ecossistema SisTer  
> **Status:** Concluído, auditado e blindado.
