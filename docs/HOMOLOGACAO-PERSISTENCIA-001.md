# MÉTIS — Relatório de Homologação da Persistência Científica Versionada
**Documento:** METIS-REL-PERSIST-001  
**Versão:** 1.1.0  
**Data:** 29/10/2026  
**Natureza:** Relatório formal de homologação técnica e científica da Prioridade Técnica 001 (revisão independente incorporada)  
**Status:** HOMOLOGADO E BLINDADO  

---

## 1. Sumário Executivo

Este documento homologa a implantação da **primeira camada de persistência científica do MÉTIS**, estruturada sobre **PostgreSQL 17 com extensão geoespacial PostGIS 3.5**, contemplando integralmente as correções apontadas na revisão independente de código e metodologia:
1. **Isolamento de Segurança:** O servidor web expõe estritamente o diretório `web/` com bind padrão em `127.0.0.1`, isolando a raiz do repositório, `.env`, `.git/` e códigos de infraestrutura.
2. **Imutabilidade Científica:** O banco bloqueia ativamente, via triggers PL/pgSQL nativos, qualquer alteração (`UPDATE`) ou exclusão (`DELETE`) em execuções e resultados homologados.
3. **Rigor Censitário:** Diferenciação estrita entre ausência de observação (`NULL`) e zero observado (`0`), com colunas anuláveis em `observacoes_censitarias`.
4. **Reprodutibilidade Ponta a Ponta:** Suíte de 11 testes automatizados sob modo estrito (`METIS_STRICT_TESTS=1`), incluindo a reconstrução e importação integral em schema limpo isolado.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ARQUITETURA DE PERSISTÊNCIA                     │
│                                                                        │
│   [Fontes Censitárias IBGE 2017/2006]    [Malha GeoJSON IBGE 2022]     │
│   (Tabelas SIDRA 6881, 6898, 1011, etc.) (497 Polígonos Municipais)    │
│                  │                                    │                │
│                  ▼                                    ▼                │
│        [fontes_dados]                           [municipios]           │
│        (Hashes SHA-256)                   (PostGIS SRID 4326 MultiPoly)│
│                  │                                    │                │
│                  ▼                                    ▼                │
│     [observacoes_censitarias] ◄───────────────────────┤                │
│     (NULL estrito para incompletos, sem zero forçado) │                │
│                                                       │                │
│     [modelos] (Catálogo Formal)                       │                │
│     (EPS-REF-001/0.1.0, 0.2.0, etc.)                  │                │
│                  │                                    │                │
│                  ▼                                    ▼                │
│     [execucoes_experimentais] ◄───────────────────────┤                │
│     (Trigger PL/pgSQL: imutavel = TRUE)               │                │
│                  │                                    │                │
│                  ▼                                    │                │
│     [resultados_experimentais] ───────────────────────┘                │
│     (Trigger PL/pgSQL: bloqueio de UPDATE/DELETE)                      │
│                  │                                                     │
│                  ▼                                                     │
│        [vw_resultados_completos] ──► Pronta para React / REST / MCP    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Verificação dos Critérios de Aceite

| # | Critério de Aceite | Resultado | Evidência Técnica |
| :---: | :--- | :---: | :--- |
| **CA-01** | **497 municípios sem duplicações** | **APROVADO** | Exatamente 497 registros na tabela `municipios`. Todos com código IBGE de 7 dígitos iniciando por `43`, pertencentes à UF `RS`, com geometrias `MultiPolygon` válidas no PostGIS (`ST_IsValid` = true). |
| **CA-02** | **Identidade estrita de dados de entrada** | **APROVADO** | As observações em `observacoes_censitarias` coincidem valor por valor com os CSVs homologados de 2017 e 2006. Ocorrências incompletas (ex: Cachoeirinha em 2017 e Pinto Bandeira em 2006) preservam `NULL` estrito, sem conversão indevida para zero. |
| **CA-03** | **Identidade estrita de resultados experimentais** | **APROVADO** | Os 497 resultados de `EPS-REF-001/0.1.0` no banco coincidem rigorosamente com `results/historico/RS_497_RESULTADOS_v0.1.0_percentil.csv` em todas as dimensões ($R, E, P, S$) e status. Os resultados vigentes de 2017 e 2006 conferem 100% com seus respectivos arquivos CSV. |
| **CA-04** | **Rastreabilidade epistêmica e proveniência** | **APROVADO** | Cada registro em `resultados_experimentais` está estritamente vinculado à sua execução (`execucoes_experimentais`), ao modelo formal e versão (`modelos`), aos parâmetros declarados e à fonte censitária (`fontes_dados`). |
| **CA-05** | **Integridade criptográfica auditável** | **APROVADO** | Todos os hashes SHA-256 gravados nas tabelas conferem com os hashes dos arquivos físicos em disco. |
| **CA-06** | **Reprodutibilidade em instalação limpa** | **APROVADO** | Procedimento automatizado testado em schema isolado (`metis_teste_limpo`), aplicando todas as migrações e executando a rotina real de importação completa sem intervenção manual. |
| **CA-07** | **Extensão multitemporal (Censo 2006)** | **APROVADO** | Ingestão e cálculo oficial para o Censo Agropecuário 2006 (497 municípios, 493 válidos e 4 incompletos / territoriais), associados com integridade numérica estrita e rastreabilidade temporal. |
| **CA-08** | **Imutabilidade científica ativa no PostgreSQL** | **APROVADO** | Migração `002_scientific_immutability.sql` implanta triggers PL/pgSQL que interceptam e abortam com exceção qualquer tentativa de `UPDATE` ou `DELETE` em execuções e resultados homologados. |
| **CA-09** | **Isolamento de segurança do servidor web** | **APROVADO** | Orquestrador `./run.sh` serve exclusivamente `--directory web` com bind padrão `127.0.0.1`. Raiz do projeto (`.git`, `.env`, códigos internos) inacessível externamente. |

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

