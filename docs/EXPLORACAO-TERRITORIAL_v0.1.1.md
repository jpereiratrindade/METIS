# MÉTIS — Especificação Técnica v0.1.1: Exploração e Descrição Agroterritorial Municipal

**Documento:** METIS-SPEC-EXP-002  
**Versão:** 0.1.1  
**Data:** 2026-10-28  
**Estágio da engenharia:** Especificação funcional e arquitetural da interface de exploração em dois níveis  
**Princípio orientador:** *"O MÉTIS não precisa conhecer previamente os limites de seu modelo para permitir que o pesquisador os identifique. A primeira forma de inteligência do sistema reside na maneira como organiza, descreve e torna examináveis as relações entre dados, representações matemáticas e o território."*

---

## 1. Propósito e Reorientação Epistêmica

O MÉTIS é um laboratório de **análise agroterritorial geral** para os 497 municípios do Rio Grande do Sul. Neste estágio de maturação (v0.1.1), o sistema prioriza a **descritibilidade rigorosa e transparente**:
1. Organizar e tornar auditáveis todos os dados censitários utilizados (Censo Agropecuário 2017).
2. Decompor cada indicador ($E, P, S, R$) em suas operações matemáticas explícitas, parâmetros normativos ($q_{10}, q_{90}$) e proveniência de dados.
3. Permitir a exploração territorial sem acoplamento a casos particulares, garantindo que o pesquisador compreenda a origem de qualquer resultado numérico (inclusive valores truncados em zero ou registros com lacunas amostrais).

---

## 2. Arquitetura de Exploração Territorial em Dois Níveis

### 2.1. Nível 1: Visão Cartográfica Estadual & Zoom Municipal Dinâmico
- **Preservação do SVG Puro:** O mapa continua sendo renderizado em vetor puro (`<svg id="map">`), sem dependência de bibliotecas geoespaciais pesadas externas (Leaflet, Mapbox, OpenLayers).
- **Enquadramento Dinâmico via `viewBox`:**
  - Em estado normal: `viewBox="0 0 740 590"` abrange o estado completo do Rio Grande do Sul.
  - Ao selecionar um município (por clique na malha ou busca):
    1. Calcula-se a caixa envolvente (*bounding box*) $[x_{\min}, y_{\min}, x_{\max}, y_{\max}]$ da geometria selecionada.
    2. Aplica-se um espaçamento relativo (*padding* de 20% a 30%) para manter contexto geográfico.
    3. Anima-se suavemente a transição do atributo `viewBox` do SVG.
- **Controle de Retorno à Visão Estadual:**
  - Um botão de controle flutuante no mapa (`↺ Visão Estadual`) permite restaurar o enquadramento completo a qualquer instante sem perder a seleção do município no painel analítico.

### 2.2. Nível 2: Detalhamento Analítico Modular ($E, P, S, R$)
O painel lateral organiza as informações em seções ou abas modulares:

1. **Estado Geral ($R$):**
   - Equação fundamental: $R = E \times (P + S)$
   - Pontuação global e classificação de status (`experimental` ou `dados_incompletos`).
2. **Dimensão Ecológica ($E$):**
   - Fórmula: $e = \frac{\text{pastagem\_natural} + \text{mata\_natural}}{\text{area\_total}}$; $E = 0,5 + \text{clamp}(e, 0, 1)$
   - Percentual de vegetação natural e interpretação do multiplicador (atenuador se $< 1,0$; amplificador se $\ge 1,0$).
3. **Dimensão Produtiva ($P$):**
   - Fórmula: $L = \ln(1 + \text{VP}/\text{área})$; $P = 50 \times \text{clamp}\left(\frac{L - q_{10}}{q_{90} - q_{10}}, 0, 1\right)$
   - Apresentação da densidade monetária calculada (R$/ha), comparada aos limites percentis $q_{10}$ e $q_{90}$ registrados no manifesto de calibração.
   - Explicação explícita: *"Pontuação zero resulta do corte pelo percentil inferior ($q_{10}$), indicando menor densidade monetária por hectare em relação ao universo estadual, não ausência de produção."*
4. **Dimensão Social ($S$):**
   - Fórmula: $S = 25 \times \left(\frac{N_{\text{assistência}}}{N_{\text{total}}} + \frac{N_{\text{cooperativa}}}{N_{\text{total}}}\right)$
   - Proporção de assistência técnica e de associativismo agropecuário.

---

## 3. Gestão de Lacunas e Dados Incompletos

- Municípios com insuficiência de reporte amostral no SIDRA (`dados_incompletos`) devem permanecer:
  1. Plenamente visíveis e selecionáveis na cartografia (preenchimento neutro `#1e293b`).
  2. Com documentação das variáveis específicas faltantes no painel de diagnóstico (distinção formal entre dado zero e dado ausente).

---

## 4. Fontes e Proveniência Rastreável

Todas as variáveis mantêm rastreabilidade direta com os conjuntos de dados homologados:
- **Tabela SIDRA 6881:** Área dos estabelecimentos, pastagens naturais e matas/florestas naturais.
- **Tabela SIDRA 6898:** Valor total da produção agropecuária.
- **Tabela SIDRA 6780:** Estabelecimentos com orientação técnica recebida.
- **Tabela SIDRA 6773:** Estabelecimentos com produtor associado a cooperativas.
- **Malha Municipal IBGE 2022:** Geometria cartográfica oficial do Rio Grande do Sul.
