# MÉTIS — Laboratório Multimodelo e Multitemporal de Resiliência Agroterritorial (v0.3.0)

> **"A inteligência que queremos investigar não é simplesmente a capacidade de produzir uma resposta correta, mas a capacidade de reconhecer, diante da realidade, quando suas próprias referências precisam ser reconsideradas."**

**MÉTIS** integra o ecossistema científico do **LABECO** (SisTer, MORFO, SisTer-Git). Constitui um laboratório computacional para formular, parametrizar, experimentar, confrontar e revisar hipóteses sobre as relações entre condições ecológicas, produtivas e sociais e a resiliência de sistemas agroterritoriais.

Conforme a diretriz **`METIS-DIR-MULTI-002`**, o MÉTIS evolui de um calculador de índice estático para um **laboratório de múltiplos modelos experimentais**, permitindo ao pesquisador selecionar um município e investigar como diferentes formulações teóricas e parametrizações produzem interpretações distintas das condições territoriais.

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

## 🔬 Três Eixos Independentes de Investigação

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

## 🌐 Visualizador Territorial Web (Rede Local & Acesso Direto)

Inicie o servidor HTTP com escuta na rede local (`0.0.0.0`):

```bash
./run.sh
```

Ou diretamente via Python:

```bash
python3 -m http.server 8080 --bind 0.0.0.0 --directory .
```

Abra no navegador pelo IP da máquina ou localmente, **direto na raiz (sem `/web`)**:
- `http://localhost:8080/`
- `http://<IP_DA_REDE>:8080/` (ex: `http://10.163.80.176:8080/`)
- `http://0.0.0.0:8080/`

O painel cartográfico opera como instrumento de **localização e contextualização territorial**, permitindo selecionar qualquer município individualmente, aproximar suavemente via zoom dinâmico SVG e experimentar diferentes parâmetros $k$ em tempo real.

---

## 📜 Licença

Distribuído sob a licença **GNU General Public License v3.0 (GPL v3.0)**. Consulte o arquivo [LICENSE](LICENSE) para obter o texto completo.

## 🔗 Repositório Remoto

```bash
git remote add origin git@github.com:jpereiratrindade/METIS.git
```
