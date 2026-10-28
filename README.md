# MÉTIS — Inteligência adaptativa (v0.1.0)

> **"A inteligência que queremos investigar não é simplesmente a capacidade de produzir uma resposta correta, mas a capacidade de reconhecer, diante da realidade, quando suas próprias referências precisam ser reconsideradas."**

**MÉTIS** integra o ecossistema científico do **LABECO** (SisTer, MORFO, SisTer-Git). Não é apenas um sistema que calcula índices municipais: é uma experiência científica e computacional orientada a investigar se um sistema computacional consegue reconhecer as limitações de suas próprias representações e, diante de evidências, sustentar uma **reconfiguração verificável**.

---

## 🧠 Origem Conceitual: Por que MÉTIS?

Na tradição filosófica clássica, *Métis* designa a inteligência prática, relacional e adaptativa — a capacidade de apreender as condições do meio, lidar com a incerteza e reconfigurar a ação diante do inesperado.

O caso do primeiro teste em **Bagé** ilustra o cerne dessa investigação:
1. O sistema calculou o estado agroterritorial de Bagé ($R = 21,15$) a partir de suas funções de referência.
2. A métrica estritamente financeira de densidade monetária por hectare ($P = 0,0$) penalizou a pecuária conservacionista do Bioma Pampa, contrastando com o alto valor do multiplicador ecológico ($E = 1,09$, com quase 60% de vegetação nativa preservada).
3. O confronto entre o modelo e a realidade territorial evidencia um limite representacional: cabe ao sistema registrar a anomalia, acolher novas hipóteses de parametrização e sustentar a reconfiguração sem perder a memória e a rastreabilidade da configuração anterior.

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

## 🌐 Visualizador Web

Inicie o servidor HTTP local na raiz:

```bash
python3 -m http.server 8080 --directory .
```

Abra no navegador:
`http://localhost:8080/web/index.html`

O painel carrega automaticamente os resultados oficiais dos 497 municípios e a malha cartográfica GeoJSON do IBGE, exibindo Bagé e demais municípios em destaque interativo.

---

## 📜 Licença

Distribuído sob a licença **GNU General Public License v3.0 (GPL v3.0)**. Consulte o arquivo [LICENSE](LICENSE) para obter o texto completo.

## 🔗 Repositório Remoto

```bash
git remote add origin git@github.com:jpereiratrindade/METIS.git
```