## 4. Dicionário das Tabelas Criadas

### 4.1. `registro_migracoes`
Controla as migrações aplicadas no banco, prevenindo reaplicação inadvertida e auditando o hash de cada script SQL.
- `versao` (VARCHAR(50), PK): Prefixo da migração (ex: `001`).
- `nome` (VARCHAR(150)): Nome do arquivo (ex: `001_initial_schema.sql`).
- `sha256` (VARCHAR(64)): Hash do script no momento da aplicação.
- `aplicado_em` (TIMESTAMPTZ): Data e hora da aplicação.

### 4.2. `fontes_dados`
Registra a proveniência, instituição de origem e integridade das bases brutas.
- `id` (VARCHAR(50), PK): `IBGE_CENSO_AGRO_2017`, `IBGE_MALHA_2022`.
- `instituicao`: `IBGE`.
- `ano_referencia`: 2017 / 2022.
- `tabelas_origem`: Array com códigos de tabelas SIDRA.
- `arquivo_origem` e `sha256_origem`: Rastreabilidade do arquivo no repositório.

### 4.3. `municipios`
Entidade geográfica central com representação espacial PostGIS.
- `codigo_ibge` (VARCHAR(7), PK): Geocódigo oficial IBGE.
- `nome` (VARCHAR(120)): Nome do município.
- `uf` (VARCHAR(2)): `RS`.
- `area_km2` (NUMERIC(12, 4)): Área oficial.
- `geometria` (geometry(MultiPolygon, 4326)): Geometria vetorial com índice espacial GIST.

### 4.4. `observacoes_censitarias`
Observações estatísticas agropecuárias agregadas.
- Chave estrangeira para `municipios` e `fontes_dados`.
- Valores declarados: `area_estabelecimentos_ha`, `pastagem_natural_ha`, `mata_natural_ha`, `valor_producao_reais`, `estabelecimentos_total`, `estabelecimentos_orientacao_tecnica`, `estabelecimentos_associados`.
- `status_observacao`: `valido` (492) ou `dados_incompletos` (5).

### 4.5. `modelos`
Catálogo matemático formal de modelos concorrentes.
- Chave primária composta `(id, versao)`.
- Fórmulas explícitas: `equacao_resiliencia`, `equacao_ecologica`, `equacao_produtiva`, `equacao_social`.
- `papel_epistemico`: `referencia_historica`, `referencia_multimodelo`, `experimental_aditivo`, `experimental_interativo`, `experimental_autonomo`.

### 4.6. `execucoes_experimentais`
Registra cada execução computacional com seus parâmetros, manifestos e integridade de saída.
- `id` (VARCHAR(64), PK): Ex: `EXEC-HISTORICA-EPS-REF-001-v0.1.0-2017`.
- `parametros` (JSONB): Calibração de percentis estaduais ou parâmetros de escala ($k$, pesos, $\lambda$).
- `metadados` (JSONB): Conteúdo integral do manifesto de proveniência.
- Hashes do CSV de saída e do arquivo de manifesto.

### 4.7. `resultados_experimentais`
Pontuações calculadas para cada município sob uma execução experimental específica.
- `execucao_id` (FK para `execucoes_experimentais`, ON DELETE CASCADE).
- `codigo_ibge` (FK para `municipios`).
- Dimensões: `densidade_monetaria_ha`, `ecologica_indice` ($e$), `ecologica_multiplicador` ($E$), `produtiva` ($P$), `social` ($S$), `resiliencia` ($R$).
- `status`: `experimental`, `dados_incompletos`.
- Restrição de unicidade: `(execucao_id, codigo_ibge)`.

### 4.8. `vw_resultados_completos`
Visão SQL otimizada que unifica geometria, indicadores, parâmetros e metadados para consultas das futuras interfaces React, rotas REST e servidores MCP.

---

## 5. Procedimento Operacional e Reprodutibilidade

Para recriar e validar o banco a partir de uma instalação limpa:

```bash
# 1. Subir o contêiner PostgreSQL 17 + PostGIS 3.5 e aplicar migrações:
./scripts/db_up.sh

# 2. Importar malha, observações censitárias e resultados históricos:
python3 scripts/importar_dados_banco.py

# 3. Executar a suíte formal de testes de persistência:
./scripts/test_persistencia.sh

# 4. Executar os testes C++26 e integração via CMake / CTest:
cmake --build build -j
ctest --test-dir build --output-on-failure
```

---

## 6. Parecer Conclusivo da Homologação

A entrega **MÉTIS — Prioridade Técnica 001** cumpre 100% dos requisitos estipulados no plano arquitetural:
1. Nenhuma alteração foi realizada nas equações, parâmetros ou código científico do modelo de referência `EPS-REF-001`.
2. A interface web e seus servidores continuam operando normalmente.
3. A integridade dos dados históricos e censitários é verificável por testes automatizados em CTest e Python.
4. O repositório está pronto para receber as próximas etapas evolutivas (React, REST e MCP).

> **Homologado por:** Equipe MÉTIS / Ecossistema SisTer  
> **Status:** Concluído e pronto para integração.
