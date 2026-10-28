# MÉTIS — Laboratório Computacional de Resiliência Agroterritorial (v0.2.0)

> **"A inteligência que queremos investigar não é simplesmente a capacidade de produzir uma resposta correta, mas a capacidade de reconhecer, diante da realidade, quando suas próprias referências precisam ser reconsideradas."**

**MÉTIS** integra o ecossistema científico do **LABECO** (SisTer, MORFO, SisTer-Git). Constitui um laboratório computacional para formular, parametrizar, experimentar, confrontar e revisar hipóteses sobre as relações entre condições ecológicas, produtivas e sociais e a resiliência de sistemas agroterritoriais.

Conforme a diretriz **`METIS-DIR-MUN-001`**, o MÉTIS adota o **município como unidade individual e autônoma de investigação**, sem utilizar resultados de outros municípios para determinar suas pontuações nem estabelecer rankings ou classificações de desempenho.

---

## 🏛️ Princípio Fundamental de Invariância (METIS-DIR-MUN-001)

> **"A alteração dos dados de outro município não poderá modificar o resultado calculado para o município em análise, mantendo-se constantes seus próprios dados, a versão do modelo e seus parâmetros experimentais."**

- **Sem normalização intermunicipal:** Eliminação de percentis estaduais ($q_{10}, q_{90}$), médias globais ou rankings competitivos.
- **Observável produtivo:** $d_m = \frac{\text{VP}_m}{A_m}$ (R$/ha), identificado como **densidade monetária da produção**.
- **Parametrização experimental explícita:**
  $$P_m(k) = 50 \times \frac{d_m}{d_m + k}, \quad k > 0$$
  onde $k$ possui unidade R$/ha$ e expressa uma hipótese de escala paramétrica declarada (valor padrão de referência: $1500{,}0\text{ R\$/ha}$), sem valores arbitrários ocultos.
- **Hipótese relacional preservada:**
  $$R_m = E_m \times (P_m + S_m)$$
  onde $E_m$ atua como modulador ecológico multiplicativo.

> [!NOTE]
> Os resultados calculados constituem indicadores exploratórios de hipóteses de trabalho e **não representam medidas empiricamente validadas de resiliência**.

---

## 🔬 Ambiente Analítico Municipal (Quatro Áreas)

A seleção territorial ativa uma bancada analítica decomposta em 4 áreas estruturadas:
- **Área A — Observações do Município:** Dados brutos do Censo Agropecuário 2017 (IBGE/SIDRA), unidades de medida, ano e metadados de coleta.
- **Área B — Parametrização Experimental:** Controle de sensibilidade interativo do parâmetro de escala $k$ (R$/ha$), equações e justificativas epistemológicas.
- **Área C — Hipótese Relacional:** Equação $R = E(P+S)$ e rastreabilidade da hipótese multiplicadora ecológica.
- **Área D — Resultados e Confronto:** Decomposição dos indicadores $R, E, P, S$, densidade monetária $d_m$, limitações e advertências metodológicas.

---

## ⚙️ Compilação e Testes Automatizados (C++26)

Requer toolchain moderno com suporte a C++26 (`-std=c++2c` / `-std=c++26`), como GCC 14+ e CMake >= 3.30.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
ctest --test-dir build --output-on-failure
```

O conjunto de testes verifica automaticamente a **invariância municipal** (o cálculo de um município isolado produz resultado idêntico ao cálculo inserido em qualquer lote de municípios).

---

## 📡 Extração Oficial via API SIDRA (IBGE)

Para obter e harmonizar os dados dos **497 municípios do RS** referentes ao Censo Agropecuário 2017 diretamente do IBGE:

```bash
python3 scripts/carregar_dados_ibge.py
```

O script consulta as tabelas **6881**, **6898**, **6780** e **6773** do SIDRA e gera:
`data/gerados/municipios_rs_2017_homologado.csv`

---

## 🧮 Executar o Cálculo Municipal (CLI)

```bash
# Execução com valor padrão de k (1500.0 R$/ha):
./build/resiliencia-rs compute data/gerados/municipios_rs_2017_homologado.csv results/RS_497_RESULTADOS.csv

# Execução com parametrização experimental específica para k:
./build/resiliencia-rs compute data/gerados/municipios_rs_2017_homologado.csv results/RS_497_RESULTADOS.csv --k 2000.0
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
