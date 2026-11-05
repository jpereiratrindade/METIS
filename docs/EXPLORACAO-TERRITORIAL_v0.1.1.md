# MÉTIS — Especificação Técnica: Exploração Agroterritorial Municipal Autônoma
**Documento:** METIS-SPEC-EXP-002 (Revisões METIS-DIR-MUN-001, METIS-DIR-MULTI-002 e METIS-DIR-INMET-002)  
**Versão:** 0.3.0  
**Data:** 05/11/2026  
**Natureza:** Especificação funcional e arquitetural da interface de exploração cartográfica, vigilância meteorológica e investigação analítica municipal  
**Princípio orientador:** *"A alteração dos dados de outro município não poderá modificar o resultado calculado para o município em análise, mantendo-se constantes seus próprios dados, a versão do modelo e seus parâmetros experimentais."*

---

## 1. Propósito e Reorientação Metodológica (METIS-DIR-MUN-001)

O MÉTIS constitui um laboratório computacional para formular, parametrizar, experimentar, confrontar e revisar hipóteses sobre as relações entre condições ecológicas, produtivas e sociais e a resiliência de sistemas agroterritoriais.

Adota o **município como unidade individual e autônoma de investigação**, eliminando rankings, médias estaduais e normalizações intermunicipais arbitrárias:
1. **Invariância intermunicipal:** O resultado calculado para o município $A$ é estritamente invariante à inclusão, exclusão ou alteração de dados dos municípios $B, C, \dots$ no modelo municipal autônomo (`EPS-EXP-004`).
2. **Separação epistemológica:** Distinção explícita entre **observações censitárias brutas**, **parametrizações experimentais**, **hipótese relacional** e **confrontações empíricas externas** (AdaptaBrasil MCTI e INMET).
3. **Cartografia como localizador territorial e exploração temático-espacial:** O mapa SVG atua primordialmente como seletor espacial, contextualizador geográfico e interface de vigilância climática. Oferece visualização reativa de camadas temáticas ($R, \Delta R, \text{INMET}, \text{AdaptaBrasil}, E, P, S$), mantendo estrita proibição de ranqueamento competitivo, índices univariados de punição ou estigmatização de municípios.

---

## 2. Arquitetura de Exploração Territorial em Dois Níveis

### 2.1. Nível 1: Visão Cartográfica Estadual, Camadas Temáticas & Zoom Dinâmico

- **Preservação do SVG Puro:** Renderização vetorial nativa (`<svg id="map">`), com malha territorial completa dos 497 municípios do Rio Grande do Sul, sem dependências remotas ou bibliotecas externas de mapas pesadas.
- **Cartografia Temática Multicamada:**
  1. `resiliencia`: Estado de Resiliência Experimental ($R$) pelo modelo ativo.
  2. `evolucao`: Evolução Temporal Decenal ($\Delta R$ entre os Censos 2006 e 2017).
  3. `inmet`: Perturbações meteorológicas agudas ativas com severidade declarada.
  4. `adaptabrasil`: Vulnerabilidade crônica e Índice de Risco Climático na Disponibilidade de Alimentos (MCTI).
  5. `ecologica`: Multiplicador Ecológico ($E$).
  6. `produtiva`: Densidade Produtiva ($P(k)$).
  7. `social`: Dimensão Social e Associativa ($S$).
- **Seleção e Filtragem Individual de Alertas INMET (METIS-DIR-INMET-002):**
  - **Barra de Controle de Alertas (`#inmet-filter-toolbar`):** Quando a camada INMET é ativada, uma barra contextual permite alternar entre:
    - *Todos os Alertas Ativos:* Visão consolidada calculando o risco máximo sobreposto em cada município.
    - *Alerta Individual Específico:* Isolamento de um aviso meteorológico selecionado pelo código oficial (ex: `AVISO-202611-001`).
  - **Filtro Geográfico Reativo:** Ao isolar um aviso específico, o mapa destaca visualmente com a cor da severidade oficial (Amarelo = Perigo Potencial, Laranja = Perigo, Vermelho = Grande Perigo) apenas os municípios interceptados topologicamente via PostGIS (`ST_Intersects`), esmaecendo os demais municípios fora da mancha.
  - **Painel de Metadados do Alerta:** Exibe descrição do fenômeno, severidade, janela temporal (`inicio` ➔ `fim`), estado de vigência (`vigente` ou `previsto`) e botão rápido `↺ Ver todos` para restaurar a visão consolidada.
- **Enquadramento Dinâmico via `viewBox`:**
  - Visão geral estadual limpa e neutra: `viewBox="0 0 740 590"`.
  - Ao selecionar um município (clique ou busca): cálculo da *bounding box* $[x_{\min}, y_{\min}, x_{\max}, y_{\max}]$ com margem de respiro contextual (25%) e transição suave.
- **Controle de Retorno à Visão Estadual:**
  - Botão flutuante no mapa (`↺ Visão Estadual`) para restaurar a visão panorâmica sem prender o usuário.

