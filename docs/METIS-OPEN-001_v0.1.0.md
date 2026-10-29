# MÉTIS — Instrução de Implementação: Laboratório Científico Aberto
**Documento:** METIS-OPEN-001  
**Versão:** 0.1.0  
**Data:** 29/10/2026  
**Natureza:** Diretriz arquitetural, epistêmica e técnica para abertura pública  
**Status:** Em implementação

---

## 1. Princípio de Acesso Público

O MÉTIS adota a **publicidade irrestrita como princípio arquitetural fundamental**:

1. **Acesso sem autenticação:** Todas as ferramentas de consulta, visualização territorial, dashboard analítico e experimentação paramétrica são acessíveis sem necessidade de cadastro, autenticação ou login.
2. **Auditabilidade integral:** Dados brutos, fontes censitárias oficiais (IBGE Censo Agropecuário), equações matemáticas, parâmetros de calibração, resultados calculados e limitações metodológicas devem ser livremente inspecionáveis e exportáveis.
3. **Imutabilidade dos modelos oficiais:** A interface pública permite experimentações paramétricas em tempo real na memória do cliente com emissão de manifestos reproduzíveis, enquanto os modelos de referência oficiais (`EPS-REF-001`, `EPS-EXP-002`, `EPS-EXP-003`, `EPS-EXP-004`) permanecem versionados sob o repositório Git sob a licença **GNU GPL v3.0**.
4. **Isenção de privilégios fictícios:** Ficam eliminados da interface quaisquer papéis administrativos simulados ou referências a servidores proprietários fechados.

---

## 2. Arquitetura de Páginas e Espaços de Trabalho

O sistema organiza-se em quatro espaços complementares, integrados pela mesma identidade visual do **Ecossistema SisTer**:

| Página | Arquivo | Finalidade Principal |
| :--- | :--- | :--- |
| **Apresentação & Notícias** | `web/index.html` (ou portal) | Apresentação institucional, conceitos E-P-S e R, estado atual do laboratório, feed de achados científicos e notícias públicas. |
| **Visão Territorial** | `web/mapa.html` | Cartografia interativa dos 497 municípios do RS com alternância de camadas temáticas (R, E, P, S). |
| **Dashboard Analítico** | `web/dashboard.html` | Exploração analítica independente de mapa, detalhamento de variáveis, bancada triaxial e ajuste de parâmetros. |
| **Modelos & Algoritmos** | `web/modelos.html` | Catálogo matemático formal, pipeline algorítmico passo a passo e dinâmica epistêmica. |

---

## 3. Dashboard Analítico sem Dependência Cartográfica

Para assegurar acessibilidade, rapidez e foco analítico, o dashboard opera de forma totalmente independente da malha GeoJSON:

- **Busca e seleção municipal:** Seletor de municípios gaúchos por nome ou código IBGE.
- **Bancada Epistêmica Triaxial independente:**
  - *Eixo 1 (Modelo):* `EPS-REF-001`, `EPS-EXP-002`, `EPS-EXP-003`, `EPS-EXP-004`.
  - *Eixo 2 (Ano de Referência):* `2017` (Censo Agropecuário oficial).
  - *Eixo 3 (Trajetória):* Experimental (calibração ativa) ou Histórica (leitura estrita).
- **Painel de decomposição:** Indicadores $R, E, P, S$ com visualizações gráficas locais.
- **Tradução das variáveis originais:** Área municipal ($A$), Valor da Produção ($VP$), densidade ($d_m$), vegetação natural ($e$), estabelecimentos com orientação técnica e cooperativismo.
- **Simulador de sensibilidade paramétrica:** Ajuste dinâmico de $k$, pesos dimensionais e intensidade de acoplamento sinérgico.
- **Confronto intramunicipal:** Tabela comparativa entre os modelos para o mesmo município.
- **Exportação reproduzível:** Download de manifesto científico em JSON e tabela em CSV contendo hash da versão e parâmetros utilizados.
- **Ausência estrita de ranqueamentos:** Nenhum índice é convertido em ranking competitivo entre municípios.

---

## 4. Sistema de Achados, Notícias e Resumos Estruturados

O MÉTIS implementa um repositório estruturado de eventos e achados científicos:

### 4.1 Categorias Obrigatórias
1. `atualizacao_tecnica`: Melhorias no código, infraestrutura ou compilação C++26.
2. `resultado_calculado`: Execução formal de modelos sobre bases homologadas.
3. `hipotese`: Proposição de novas relações funcionais ou parâmetros.
4. `simulacao`: Exercício exploratório paramétrico sob cenários hipotéticos.
5. `achado_corroborado`: Padrão confirmado empiricamente e revisado pela governança do laboratório.

### 4.2 Esquema dos Registros de Achados (`achados.json`)
```json
{
  "id": "ACH-2026-001",
  "titulo": "Título assertivo do achado",
  "resumo": "Descrição concisa em linguagem acessível",
  "categoria": "resultado_calculado | hipotese | simulacao | achado_corroborado | atualizacao_tecnica",
  "data": "2026-10-29",
  "municipio_ibge": null,
  "modelo": "EPS-EXP-004",
  "ano_referencia": "2017",
  "trajetoria": "experimental",
  "natureza_evidencia": "Dedução formal C++26 sobre dados SIDRA/IBGE",
  "fontes": ["Censo Agropecuário 2017 - Tabelas 6881, 6898"],
  "versao_metis": "0.1.0",
  "limitacoes": "Escala municipal agregada sem diferenciação intramunicipal",
  "situacao_validacao": "aprovado"
}
```

---

## 5. Distribuição Pública de Conteúdos (API Pública Somente-Leitura)

Endpoints públicos servidos como JSONs estáticos versionados:
- `GET /api/public/achados` (`api/public/achados.json`)
- `GET /api/public/achados/{id}` (`api/public/achados/{id}.json`)
- `GET /api/public/noticias` (`api/public/noticias.json`)
- `GET /api/public/resumos` (`api/public/resumos.json`)
- `GET /api/public/modelos` (`api/public/modelos.json`)

Contratos compatíveis com totens digitais, portais do Ecossistema SisTer e clientes externos.

---

## 6. Revisões Técnicas e Científicas Obrigatórias

1. **Eliminação de identidades fictícias:** Remoção de botões ou perfis de administrador simulados e servidores não verificados.
2. **Proibição de ranqueamento territorial:** O sistema nunca ordena municípios pelo escore de resiliência.
3. **Preservação de EPS-REF-001:** Mantido intacto como linha de base histórica.
4. **Isolamento de credenciais:** Garantia de que arquivos internos (`.git`, `.env`) não são servidos publicamente.
5. **Rastreabilidade e proveniência:** Todo resultado experimental emitido inclui parâmetros, data, hash Git e modelo.

---

## 7. Princípio Orientador

> *O MÉTIS deve tornar públicos não apenas seus resultados, mas também os meios necessários para compreendê-los, experimentá-los, reproduzi-los e questioná-los.*  
> **Sempre pronto. Sempre incompleto.**
