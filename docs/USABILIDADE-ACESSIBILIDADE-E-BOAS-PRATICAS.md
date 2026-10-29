# MÉTIS — Diretrizes de Usabilidade, Acessibilidade e Boas Práticas de Engenharia
**Documento:** METIS-DIR-USA-001  
**Versão:** 1.0.0  
**Data:** 29/10/2026  
**Natureza:** Avaliação e especificações de usabilidade (Nielsen), exploração visual (Shneiderman), acessibilidade (WCAG 2.1/e-MAG) e integridade de software  
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
| **1. Visibilidade do status do sistema** | A barra superior (*Topbar*) informa permanentemente os três eixos da bancada epistêmica: `[ Modelo Ativo ] · [ Ano Censitário ] · [ Trajetória ]`. Ao calcular novos parâmetros (ex: slider de $k$), os valores nas tabelas e no mapa atualizam-se instantaneamente com indicativo numérico preciso. | **Alta** |
| **2. Correspondência entre o sistema e o mundo real** | O sistema utiliza a linguagem conceitual agronômica e ecológica consagrada ($VP$, Área em hectares, densidade monetária em R$/ha, percentual de cobertura vegetal). O glossário nas páginas diferencia claramente dado bruto de indicador relacional. | **Alta** |
| **3. Controle do usuário e liberdade** | No mapa, botões flutuantes (`↺ Visão Estadual`) e cliques no fundo restauram imediatamente a visão panorâmica sem prender o usuário em zooms indesejados. No simulador, o usuário pode resetar parâmetros para as calibrações de referência. | **Alta** |
| **4. Consistência e padrões** | Todas as páginas (`index.html`, `mapa.html`, `dashboard.html`, `modelos.html`) compartilham rigorosamente o mesmo *shell* de navegação: mesma barra lateral (*Sidebar*), mesma barra superior (*Topbar*), paleta tipográfica e semântica de cores unificadas. | **Alta** |
| **5. Prevenção de erros** | Municípios com dados omissos na fonte censitária oficial (IBGE) recebem o rótulo formal `dados_incompletos` e são destacados com padrão hachurado neutro, impedindo cálculos enviesados ou a inserção arbitrária de zero. Controles deslizantes contam com limites matemáticos seguros. | **Alta** |
| **6. Reconhecimento em vez de memorização** | As fórmulas matemáticas completas e o significado de cada parâmetro (ex: papel de $k$, peso $w_e$, acoplamento $\lambda$) estão visíveis diretamente no painel contextual ativo, sem exigir que o pesquisador memorize equações de outras páginas. | **Alta** |
| **7. Eficiência e flexibilidade de uso** | Oferece múltiplos modos de exploração: usuários que buscam imersão espacial utilizam a cartografia vetorial (`mapa.html`); usuários focados em números rápidos e conexões lentas contam com o *Dashboard Analítico sem Mapa* (`dashboard.html`). Usuários avançados contam com a CLI em C++26 e a API REST pública em JSON. | **Alta** |
| **8. Estética e design minimalista** | Interface limpa e despoluída, sem anúncios, sem pop-ups, sem banners promocionais e sem ruído visual. Hierarquia tipográfica orientada pela legibilidade (Inter/SF Pro e fontes monoespaçadas para termos científicos e códigos IBGE). | **Alta** |
| **9. Auxílio aos usuários para reconhecer, diagnosticar e recuperar erros** | Mensagens de diagnóstico explícitas e em português: quando um município não possui dados de cooperativismo ou orientação técnica, o sistema informa exatamente qual variável ausente impediu o cômputo da dimensão social, indicando o código da tabela censitária de origem. | **Alta** |
| **10. Ajuda e documentação** | Além dos manuais de arquitetura na pasta `/docs`, o sistema dispõe de página própria de transparência matemática (`modelos.html`) e feed de resumos em linguagem didática simplificada para divulgação científica (`resumos.json`). | **Alta** |

---

## 3. Aplicação do Modelo de Shneiderman (Exploração Visual)

A cartografia interativa (`web/mapa.html`) e o ambiente analítico implementam com fidelidade a tríade de Shneiderman:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. VISÃO GERAL (Overview First)                                 │
│    - Malha vetorial SVG dos 497 municípios do Rio Grande do Sul │
│    - Distribuição temática global de R, E, P ou S               │
├─────────────────────────────────────────────────────────────────┤
│ 2. ZOOM E FILTRAGEM (Zoom & Filter)                             │
│    - Busca dinâmica por nome do município ou código IBGE        │
│    - Transição suave de viewBox centrada no município escolhido │
│    - Filtro de camadas temáticas no topo do mapa                │
├─────────────────────────────────────────────────────────────────┤
│ 3. DETALHES SOB DEMANDA (Details-on-Demand)                     │
│    - Painel lateral municipal em 4 áreas especializadas         │
│      Área A: Insumos censitários brutos                         │
│      Área B: Parametrização e sensibilidade                     │
│      Área C: Hipótese matemática subjacente                     │
│      Área D: Resultados e matriz de confronto intramunicipal    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Diretrizes de Acessibilidade Web (WCAG 2.1 AA / e-MAG)