---

### 2.2. Nível 2: Ambiente Analítico Municipal Estruturado em Sete Áreas Especializadas

Ao selecionar um município na malha ou busca, o painel lateral organiza a investigação científica através de sete abas especializadas:

```
┌────────────────────────────────────────────────────────────────────────┐
│ AMBIENTE ANALÍTICO MUNICIPAL                                           │
│ [D·Resultados] [T·Trajetória] [E·Evidências] [M·Confronto]             │
│ [A·Insumos]    [B·Parâmetros] [C·Hipótese]                             │
└────────────────────────────────────────────────────────────────────────┘
```

#### Área D — Resultados e Decomposição Dimensional
- Indicador experimental de resiliência ($R$) e barras dimensionais proporcionais ($E, P, S$).
- Densidade monetária da produção ($d_m$, em R$/ha$).
- Declaração explícita de limites e incertezas: **os resultados constituem indicadores exploratórios de uma hipótese de trabalho e não medidas empiricamente validadas de resiliência**.

#### Área T — Trajetória Decenal (Censos 2006 vs 2017)
- Comparação direta das séries censitárias oficiais do IBGE para o município.
- Variação líquida de área produtiva ($\Delta A$), valor da produção ($\Delta \text{VP}$) e preservação de remanescentes naturais ($\Delta \text{Vegetação}$).
- Análise da dinâmica da resiliência intercensitária ($\Delta R = R_{2017} - R_{2006}$).

#### Área E — Evidências Empíricas e Vigilância Climática (METIS-DIR-EVID-001)
- **Vulnerabilidade Estrutural Crônica (AdaptaBrasil MCTI):**
  - Risco de Disponibilidade de Alimentos (Baseline 2017, Projeções 2030 e 2050 sob RCP4.5).
  - Componentes de Exposição, Vulnerabilidade e Capacidade Adaptativa.
- **Perturbações Agudas em Tempo Real (INMET):**
  - Avisos meteorológicos vigentes incidindo sobre o polígono municipal.
  - Registro de Episódio Investigativo e estado basal congelado $R(t_0)$ perante eventos severos.

#### Área M — Confronto Multimodelo (Bancada Triaxial)
- Tabela comparativa avaliando o mesmo município sob os quatro modelos do catálogo:
  - `EPS-REF-001` (Referência E-P-S histórica com percentis)
  - `EPS-EXP-002` (Aditivo Linear Ponderado)
  - `EPS-EXP-003` (Acoplamento Não-Linear e Sinergia Social)
  - `EPS-EXP-004` (Autônomo Municipal com Escala $k$)
- Identificação de sensibilidade e desvios de formulação teórica.

#### Área A — Insumos Censitários Brutos
- Dados censitários oficiais do IBGE:
  - Área total dos estabelecimentos ($A$, em hectares);
  - Valor total da produção agropecuária ($\text{VP}$, em milhares de R$);
  - Área de pastagens naturais e matas/florestas nativas (ha);
  - Estabelecimentos assistidos e vinculados a cooperativas;
- Identificação de tabelas SIDRA de proveniência (6881, 6898, 6780, 6773).

#### Área B — Parametrização Experimental
- Declaração e ajuste interativo do parâmetro de escala da dimensão produtiva ($k$, em R$/ha$):
  - Função experimental: $P_m(k) = 50 \times \frac{d_m}{d_m + k}$, onde $d_m = \text{VP}_m / A_m$.
  - Sliders e inputs numéricos diretos para análise de sensibilidade em tempo real.
  - Ajuste de pesos $w_e, w_p, w_s$ e do acoplamento sinérgico $\lambda$.

#### Área C — Hipótese Relacional
- Formulação matemática completa do modelo ativo.
- Justificativa conceitual dos operadores (multiplicativos vs aditivos).
- Rastreabilidade de versionamento do modelo e integridade algorítmica.

---

## 3. Gestão de Lacunas e Integridade Amostral

- Municípios com insuficiência amostral ou dados ausentes na fonte censitária (`dados_incompletos`) são mantidos selecionáveis e visíveis.
- Padrão visual hachurado neutro no mapa SVG para indicar ausência de dado censitário na fonte original.
- Não há imputação artificial nem substituição de dados ausentes por zero. Indicadores não calculados permanecem devidamente sinalizados como incompletos.

---

## 4. Fontes e Proveniência Rastreável

- **Censo Agropecuário 2017 e 2006 (IBGE/SIDRA):** Tabelas 6881, 6898, 6780 e 6773.
- **Malha Municipal IBGE 2022:** Cartografia vetorial dos 497 municípios do RS com SRID 4326.
- **AdaptaBrasil MCTI:** 558 indicadores catalogados e projeções IPCC sob RCP4.5.
- **INMET Operacional:** API REST JSON e avisos meteorológicos auditáveis com histórico append-only e integridade criptográfica SHA-256.
