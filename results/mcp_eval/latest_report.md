# Relatório de Estresse e Avaliação MCP — MÉTIS
- **Data:** 2026-11-11T17:51:25.092245+00:00
- **Chamadas:** 56 (concorrência=8, 208.08 req/s)
- **Paridade C++26:** PASSED (máx diff=0.0)

## Métricas por Ferramenta
| Ferramenta | Chamadas | Erros | p50 (ms) | p95 (ms) | Max Bytes | ~Tokens Max |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| `capabilities` | 4 | 0 | 82.2 | 87.32 | 1074 | 268 |
| `search_municipalities` | 8 | 0 | 53.91 | 102.4 | 2069 | 517 |
| `municipality_dossier` | 4 | 0 | 6.17 | 29.69 | 7411 | 1853 |
| `confront_models` | 4 | 0 | 1.07 | 12.53 | 2916 | 729 |
| `simulate_scenario` | 12 | 0 | 7.42 | 30.49 | 8678 | 2170 |
| `inmet_alerts` | 8 | 0 | 55.22 | 115.67 | 7670 | 1918 |
| `investigation_episodes` | 4 | 0 | 8.76 | 15.52 | 13563 | 3391 |
| `scientific_catalog` | 8 | 0 | 0.59 | 2.58 | 5016 | 1254 |
| `verify` | 4 | 0 | 62.89 | 72.09 | 453 | 113 |

## Achados e Oportunidades de Melhoria
- **[INFORMATIVA] `fluxo_cientifico`:** 4609 episódio(s) de investigação ainda com desfecho 'em_aberto'. *Recomendação:* Habilitar revisão assistida no navegador para registrar evidências de impacto pós-evento.
