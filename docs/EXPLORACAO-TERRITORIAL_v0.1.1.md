# MÉTIS — Especificação Técnica: Exploração Agroterritorial Municipal Autônoma
**Documento:** METIS-SPEC-EXP-002 (Revisão METIS-DIR-MUN-001)  
**Versão:** 0.2.0  
**Data:** 28/10/2026  
**Natureza:** Especificação funcional e arquitetural da interface de exploração e investigação municipal  
**Princípio orientador:** *"A alteração dos dados de outro município não poderá modificar o resultado calculado para o município em análise, mantendo-se constantes seus próprios dados, a versão do modelo e seus parâmetros experimentais."*

---

## 1. Propósito e Reorientação Metodológica (METIS-DIR-MUN-001)

O MÉTIS constitui um laboratório computacional para formular, parametrizar, experimentar, confrontar e revisar hipóteses sobre as relações entre condições ecológicas, produtivas e sociais e a resiliência de sistemas agroterritoriais.

Adota o **município como unidade individual e autônoma de investigação**, eliminando rankings, médias estaduais e normalizações intermunicipais (como percentis $q_{10}$ e $q_{90}$):
1. **Invariância intermunicipal:** O resultado calculado para o município $A$ é estritamente invariante à inclusão, exclusão ou alteração de dados dos municípios $B, C, \dots$.
2. **Separação epistemológica:** Distinção explícita entre **observações censitárias brutas**, **parametrizações experimentais**, **hipótese relacional** e **resultados/confrontos**.
3. **Cartografia como localizador territorial e exploração temático-espacial:** O mapa SVG atua primordialmente como seletor espacial e contextualizador geográfico. Conforme ampliado pela diretriz `METIS-DIR-MULTI-002`, oferece visualização reativa de camadas temáticas ($R, E, P, S$), mantendo estrita proibição de ranqueamento competitivo, índices univariados de punição ou estigmatização de municípios.

---

## 2. Arquitetura de Exploração Territorial em Dois Níveis

### 2.1. Nível 1: Visão Cartográfica Estadual & Zoom Municipal Dinâmico
- **Preservação do SVG Puro:** Renderização vetorial nativa (`<svg id="map">`), sem dependências remotas ou bibliotecas externas.
- **Cartografia Temática Reativa e Contextual:** Preenchimento temático suave calibrado pelo indicador ativo ($R, E, P$ ou $S$) ou neutro uniforme, com distinção clara para municípios com dados censitários incompletos (`dados_incompletos`). Nenhuma coloração deve ser interpretada como classificação de virtude, prêmio ou demérito.
- **Enquadramento Dinâmico via `viewBox`:**
  - Visão geral estadual: `viewBox="0 0 740 590"`.
  - Ao selecionar um município (clique ou busca): cálculo da *bounding box* $[x_{\min}, y_{\min}, x_{\max}, y_{\max}]$ com margem de contexto (25%) e transição animada.
- **Controle de Retorno à Visão Estadual:**
  - Botão flutuante no mapa (`↺ Visão Estadual`) para restaurar a visão panorâmica sem desmarcar o município ativo.

### 2.2. Nível 2: Ambiente Analítico Municipal Estruturado em Quatro Áreas

Ao selecionar um município, o painel lateral organiza a investigação nas seguintes áreas fundamentais:

#### Área A — Observações do Município
- Dados censitários de origem (IBGE / Censo Agropecuário 2017):
  - Área total dos estabelecimentos ($A$, em hectares)
  - Valor total da produção agropecuária ($\text{VP}$, em milhares de R$)
  - Área de pastagens naturais e matas/florestas naturais (ha)
  - Número de estabelecimentos atendidos por assistência técnica e vinculados a cooperativas
  - Total de estabelecimentos agropecuários recenseados
- Metadados de proveniência (tabelas SIDRA 6881, 6898, 6780, 6773).

#### Área B — Parametrização Experimental
- Declaração e ajuste interativo do parâmetro de escala da dimensão produtiva ($k$, em R$/ha$):
  - Função experimental: $P_m(k) = 50 \times \frac{d_m}{d_m + k}$, onde $d_m = \text{VP}_m / A_m$.
  - Controle interativo por controle deslizante (*slider*) e campo numérico direto para análise de sensibilidade em tempo real.
  - Registro de justificativa: $k$ representa a densidade monetária de referência na qual $P = 25,0$ (meia escala), derivado de hipótese explícita e não da distribuição dos demais municípios.

#### Área C — Hipótese Relacional
- Formulação experimental ativa: $R_m = E_m \times (P_m + S_m)$.
- Justificativa da hipótese: papel multiplicador da dimensão ecológica ($E$), amplificando ou atenuando as capacidades produtivas e sociais acumuladas.
- Rastreabilidade de versionamento do modelo (`EPS-DIR-MUN-001/0.2.0`).

#### Área D — Resultados e Confronto
- Indicador experimental de resiliência ($R$) e decomposição em suas dimensões ($E, P, S$).
- Densidade monetária da produção ($d_m$, em R$/ha$).
- Declaração explícita de limites e incertezas: **os resultados constituem indicadores exploratórios de uma hipótese de trabalho e não medidas empiricamente validadas de resiliência**.

---

## 3. Gestão de Lacunas e Integridade Amostral

- Municípios com insuficiência amostral ou dados ausentes na fonte censitária (`dados_incompletos`) são mantidos selecionáveis e visíveis.
- Não há imputação artificial nem substituição de dados ausentes por zero. Indicadores não calculados permanecem devidamente sinalizados como incompletos.

---

## 4. Fontes e Proveniência Rastreável

- **Tabela SIDRA 6881:** Área dos estabelecimentos, pastagens naturais e matas/florestas naturais.
- **Tabela SIDRA 6898:** Valor da produção agropecuária.
- **Tabela SIDRA 6780:** Estabelecimentos com assistência técnica.
- **Tabela SIDRA 6773:** Estabelecimentos associados a cooperativas.
- **Malha Municipal IBGE 2022:** Cartografia vetorial dos municípios do RS.
