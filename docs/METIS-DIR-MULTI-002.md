# MÉTIS — Diretriz de Evolução para Laboratório Multimodelo e Multitemporal
**Documento:** METIS-DIR-MULTI-002  
**Versão:** 0.3.0  
**Data:** 28/10/2026  
**Natureza:** Orientação científica e arquitetural para o laboratório multimodelo  
**Prioridade:** Alta  

---

## 1. Decisão Epistêmica e Metodológica

O MÉTIS evolui de um calculador de índice fixo para um **laboratório computacional multimodelo e multitemporal**, no qual o pesquisador seleciona um município, escolhe um modelo e investiga como diferentes hipóteses, parametrizações e trajetórias produzem interpretações distintas das condições agroterritoriais.

> **Hipótese de investigação estruturante:**  
> *"Diferentes formulações matemáticas, aplicadas a um mesmo sistema territorial, podem produzir representações distintas de suas condições e trajetórias. O confronto entre essas representações, os dados disponíveis e as evidências históricas permite investigar os limites, a sensibilidade e a pertinência científica de cada modelo."*

A escolha do modelo torna-se parte explícita e auditável do método de investigação.

---

## 2. Distinção Conceitual Quádrupla

Para garantir o rigor analítico, o MÉTIS distingue formalmente quatro elementos:

| Elemento | Função no Sistema | Exemplo no MÉTIS |
| :--- | :--- | :--- |
| **Variáveis** | Dados observados brutos coletados em fontes oficiais | Área total, valor da produção, matas, pastagens (Censo Agropecuário 2017) |
| **Indicadores** | Transformações e relações matemáticas construídas a partir das variáveis | Densidade monetária ($d_m = \text{VP}/A$), proporção vegetal ($e$), cobertura de assistência |
| **Modelos** | Formulações conceituais que organizam indicadores, componentes e suas interações | EPS-REF-001 (Referência), EPS-EXP-002 (Aditivo), EPS-EXP-003 (Interativo), EPS-EXP-004 (Autônomo) |
| **Cenários** | Execuções de um modelo com parâmetros, pesos e condições experimentais definidos | $k = 1500{,}0\text{ R\$/ha}$, $\lambda = 0{,}5$, pesos aditivos $(0{,}33, 0{,}33, 0{,}34)$ |

Dois modelos utilizam os mesmos dados observados e produzem resultados distintos porque representam **hipóteses teóricas concorrentes**.

---

## 3. Três Eixos Independentes de Investigação

O pesquisador navega através de três eixos ortogonais:

1. **Eixo 1 — Modelo:** Seleção da formulação conceitual ativa no catálogo de modelos.
2. **Eixo 2 — Ano de Referência:** Identificação da base temporal censitária (iniciando com 2017, com arquitetura extensível para séries históricas compatíveis).
3. **Eixo 3 — Tipo de Trajetória:**
   - **Histórica:** Leitura de observações consolidadas de períodos sucessivos.
   - **Experimental:** Exploração de cenários contrafactuais, calibrações de escala e análise de sensibilidade paramétrica.

---

## 4. O Catálogo de Modelos do MÉTIS

### 4.1. EPS-REF-001 — Modelo de Referência Histórica
- **Hipótese:** Estrutura original de resiliência acoplada $R_m = E_m(P_m + S_m)$, com dimensão produtiva calibrada pela distribuição empírica dos municípios gaúchos (percentis $q_{10} = 7{,}273$ e $q_{90} = 8{,}932$ sobre $\ln(1+d_m)$).
- **Papel:** Referência histórica imutável preservada para confronto e reprodução.

### 4.2. EPS-EXP-002 — Modelo Aditivo Ponderado
- **Hipótese:** Dimensões ecológica, produtiva e social operam como esferas autônomas e independentes, combinadas linearmente por soma ponderada sem condicionamento multiplicativo restritivo.
- **Equação:**  
  $$R_m = w_e \cdot E_{\text{norm}} + w_p \cdot P_{100} + w_s \cdot S_{100}$$  
  onde $w_e + w_p + w_s = 1{,}0$ (padrão: $0{,}33; 0{,}33; 0{,}34$).

### 4.3. EPS-EXP-003 — Modelo Interativo com Acoplamento Não-Linear
- **Hipótese:** As dimensões ecológica, produtiva e social produzem sinergias explícitas; a coesão social/cooperativa potencializa a eficiência produtiva econômica sob a modulação ecossistêmica.
- **Equação:**  
  $$R_m = E_m \cdot (P_m + S_m) + \lambda \cdot \frac{P_m \cdot S_m}{50}$$  
  onde $\lambda \in [0, 1]$ expressa a intensidade da sinergia socio-produtiva interativa (padrão: $\lambda = 0{,}5$).

### 4.4. EPS-EXP-004 — Modelo Autônomo Municipal (METIS-DIR-MUN-001)
- **Hipótese:** O município é uma unidade individual de investigação sem normalização intermunicipal. A dimensão produtiva utiliza parâmetro de escala explícito $k$ (em R$/ha$) e $R_m = E_m(P_m + S_m)$.
- **Equação:**  
  $$P_m(k) = 50 \cdot \frac{d_m}{d_m + k}, \quad R_m = E_m \cdot (P_m + S_m)$$

---

## 5. Princípios de Implementação e Interface

1. **Bancada Epistêmica Triaxial no Cabeçalho:**
   Apresentação clara da configuração ativa:  
   `[ Modelo ] · [ Ano ] · [ Trajetória ]`
2. **Confronto Exclusivamente Intramunicipal:**
   Ao selecionar um município, a interface disponibiliza uma matriz comparativa entre os modelos do catálogo para aquele município específico, confrontando pontuações, desvios e interpretações teóricas.
3. **Cartografia Reativa:**
   O mapa estadual é caracterizado por $R$ (ou $E, P, S$) e reage dinamicamente à troca de modelo, ano ou parâmetros em tempo real.
4. **Transparência de Limites:**
   Nenhum modelo é apresentado como empiricamente validado ou definitivo. As divergências entre modelos constituem objeto de reflexão científica.
