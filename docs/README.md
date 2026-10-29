# MÉTIS — Acervo Documental e Arquitetura do Conhecimento

Bem-vindo ao índice central da documentação científica, arquitetural e normativa do **MÉTIS** (Laboratório Científico Aberto de Resiliência Agroterritorial), componente do **Ecossistema SisTer**.

---

## 🗺️ Mapa de Documentos

```
docs/
├── README.md                               # Este índice geral do acervo
├── METIS-DIR-EVID-001.md                   # [METIS-DIR-EVID-001] Diretriz de evidências climáticas (AdaptaBrasil/INMET) e episódios investigativos
├── HOMOLOGACAO-PERSISTENCIA-001.md         # [METIS-REL-PERSIST-001] Relatório de homologação da camada de persistência
├── GOVERNANCA-DADOS-E-MARCO-LEGAL.md       # [METIS-DIR-LEG-001] Conformidade LGPD, LAI, Dados Abertos e Disclaimer
├── USABILIDADE-ACESSIBILIDADE-E-BOAS-PRATICAS.md # [METIS-DIR-USA-001] Nielsen, Shneiderman, WCAG 2.1 e e-MAG
├── METIS-OPEN-001_v0.1.0.md                # Diretriz de abertura pública universal, API e dashboard
├── METIS-DIR-MULTI-002.md                  # Laboratório multimodelo, multitemporal e bancada triaxial
├── METIS-DIR-MUN-001.md                    # Reorientação metodológica: invariância municipal e escala k
├── EXPLORACAO-TERRITORIAL_v0.1.1.md        # Especificação técnica da interface cartográfica e analítica
└── RESILIENCIA-SISTEMA-EXP-001_v0.1.0.md   # Prova conceitual de referência inicial (EPS-REF-001)
```

---

## 📋 Síntese dos Documentos Normativos e Técnicos

### 1. Governança, Legislação e Ética
- **[GOVERNANCA-DADOS-E-MARCO-LEGAL.md](GOVERNANCA-DADOS-E-MARCO-LEGAL.md) (`METIS-DIR-LEG-001` - v1.0.0):**  
  Analisa e fundamenta a conformidade jurídica com a **LGPD (Lei 13.709/2018)** (não tratamento de dados pessoais em bases estatísticas municipais e privacidade por design), a **LAI (Lei 12.527/2011)** e o **Decreto de Dados Abertos (Decreto 8.777/2016)**, a licença livre **GNU GPL v3.0**, a atribuição às bases do **IBGE (Censo Agropecuário 2017)** e o **Termo de Responsabilidade Científica (Disclaimer)** com vedação a ranqueamentos competitivos.

### 2. Usabilidade, Acessibilidade e Engenharia
- **[HOMOLOGACAO-PERSISTENCIA-001.md](HOMOLOGACAO-PERSISTENCIA-001.md) (`METIS-REL-PERSIST-001` - v1.0.0):**  
  Homologação formal da **Prioridade Técnica 001**: banco PostgreSQL 17 + PostGIS 3.5, migrações versionadas, importação dos 497 municípios e observações do Censo Agropecuário 2017, integridade com os resultados do modelo `EPS-REF-001/0.1.0` e execução multimodelo vigente, rastreabilidade criptográfica por hashes SHA-256 e testes automatizados.
- **[USABILIDADE-ACESSIBILIDADE-E-BOAS-PRATICAS.md](USABILIDADE-ACESSIBILIDADE-E-BOAS-PRATICAS.md) (`METIS-DIR-USA-001` - v1.0.0):**  
  Avaliação formal segundo as **10 Heurísticas de Usabilidade de Nielsen**, aplicação do **Mantra da Exploração Visual de Shneiderman**, requisitos de **Acessibilidade Web (WCAG 2.1 AA / e-MAG brasileiro)** e padrões de transparência algorítmica e reprodutibilidade (princípios FAIR).

### 3. Evidências Empíricas e Vigilância Operacional
- **[METIS-DIR-EVID-001.md](METIS-DIR-EVID-001.md) (`METIS-DIR-EVID-001` - v0.1.0):**  
  Diretriz de integração contínua do **AdaptaBrasil (MCTI)** (558 indicadores, projeções IPCC 2030/2050) e do **INMET** (avisos meteorológicos operacionais em tempo real e cruzamento PostGIS via `ST_Intersects`). Define o **Motor de Episódios Investigativos** que congela o estado basal $R(t_0)$ perante eventos severos e estabelece o isolamento epistêmico entre a equação matemática territorial e a confrontação empírica externa.

### 4. Abertura Científica e Distribuição Pública
- **[METIS-OPEN-001_v0.1.0.md](METIS-OPEN-001_v0.1.0.md) (`METIS-OPEN-001` - v0.1.0):**  
  Diretriz arquitetural para acesso público universal sem autenticação, isolamento de credenciais, estruturação do feed de achados científicos categorizados, resumos didáticos para totens digitais e contratos da API REST somente-leitura.

### 5. Metodologia Multimodelo e Triaxial
- **[METIS-DIR-MULTI-002.md](METIS-DIR-MULTI-002.md) (`METIS-DIR-MULTI-002` - v0.3.0):**  
  Especifica a evolução para a Bancada Epistêmica Triaxial (Modelo, Ano de Referência, Trajetória) e define os quatro modelos do catálogo: `EPS-REF-001` (Referência histórica), `EPS-EXP-002` (Aditivo linear), `EPS-EXP-003` (Sinergia não-linear) e `EPS-EXP-004` (Autônomo municipal).
- **[METIS-DIR-MUN-001.md](METIS-DIR-MUN-001.md) (`METIS-DIR-MUN-001` - v0.1.0):**  
  Documenta a decisão de reorientação para adotar o município como unidade individual e autônoma de investigação, eliminando a dependência intermunicipal por quantis e introduzindo a escala $k$.

### 6. Especificação Funcional e Histórico Conceitual
- **[EXPLORACAO-TERRITORIAL_v0.1.1.md](EXPLORACAO-TERRITORIAL_v0.1.1.md) (`METIS-SPEC-EXP-002` - v0.2.0):**  
  Detalhamento da interface em dois níveis (visão cartográfica dinâmica e ambiente analítico municipal em quatro áreas: A-Insumos, B-Parâmetros, C-Hipótese, D-Resultados).
- **[RESILIENCIA-SISTEMA-EXP-001_v0.1.0.md](RESILIENCIA-SISTEMA-EXP-001_v0.1.0.md) (`RESILIENCIA-SISTEMA-EXP-001` - v0.1.0):**  
  Registro histórico da primeira prova de cálculo executável e da formulação original $R = E(P+S)$.

---

## 🔬 Princípio Orientador Permanente

> **"Sempre pronto. Sempre incompleto!"**  
> Toda a documentação e código do MÉTIS são versionados com rigor no Git para permitir que a comunidade científica audite, critique e aprimore as hipóteses de modelagem territorial.