O MÉTIS foi projetado com foco em acessibilidade universal, atendendo aos quatro princípios fundamentais das diretrizes internacionais e do Modelo de Acessibilidade em Governo Eletrônico (e-MAG):

### 4.1. Perceptibilidade
- **Contraste de Cores:** A paleta de cores (fundo escuro/claro com texto de alto contraste) atende à razão mínima de contraste de 4.5:1 para texto normal e 3:1 para texto grande e componentes de interface (conforme critério de sucesso 1.4.3 da WCAG 2.1).
- **Independência de Cores:** Informações sobre incompletude ou estado dos dados não dependem exclusivamente de matiz cromática; utilizam ícones, textos e padrões de preenchimento específicos.
- **Tipografia Escalonável:** Unidades relativas (`rem`, `%`) em folhas de estilo, permitindo ampliação de fonte em até 200% via navegador sem quebra de layout.

### 4.2. Operabilidade
- **Navegação por Teclado:** Todos os elementos interativos (links de menu, seletores de modelos, campos de busca, botões de filtro e sliders numéricos) são focalizáveis e operáveis via teclado (`Tab`, `Shift+Tab`, `Enter`, `Espaço`, `Setas`).
- **Rótulos ARIA:** Aplicação de `aria-label`, `role="group"`, `role="region"` e `aria-hidden` em SVGs decorativos e controles de busca, assegurando interpretação correta por leitores de tela (ex: NVDA, Orca, VoiceOver).
- **Sem Limites de Tempo:** As interfaces não impõem timeouts, contagens regressivas ou expirações de sessão.

### 4.3. Compreensibilidade
- **Idioma Declarado:** Atributo `lang="pt-BR"` declarado explicitamente em todas as páginas HTML.
- **Previsibilidade:** A alternância de abas e parâmetros atualiza as informações no painel de forma determinística, sem deslocamentos abruptos de tela ou abertura involuntária de novas janelas.
- **Divulgação Científica em Linguagem Clara:** Existência de um feed específico de resumos explicativos (`resumos.json`) para cidadãos não especializados e totens digitais.

### 4.4. Robustez
- **HTML5 Válido e Semântico:** Uso correto de tags semânticas estruturantes (`<header>`, `<nav>`, `<main>`, `<aside>`, `<section>`, `<article>`, `<footer>`).
- **Renderização Nativa e Resiliente:** Ausência de dependência de bibliotecas externas pesadas (sem CDNs terceiros de scripts proprietários), permitindo execução local autônoma e em redes com conectividade restrita.

---

## 5. Transparência Algorítmica e Salvaguardas Epistêmicas

### 5.1. Distinção Quádrupla Essencial
Para assegurar o rigor da comunicação pública dos resultados, a interface e a documentação mantêm distinção formal e visual constante entre:
1. **Variáveis:** O que foi medido no mundo empírico pelo Censo Agropecuário oficial.
2. **Indicadores:** Transformações matemáticas e relações (ex: densidade de receita por hectare).
3. **Modelos:** Estruturas conceituais que articulam os indicadores sob certas premissas teóricas.
4. **Cenários:** Casos de teste sob calibrações de parâmetros particulares.

### 5.2. Diretriz Anti-Estigmatização e Proibição de Ranqueamento
- Sistemas públicos que classificam municípios por indicadores únicos correm risco de simplificação perigosa e estigmatização de regiões inteiras.
- O MÉTIS adota o princípio de **Confronto Intramunicipal**: ao invés de perguntar *"Qual município é melhor?"*, o pesquisador investiga *"Como diferentes formulações teóricas interpretam as características deste município?"*.

---

## 6. Boas Práticas de Engenharia de Software Adotadas

1. **Reprodutibilidade Determinística:** Implementação de núcleo em C++26 com tipagem estrita e testes automatizados de regressão (`nucleo_modelo`).
2. **Invariância Municipal Testada:** Verificação contínua de que os resultados de um município são matematicamente independentes das variações de outros municípios no modelo `EPS-EXP-004`.
3. **Imutabilidade e Rastreabilidade Git:** Todas as versões de modelos possuem nomenclatura semântica estrita, integridade com soma de verificação e registros históricos preservados.
4. **Arquitetura Desacoplada:** Os dados censitários, o núcleo de processamento matemático, a API JSON estática e as interfaces web operam com contratos de dados transparentes e padronizados.
