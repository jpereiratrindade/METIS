# MÉTIS — Diretrizes de Usabilidade, Acessibilidade e Boas Práticas de Engenharia
**Documento:** METIS-DIR-USA-001  
**Versão:** 1.2.0  
**Data:** 05/11/2026 (Incorporação do Laudo de Inspeção METIS-REL-USA-002)  
**Natureza:** Avaliação e especificações de usabilidade (Nielsen), exploração visual (Shneiderman), acessibilidade (WCAG 2.1/e-MAG) e ergonomia cognitiva  
**Status:** Vigente e Homologado  

---

## 1. Princípios e Modelos de Referência

O desenvolvimento de interfaces e fluxos analíticos do **MÉTIS** adota quatro referenciais consolidados da ciência da computação e do design de interação humano-computador (IHC):

1. **Heurísticas de Usabilidade de Jakob Nielsen:** 10 regras de ouro para usabilidade de software e sistemas interativos.
2. **Mantra da Exploração de Informação Visual de Ben Shneiderman:** *"Overview first, zoom and filter, then details-on-demand"*.
3. **Diretrizes de Acessibilidade de Conteúdo Web (WCAG 2.1, Nível AA)** e o **Modelo de Acessibilidade em Governo Eletrônico (e-MAG)** do Governo Federal Brasileiro.
4. **Princípios FAIR de Dados e Algoritmos Científicos:** *Findable, Accessible, Interoperable, Reusable*.

---

## 2. Avaliação pelas 10 Heurísticas de Usabilidade de Nielsen

| Heurística | Implementação no MÉTIS | Conformidade |
| :--- | :--- | :---: |
| **1. Visibilidade do status do sistema** | A barra superior (*Topbar*) informa permanentemente os três eixos da bancada epistêmica: `[ Modelo Ativo ] · [ Ano Censitário ] · [ Trajetória ]`. Ao calcular novos parâmetros (ex: slider de $k$), os valores nas tabelas e no mapa atualizam-se instantaneamente com indicativo numérico preciso. Indicador de frescor do INMET informa data e validade da coleta. | **Alta** |
| **2. Correspondência entre o sistema e o mundo real** | O sistema utiliza a linguagem conceitual agronômica e ecológica consagrada ($VP$, Área em hectares, densidade monetária em R$/ha, percentual de cobertura vegetal). O glossário nas páginas diferencia claramente dado bruto de indicador relacional. | **Alta** |
| **3. Controle do usuário e liberdade** | No mapa, botões flutuantes (`↺ Visão Estadual`), botão `↺ Ver todos` na barra do INMET e cliques no fundo restauram imediatamente a visão panorâmica. No simulador, o usuário conta com reset de parâmetros. Fechamento de modais via `Escape`. | **Alta** |
| **4. Consistência e padrões** | Todas as páginas (`index.html`, `mapa.html`, `dashboard.html`, `modelos.html`) compartilham rigorosamente o mesmo *shell* de navegação: mesma barra lateral (*Sidebar*), mesma barra superior (*Topbar*), paleta tipográfica e semântica de cores unificadas. | **Alta** |
| **5. Prevenção de erros** | Municípios com dados omissos na fonte censitária oficial (IBGE) recebem o rótulo formal `dados_incompletos` e são destacados com padrão hachurado neutro, impedindo cálculos enviesados ou a inserção arbitrária de zero. Controles deslizantes contam com limites matemáticos seguros. | **Alta** |
| **6. Reconhecimento em vez de memorização** | As fórmulas matemáticas completas e o significado de cada parâmetro (ex: papel de $k$, peso $w_e$, acoplamento $\lambda$) estão visíveis diretamente no painel contextual ativo, sem exigir que o pesquisador memorize equações de outras páginas. | **Alta** |
| **7. Eficiência e flexibilidade de uso** | Oferece múltiplos modos de exploração: usuários que buscam imersão espacial utilizam a cartografia vetorial (`mapa.html`); usuários focados em números rápidos e conexões lentas contam com o *Dashboard Analítico sem Mapa* (`dashboard.html`). Usuários avançados contam com a CLI em C++26 e a API REST pública em JSON. | **Alta** |
| **8. Estética e design minimalista** | Interface limpa e despoluída, sem anúncios, sem pop-ups, sem banners promocionais e sem ruído visual. Hierarquia tipográfica orientada pela legibilidade (Inter/SF Pro e fontes monoespaçadas para termos científicos e códigos IBGE). | **Alta** |
| **9. Auxílio aos usuários para reconhecer, diagnosticar e recuperar erros** | Mensagens de diagnóstico explícitas e em português: quando um município não possui dados de cooperativismo ou orientação técnica, o sistema informa exatamente qual variável ausente impediu o cômputo da dimensão social, indicando o código da tabela censitária de origem. | **Alta** |
| **10. Ajuda e documentação** | Além dos manuais de arquitetura na pasta `/docs`, o sistema dispõe de página própria de transparência matemática (`modelos.html`), feed de resumos em linguagem didática simplificada para divulgação científica (`resumos.json`) e rotas documentadas de API. | **Alta** |

---

## 3. Aplicação do Modelo de Shneiderman (Exploração Visual)

