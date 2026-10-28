# MÉTIS — Inteligência adaptativa (v0.1.0)

> **"A inteligência que queremos investigar não é simplesmente a capacidade de produzir uma resposta correta, mas a capacidade de reconhecer, diante da realidade, quando suas próprias referências precisam ser reconsideradas."**

**MÉTIS** integra o ecossistema científico do **LABECO** (SisTer, MORFO, SisTer-Git). Não é apenas um sistema que calcula índices municipais: é uma experiência científica e computacional orientada a investigar se um sistema computacional consegue reconhecer as limitações de suas próprias representações e, diante de evidências, sustentar uma **reconfiguração verificável**.

---

## 🧠 Origem Conceitual: Por que MÉTIS?

Na tradição filosófica clássica, *Métis* designa a inteligência prática, relacional e adaptativa — a capacidade de apreender as condições do meio, lidar com a incerteza e reconfigurar a ação diante do inesperado.

O MÉTIS opera como um laboratório de **descrição e investigação agroterritorial geral**, orientado universalmente aos 497 municípios do Rio Grande do Sul:
1. **Organização e cálculo verificável**: computa o estado de referência ($R$) a partir do acoplamento relacional entre as dimensões Ecológica ($E$), Produtiva ($P$) e Social ($S$).
2. **Transparência matemática**: explicita as fórmulas, variáveis brutas e parâmetros estatísticos (como percentis de corte $q_{10}$ e $q_{90}$), tornando visível o porquê de cada pontuação sem ocultar dados sob um índice escalar único.
3. **Detecção de limites representacionais**: confronta os modelos matemáticos com a diversidade dos sistemas territoriais, permitindo ao pesquisador identificar onde métricas abstratas encontram seus limites e demandam evolução epistêmica.

---

## 🏛️ Identidade Visual SisTer-Git & Painel Local

A interface web em `web/` foi harmonizada com o design system do **SisTer-Git / MORFO**:
- **Paleta profunda SisTer**: base marinho profunda (`#071e38`), acentos céu/teal (`#2ea8e8`, `#087f8c`) e superfícies contrastadas (`#ffffff`, `#edf2f8`).
- **Ícone do Cérebro (Brain)**: símbolo vetorial da inteligência adaptativa e das sinapses relacionais.
- **Cartografia SVG Pura**: mapa coroplético dos 497 municípios do Rio Grande do Sul sem dependências externas, bibliotecas remotas ou telemetria.
- **Decomposição Analítica**: inspeção detalhada de cada município ($R, E, P, S$) e cruzamento com dados censitários brutos.

---

## ⚙️ Compilação e Testes (C++26)

Requer toolchain moderno com suporte a C++26 (`-std=c++2c` / `-std=c++26`), como GCC 14+ e CMake >= 3.30.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
ctest --test-dir build --output-on-failure
```

---

## 📡 Extração Oficial via API SIDRA (IBGE)

Para obter e harmonizar os dados dos **497 municípios do RS** referentes ao Censo Agropecuário 2017 diretamente do IBGE:

```bash
python3 scripts/carregar_dados_ibge.py
```

O script consulta as tabelas **6881**, **6898**, **6780** e **6773** do SIDRA e gera:
`data/gerados/municipios_rs_2017_homologado.csv`

---

## 🧮 Executar o Cálculo Oficial dos 497 Municípios

```bash
./build/resiliencia-rs compute data/gerados/municipios_rs_2017_homologado.csv results/RS_497_RESULTADOS.csv
```

Saídas geradas:
- `results/RS_497_RESULTADOS.csv`: resultados calculados para os 497 municípios.
- `results/RS_497_RESULTADOS.manifest.json`: manifesto com parâmetros $q_{10}$, $q_{90}$, universo e integridade.

---

## 🌐 Visualizador Web (Rede Local & Acesso Direto)

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

O painel carrega automaticamente os resultados oficiais dos 497 municípios e a malha cartográfica GeoJSON do IBGE, permitindo a seleção e inspeção de qualquer município em destaque interativo.

---

## 🗺️ Roadmap v0.1.1 — Exploração e Descrição Agroterritorial Municipal

O próximo incremento do MÉTIS aprofunda a transparência cognitiva e descritiva:
- **Exploração em Dois Níveis:**
  - **Zoom Territorial no SVG:** ao selecionar qualquer município, o enquadramento cartográfico aproxima suavemente seus limites através da manipulação do `viewBox`, com controle para restaurar a visão estadual completa a qualquer momento.
  - **Detalhamento Analítico Modular ($E, P, S, R$):** inspeção aberta de cada dimensão, apresentando dados brutos censitários (IBGE/SIDRA), fórmulas aplicadas, parâmetros de calibração ($q_{10}, q_{90}$) e explicações conceituais de eventuais pontuações extremas ou dados incompletos.
- **Auditoria Epistêmica:** antes de automatizar a auto-reconfiguração, o sistema capacita o pesquisador a avaliar as relações entre dados, representação matemática e o território real.

---

## 📜 Licença

Distribuído sob a licença **GNU General Public License v3.0 (GPL v3.0)**. Consulte o arquivo [LICENSE](LICENSE) para obter o texto completo.

## 🔗 Repositório Remoto

```bash
git remote add origin git@github.com:jpereiratrindade/METIS.git
```
