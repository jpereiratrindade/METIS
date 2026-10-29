# MÉTIS — Laboratório Científico Aberto de Resiliência Agroterritorial (v0.3.0)

> **"A inteligência que queremos investigar não é simplesmente a capacidade de produzir uma resposta correta, mas a capacidade de reconhecer, diante da realidade, quando suas próprias referências precisam ser reconsideradas."**

**MÉTIS** integra o **Ecossistema SisTer** (SisTer, MORFO, SisTer-Git). Constitui um laboratório computacional público e aberto para formular, parametrizar, experimentar, confrontar e revisar hipóteses sobre as relações entre condições ecológicas, produtivas e sociais e a capacidade adaptativa de sistemas agroterritoriais.

Sob a diretriz **`METIS-OPEN-001`**, o MÉTIS consolida o **acesso público universal sem autenticação**, estruturado em quatro ambientes complementares com proveniência e exportação reproduzível de experimentos.

---

## 🌐 Ambientes e Espaços de Trabalho Web

| Espaço | Rota Local | Descrição |
| :--- | :--- | :--- |
| **Apresentação & Notícias** | [`index.html`](http://localhost:8080/) | Portal institucional SisTer, fundamentos científicos, feed dinâmico de achados e notícias. |
| **Visão Territorial** | [`mapa.html`](http://localhost:8080/mapa.html) | Cartografia interativa reativa dos 497 municípios do RS com alternância de camadas (R, E, P, S). |
| **Dashboard Analítico** | [`dashboard.html`](http://localhost:8080/dashboard.html) | Exploração rápida e numérica sem mapa, simulador paramétrico e exportação de manifestos JSON/CSV. |
| **Modelos & Algoritmos** | [`modelos.html`](http://localhost:8080/modelos.html) | Catálogo matemático formal, pipeline algorítmico e hipóteses dos 4 modelos. |

---

## 📡 API Pública de Distribuição (Somente Leitura)

- `GET /api/public/achados.json`: Catálogo de achados científicos categorizados (`achado_corroborado`, `resultado_calculado`, `hipotese`, `simulacao`, `atualizacao_tecnica`).
- `GET /api/public/noticias.json`: Notícias e comunicados do laboratório.
- `GET /api/public/resumos.json`: Resumos em linguagem acessível para totens digitais e portais.
- `GET /api/public/modelos.json`: Metadados, fórmulas e parâmetros dos 4 modelos.

---

## 🏛️ Organização Conceitual Quádrupla

Para assegurar rigor epistêmico, o sistema distingue quatro elementos fundamentais:

| Elemento | Função no MÉTIS |
| :--- | :--- |
| **Variáveis** | Dados observados brutos censitários (IBGE / Censo Agropecuário 2017). |
| **Indicadores** | Relações matemáticas construídas a partir das variáveis ($d_m = \text{VP}/A$, cobertura vegetal natural $e$, assistência técnica). |
| **Modelos** | Formulações conceituais que organizam indicadores, componentes e suas interações. |
| **Cenários** | Execuções de um modelo sob parâmetros, calibrações e condições experimentais declaradas. |

---

## 🔬 Três Eixos Independentes de Investigação (Bancada Triaxial)

1. **Eixo 1 — Modelo Teórico:**
   - **`EPS-REF-001` (Referência):** Formulação original $R = E(P+S)$ com calibração empírica da produtividade por percentis estaduais ($q_{10}$ e $q_{90}$).
   - **`EPS-EXP-002` (Aditivo Linear Ponderado):** Componentes independentes combinados por soma linear ponderada: $R = w_e E + w_p P + w_s S$.
   - **`EPS-EXP-003` (Interativo com Acoplamento Não-Linear):** Interações sinérgicas explícitas entre coesão social e capacidade produtiva: $R = E(P+S) + \lambda \frac{P \cdot S}{50}$.
   - **`EPS-EXP-004` (Autônomo DIR-MUN-001):** Análise municipal individual com escala $k$ explícita e estrita invariância intermunicipal ($P = 50 \frac{d_m}{d_m+k}$).
2. **Eixo 2 — Ano de Referência:**
   - **2017:** Censo Agropecuário oficial homologado (497 municípios do RS).
   - Suporte arquitetural extensível para múltiplas séries históricas.
3. **Eixo 3 — Tipo de Trajetória:**
   - **Experimental:** Exploração interativa de cenários, sensibilidade a parâmetros e confrontos contrafactuais.
   - **Histórica:** Leitura estrita de dados observados em períodos consolidados.

> [!NOTE]
> Os resultados calculados constituem indicadores exploratórios de hipóteses concorrentes e **não representam medidas empiricamente validadas de resiliência**. As divergências entre modelos revelam os limites teóricos de cada formulação.

---

## 🗺️ Cartografia Reativa & Confronto Intramunicipal

- **Tendência Territorial Estadual:** O mapa SVG é caracterizado por padrão por **$R$** (com alternância para $E$, $P$ e $S$) e recalcula sua coloração em tempo real ao alternar de modelo ou ajustar parâmetros.
- **Confronto Exclusivamente Intramunicipal (Aba M · Confronto):** Ao selecionar um município, a interface apresenta uma matriz comparando lado a lado as pontuações e desvios ($\Delta R$ vs REF) de todos os 4 modelos para aquele município específico sob os mesmos dados empíricos observados.
- **Ambiente Analítico Municipal em Quatro Áreas:**
  - **Área D — Resultados:** Valores e diagnósticos do modelo ativo.
  - **Área M — Confronto:** Tabela comparativa dos 4 modelos para o município.
  - **Área A — Insumos:** Variáveis censitárias brutas do IBGE/SIDRA.
  - **Área B — Parâmetros:** Controles de sensibilidade paramétrica do modelo ativo ($k$, pesos, $\lambda$).
  - **Área C — Hipótese:** Equação e justificativa epistemológica da formulação selecionada.

---

## ⚙️ Compilação e Testes Automatizados (C++26)

Requer toolchain moderno com suporte a C++26 (`-std=c++2c` / `-std=c++26`), como GCC 14+ e CMake >= 3.30.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
ctest --test-dir build --output-on-failure
```

O conjunto de testes verifica automaticamente os 4 modelos do catálogo, a função de confronto intramunicipal e a invariância municipal.

---

## 🧮 Executar o Cálculo Oficial via CLI

```bash
# Execução com o modelo de referência histórica (padrão):
./build/resiliencia-rs compute data/gerados/municipios_rs_2017_homologado.csv results/RS_497_RESULTADOS.csv --model EPS-REF-001

# Execução com modelo aditivo ponderado:
./build/resiliencia-rs compute data/gerados/municipios_rs_2017_homologado.csv results/RS_497_RESULTADOS.csv --model EPS-EXP-002

# Execução com modelo autônomo municipal (k = 2000 R$/ha):
./build/resiliencia-rs compute data/gerados/municipios_rs_2017_homologado.csv results/RS_497_RESULTADOS.csv --model EPS-EXP-004 --k 2000.0
```

Saídas geradas:
- `results/RS_497_RESULTADOS.csv`: dados e pontuações calculadas de forma autônoma para os 497 municípios.
- `results/RS_497_RESULTADOS.manifest.json`: manifesto com parâmetros experimentais declarados, versão do modelo (`EPS-DIR-MUN-001/0.2.0`) e integridade.
- `results/historico/`: manifestos e resultados da formulação v0.1.0 histórica preservados para reprodutibilidade.

---

## 🚀 Execução Unificada com Único Script (`./run.sh`)

O MÉTIS é 100% padronizado para operar através de um único orquestrador unificado ([`run.sh`](run.sh)):

```bash
# Iniciar o ambiente completo (C++26 + PostgreSQL/PostGIS + Migrações + Importação + Servidor Web):
./run.sh

# Executar todos os testes automatizados (CTest C++26 e PostGIS):
./run.sh test

# Verificar integridade completa de compilação, banco de dados e testes:
./run.sh check

# Comandos específicos para controle do banco de dados:
./run.sh db status       # Inspeciona estado do contêiner
./run.sh db down         # Para o serviço de banco
./run.sh db up           # Sobe o banco e aplica migrações
./run.sh db import       # Força reimportação dos dados censitários
```

Ao executar `./run.sh` sem parâmetros, o orquestrador realiza automaticamente em cascata:
1. Carrega ou cria o arquivo `.env` a partir de `.env.example`.
2. Verifica e compila o núcleo C++26 nativo via CMake (se necessário).
3. Inicia o contêiner PostgreSQL 17 + PostGIS 3.5 (`metis-db`).
4. Executa migrações SQL versionadas pendentes.
5. Importa as observações e geometrias censitárias se o banco for novo.
6. Cria os atalhos de roteamento direto para a web.
7. Abre o servidor web na porta `8080` (configurável via `METIS_PORT`).

Acesse no navegador:
- **Apresentação & Notícias:** `http://localhost:8080/`
- **Visão Territorial (RS 497):** `http://localhost:8080/mapa.html`
- **Dashboard Analítico:** `http://localhost:8080/dashboard.html`
- **Modelos & Algoritmos:** `http://localhost:8080/modelos.html`
- **Rede Local (IP):** `http://<IP_DA_REDE>:8080/` (ex: `http://10.163.80.176:8080/`)

---

## ⚖️ Conformidade Legal Brasileira (LGPD, LAI e Dados Abertos)

O MÉTIS foi concebido em estrita consonância com o ordenamento jurídico brasileiro e as diretrizes de transparência pública:

1. **LGPD (Lei Geral de Proteção de Dados - Lei nº 13.709/2018):**
   - **Bases Estatísticas Agregadas (Art. 12):** O sistema opera unicamente sobre dados agregados censitários em escala municipal oficial. Não há tratamento de dados pessoais, nem identificação direta ou indireta de pessoas físicas, agricultores familiares ou propriedades privadas.
   - **Privacidade por Padrão (*Privacy by Default*):** O acesso público é universal e não exige cadastro, senha, login ou fornecimento de e-mail. Não são empregados cookies analíticos de terceiros nem técnicas de rastreamento individual.
2. **Lei de Acesso à Informação (LAI - Lei nº 12.527/2011) e Governo Digital (Lei nº 14.129/2021):**
   - Transparência pública ativa (Art. 8º): fórmulas, dados brutos, parâmetros e resultados são plenamente auditáveis e exportáveis.
   - Padrões de dados abertos (Decreto nº 8.777/2016): dados servidos em formatos não-proprietários e estruturados (`.csv`, `.json`).
3. **Citação e Atribuição de Fontes Oficiais (IBGE):**
   - Dados provenientes do Instituto Brasileiro de Geografia e Estatística (Censo Agropecuário 2017 / SIDRA, tabelas 6881, 6898, 6780 e 6773).
4. **Isenção de Responsabilidade (Scientific Disclaimer):**
   - Os resultados calculados destinam-se exclusivamente à pesquisa acadêmica, exploração de hipóteses e apoio ao debate público. **Não constituem decisão automatizada vinculante (Art. 20 da LGPD), nem base isolada para sanções fiscais/ambientais ou pontuação de crédito rural.**

Consulte o documento completo: [METIS-DIR-LEG-001 — Marco Legal, Governança de Dados e Responsabilidade Científica](docs/GOVERNANCA-DADOS-E-MARCO-LEGAL.md).

---

## ♿ Usabilidade, Acessibilidade e Engenharia Centrada no Usuário

A concepção das interfaces e do pipeline computacional segue os modelos consagrados de usabilidade e acessibilidade:

- **10 Heurísticas de Jakob Nielsen:** Feedback imediato de status, consistência de navegação entre páginas, prevenção contra inserção de zeros artificiais em dados censitários omissos e explicabilidade contínua de equações.
- **Mantra de Shneiderman:** *"Overview first, zoom and filter, then details-on-demand"* na cartografia SVG e no dashboard analítico.
- **Acessibilidade Web (e-MAG / WCAG 2.1 AA):** Semântica HTML5, contraste cromático em conformidade, navegação integral por teclado e rótulos ARIA para leitores de tela.
- **Diretriz Ética Anti-Ranqueamento:** Proibição de ranqueamento competitivo entre municípios, substituído pelo confronto intramunicipal entre modelos.

Consulte o guia completo: [METIS-DIR-USA-001 — Diretrizes de Usabilidade, Acessibilidade e Boas Práticas](docs/USABILIDADE-ACESSIBILIDADE-E-BOAS-PRATICAS.md).

---

## 📚 Mapa da Documentação Técnica e Epistêmica

O acervo documental completo está reunido no diretório [`docs/`](docs/README.md):

| Documento | Identificador | Tema Central |
| :--- | :--- | :--- |
| [HOMOLOGACAO-PERSISTENCIA-001.md](docs/HOMOLOGACAO-PERSISTENCIA-001.md) | `METIS-REL-PERSIST-001` | Homologação da Persistência PostgreSQL/PostGIS (Prioridade 001) |
| [GOVERNANCA-DADOS-E-MARCO-LEGAL.md](docs/GOVERNANCA-DADOS-E-MARCO-LEGAL.md) | `METIS-DIR-LEG-001` | LGPD, LAI, Dados Abertos, Citação IBGE e Disclaimer Científico |
| [USABILIDADE-ACESSIBILIDADE-E-BOAS-PRATICAS.md](docs/USABILIDADE-ACESSIBILIDADE-E-BOAS-PRATICAS.md) | `METIS-DIR-USA-001` | Nielsen, Shneiderman, WCAG 2.1, e-MAG e Transparência Algorítmica |
| [METIS-OPEN-001_v0.1.0.md](docs/METIS-OPEN-001_v0.1.0.md) | `METIS-OPEN-001` | Laboratório aberto, acesso sem login, dashboard analítico e API |
| [METIS-DIR-MULTI-002.md](docs/METIS-DIR-MULTI-002.md) | `METIS-DIR-MULTI-002` | Bancada triaxial e catálogo dos 4 modelos concorrentes |
| [METIS-DIR-MUN-001.md](docs/METIS-DIR-MUN-001.md) | `METIS-DIR-MUN-001` | Reorientação municipal autônoma e invariância intermunicipal |
| [EXPLORACAO-TERRITORIAL_v0.1.1.md](docs/EXPLORACAO-TERRITORIAL_v0.1.1.md) | `METIS-SPEC-EXP-002` | Especificação técnica de interface cartográfica em 2 níveis |
| [RESILIENCIA-SISTEMA-EXP-001_v0.1.0.md](docs/RESILIENCIA-SISTEMA-EXP-001_v0.1.0.md) | `RESILIENCIA-EXP-001` | Formulação experimental de referência histórica (v0.1.0) |

---

## 🗄️ Persistência Científica Versionada (PostgreSQL 17 + PostGIS 3.5)

Conforme a **Prioridade Técnica 001**, o MÉTIS conta com uma camada de persistência científica com rastreabilidade integral:

- **PostGIS 3.5 com SRID 4326:** Malha municipal vetorial completa dos 497 municípios gaúchos.
- **Rastreabilidade e Proveniência:** Registro das fontes do Censo Agropecuário 2017 com somas de verificação SHA-256 auditáveis.
- **Execuções Experimentais & Manifestos:** Registro das execuções e resultados de `EPS-REF-001/0.1.0` e vigentes com parâmetros em `JSONB`.
- **Base para Futuras Entregas:** Visão analítica `vw_resultados_completos` preparada para as próximas interfaces React, APIs REST e servidores MCP.

```bash
# Iniciar o banco (via Podman/Docker) e aplicar migrações:
./scripts/db_up.sh

# Importar dados censitários, geometrias e resultados de referência:
python3 scripts/importar_dados_banco.py

# Executar a suíte formal de testes de persistência:
./scripts/test_persistencia.sh

# Parar o contêiner:
./scripts/db_down.sh
```

Consulte o relatório formal: [METIS-REL-PERSIST-001 — Homologação da Persistência Científica](docs/HOMOLOGACAO-PERSISTENCIA-001.md).

---

## 📜 Licença

Distribuído sob a licença **GNU General Public License v3.0 (GPL v3.0)**. Consulte o arquivo [LICENSE](LICENSE) para obter o texto completo.

## 🔗 Repositório Remoto

```bash
git remote add origin git@github.com:jpereiratrindade/METIS.git
```