A cartografia interativa (`web/mapa.html`) e o ambiente analítico implementam com fidelidade a tríade de Shneiderman:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. VISÃO GERAL (Overview First)                                 │
│    - Malha vetorial SVG dos 497 municípios do Rio Grande do Sul │
│    - Inicialização limpa e neutra (sem pré-seleção arbitrária)  │
│    - Distribuição temática global de R, ΔR, INMET, Adapta, E,P,S│
├─────────────────────────────────────────────────────────────────┤
│ 2. ZOOM E FILTRAGEM (Zoom & Filter)                             │
│    - Busca por nome do município ou código IBGE com sugestões   │
│    - Filtro e seleção de alertas meteorológicos individuais     │
│    - Transição suave de viewBox centrada no município escolhido │
│    - Filtro de camadas temáticas no topo do mapa                │
├─────────────────────────────────────────────────────────────────┤
│ 3. DETALHES SOB DEMANDA (Details-on-Demand)                     │
│    - Painel lateral municipal em 7 áreas especializadas:        │
│      Área D: Resultados e decomposição dimensional              │
│      Área T: Trajetória decenal comparada (Censos 2006 vs 2017) │
│      Área E: Evidências climáticas (AdaptaBrasil) e INMET       │
│      Área M: Matriz de confronto multimodelo                    │
│      Área A: Insumos censitários brutos (IBGE/SIDRA)            │
│      Área B: Parametrização e sensibilidade experimental        │
│      Área C: Hipótese matemática subjacente                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Diretrizes Normativas de Acessibilidade Digital (WCAG 2.1 AA / e-MAG)

### 4.1. Perceptibilidade
- **Contraste de Cores:** A paleta de cores atende à razão mínima de contraste de 4.5:1 para texto normal e 3:1 para texto grande e componentes de interface (conforme critério de sucesso 1.4.3 da WCAG 2.1).
- **Independência de Cores:** Informações sobre incompletude ou estado dos dados não dependem exclusivamente de matiz cromática; utilizam ícones, textos e padrões de preenchimento específicos.
- **Tipografia Escalonável:** Unidades relativas (`rem`, `%`) em folhas de estilo, permitindo ampliação de fonte em até 200% via navegador sem quebra de layout.

### 4.2. Operabilidade
- **Navegação Integral por Teclado (Critério 2.1.1):** Todos os elementos interativos — incluindo cada polígono municipal `<path>` no SVG do mapa, botões de abas, seletores de modelos e sliders — devem ser focalizáveis e ativáveis por teclado (`Tab`, `Shift+Tab`, `Enter`, `Espaço`, `Setas`).
- **Anel de Foco Visível (Critério 2.4.7):** Elementos interativos no mapa e nos painéis devem exibir contorno nítido via `:focus-visible` (`outline: 2px solid var(--sky); outline-offset: 2px`).
- **Sem Limites de Tempo (Critério 2.2.1):** As interfaces não impõem timeouts, contagens regressivas ou expirações de sessão.

### 4.3. Compreensibilidade
- **Idioma Declarado:** Atributo `lang="pt-BR"` declarado explicitamente em todas as páginas HTML.
- **Entrada Não-Intrusiva (Critério 3.2.2):** O campo de busca municipal não deve sequestrar o foco nem disparar zooms involuntários ao digitar; deve exibir lista de sugestões suspensa navegável e acionar a seleção somente após confirmação (`Enter` ou clique).
- **Semântica ARIA Robusta (Critério 4.1.2):** Botões de camadas devem conter `aria-pressed="true|false"` e as abas analíticas devem conter `role="tab"`, `aria-selected="true|false"` dentro de container `role="tablist"`.

---

## 5. Decisões de Design e Salvaguardas Epistêmicas

### 5.1. Inicialização em Visão Panorâmica Estadual Limpa
- **Decisão:** O sistema inicia sem nenhum município pré-selecionado (`current = null`).
- **Justificativa Ética:** A pré-seleção forçada de qualquer município viola o princípio de neutralidade científica do laboratório, induzindo o usuário a focar em uma localidade arbitrária. A interface acolhe o pesquisador com a visão global do Rio Grande do Sul e um convite explícito para pesquisa ou exploração livre na malha.

### 5.2. Proibição Expressa de Ranqueamentos Competitivos
- O MÉTIS veda a classificação unidimensional de municípios como "melhores" ou "piores". O confronto é intra-territorial e multimodelo: como diferentes hipóteses interpretam as condições daquele mesmo território.

---

## 6. Auditoria Técnica e Backlog de Acessibilidade (METIS-REL-USA-002)

O laudo pericial formalizado no documento `METIS-REL-USA-002` estabeleceu o backlog priorizado:
- **P0:** Habilitação de `Enter`/`Espaço` e `:focus-visible` nos `<path>` do mapa SVG;
- **P0:** Busca não-intrusiva com `<datalist>` e cancelamento suave via `Escape`;
- **P1:** Alinhamento do estado inicial neutro no Dashboard (`dashboard.js`);
- **P1:** Enriquecimento de atributos ARIA (`aria-pressed`, `role="tab"`, `aria-selected`);
- **P1:** Correção da mensagem do `#map-placeholder`.
